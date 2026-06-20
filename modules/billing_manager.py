"""
billing_manager.py — Stripe Subscription Billing (Phase 5 Session 10)

Handles the full Stripe billing lifecycle for PostPilot Pro:

  BillingManager
    ─ create_checkout_session()        — redirect user to Stripe-hosted checkout
    ─ create_customer_portal_session() — self-serve plan change / cancellation
    ─ handle_webhook()                 — process all 5 Stripe events
    ─ get_subscription_info()          — current plan + next billing date
    ─ cancel_subscription()            — mark cancel-at-period-end

Stripe webhook events handled:
    customer.subscription.created     → activate tier
    customer.subscription.updated     → upgrade / downgrade tier
    customer.subscription.deleted     → graceful downgrade to free
    invoice.payment_failed            → lock paid features, email user
    invoice.payment_succeeded         → ensure tier active after retry

Graceful downgrade policy (never delete data):
    - payment_failed:  sub_status → 'past_due', features locked for paid platforms
    - subscription.deleted: tier → 'free', data retained for 30 days
    - User can resubscribe at any time and get their data back immediately

Stripe Price IDs:
    Fill in from Stripe Dashboard → Products → Pricing.
    Set them in .env as STRIPE_PRICE_STARTER_MONTHLY etc.
    or replace the placeholders in STRIPE_PRICES below.
"""

import os
import logging
import stripe
from datetime import datetime
from typing import Optional

from modules.user_manager import UserManager

logger = logging.getLogger(__name__)

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '')

# ---------------------------------------------------------------------------
# Price ID map  — fill in from Stripe Dashboard or .env
# ---------------------------------------------------------------------------
STRIPE_PRICES: dict[str, str] = {
    'starter_monthly':  os.environ.get('STRIPE_PRICE_STARTER_MONTHLY',  'price_starter_monthly'),
    'starter_annual':   os.environ.get('STRIPE_PRICE_STARTER_ANNUAL',   'price_starter_annual'),
    'growth_monthly':   os.environ.get('STRIPE_PRICE_GROWTH_MONTHLY',   'price_growth_monthly'),
    'growth_annual':    os.environ.get('STRIPE_PRICE_GROWTH_ANNUAL',     'price_growth_annual'),
    'pro_monthly':      os.environ.get('STRIPE_PRICE_PRO_MONTHLY',       'price_pro_monthly'),
    'pro_annual':       os.environ.get('STRIPE_PRICE_PRO_ANNUAL',        'price_pro_annual'),
    'agency_monthly':   os.environ.get('STRIPE_PRICE_AGENCY_MONTHLY',    'price_agency_monthly'),
    'agency_annual':    os.environ.get('STRIPE_PRICE_AGENCY_ANNUAL',     'price_agency_annual'),
}

# Reverse map: price_id → tier name
_PRICE_TO_TIER: dict[str, str] = {
    v: k.split('_')[0]   # 'starter_monthly' → 'starter'
    for k, v in STRIPE_PRICES.items()
}


def tier_from_price_id(price_id: str) -> str:
    """
    Map a Stripe Price ID back to a tier name.
    Returns 'free' if the price ID is unknown.
    """
    return _PRICE_TO_TIER.get(price_id, 'free')


# ---------------------------------------------------------------------------
# BillingManager
# ---------------------------------------------------------------------------
class BillingManager:

    # ── Checkout ─────────────────────────────────────────────────────────
    @staticmethod
    def create_checkout_session(
        user_id:     str,
        price_key:   str,
        success_url: str,
        cancel_url:  str,
    ) -> Optional[str]:
        """
        Create a Stripe Checkout session and return the redirect URL.

        Args:
            user_id:     PostPilot user UUID.
            price_key:   Key from STRIPE_PRICES, e.g. 'starter_monthly'.
            success_url: URL to redirect after successful payment.
                         Include {CHECKOUT_SESSION_ID} for verification.
            cancel_url:  URL to redirect if user cancels.

        Returns:
            Stripe Checkout URL string, or None on failure.
        """
        price_id = STRIPE_PRICES.get(price_key)
        if not price_id:
            logger.error('create_checkout_session: unknown price_key=%s', price_key)
            return None

        user = UserManager.get_user(user_id)
        if not user:
            logger.error('create_checkout_session: user not found user_id=%s', user_id)
            return None

        try:
            # Reuse existing Stripe customer if available
            customer_id = user.stripe_customer_id
            if not customer_id:
                customer    = stripe.Customer.create(
                    email    = user.email,
                    metadata = {'postpilot_user_id': user_id},
                )
                customer_id = customer.id
                # Persist customer_id immediately so we don’t create duplicates
                UserManager.update_subscription(
                    user_id,
                    tier               = user.subscription_tier,
                    stripe_customer_id = customer_id,
                )

            session = stripe.checkout.Session.create(
                customer     = customer_id,
                mode         = 'subscription',
                line_items   = [{'price': price_id, 'quantity': 1}],
                success_url  = success_url,
                cancel_url   = cancel_url,
                metadata     = {'postpilot_user_id': user_id},
                allow_promotion_codes = True,
            )
            logger.info('Checkout session created: user=%s price=%s', user_id, price_key)
            return session.url

        except stripe.error.StripeError as e:
            logger.error('Stripe checkout error for user=%s: %s', user_id, e)
            return None

    # ── Customer portal (self-serve plan changes + cancellation) ─────────
    @staticmethod
    def create_customer_portal_session(
        user_id:    str,
        return_url: str,
    ) -> Optional[str]:
        """
        Open the Stripe Customer Portal for self-serve plan management.
        User can upgrade, downgrade, cancel, or update payment method.

        Returns:
            Portal URL string, or None on failure.
        """
        user = UserManager.get_user(user_id)
        if not user or not user.stripe_customer_id:
            logger.error('create_customer_portal_session: no Stripe customer for user=%s', user_id)
            return None

        try:
            portal = stripe.billing_portal.Session.create(
                customer   = user.stripe_customer_id,
                return_url = return_url,
            )
            logger.info('Customer portal session created: user=%s', user_id)
            return portal.url
        except stripe.error.StripeError as e:
            logger.error('Stripe portal error for user=%s: %s', user_id, e)
            return None

    # ── Webhook handler ──────────────────────────────────────────────────
    @staticmethod
    def handle_webhook(payload: bytes, sig_header: str) -> tuple[dict, int]:
        """
        Verify and process an incoming Stripe webhook.

        Call this from the Flask route:
            payload    = request.data
            sig_header = request.headers.get('Stripe-Signature')
            body, code = BillingManager.handle_webhook(payload, sig_header)

        Returns:
            (response_dict, http_status_code)
        """
        webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
        except stripe.error.SignatureVerificationError:
            logger.warning('Stripe webhook: invalid signature')
            return {'error': 'Invalid signature'}, 400
        except Exception as e:
            logger.error('Stripe webhook construct error: %s', e)
            return {'error': str(e)}, 400

        event_type = event['type']
        data       = event['data']['object']

        handlers = {
            'customer.subscription.created':  BillingManager._on_subscription_created,
            'customer.subscription.updated':  BillingManager._on_subscription_updated,
            'customer.subscription.deleted':  BillingManager._on_subscription_deleted,
            'invoice.payment_failed':         BillingManager._on_payment_failed,
            'invoice.payment_succeeded':      BillingManager._on_payment_succeeded,
        }

        handler = handlers.get(event_type)
        if handler:
            handler(data)
            logger.info('Stripe webhook handled: %s', event_type)
        else:
            logger.debug('Stripe webhook ignored: %s', event_type)

        return {'received': True}, 200

    # ── Private event handlers ────────────────────────────────────────────

    @staticmethod
    def _resolve_user(subscription) -> Optional[str]:
        """
        Find the PostPilot user_id from a Stripe subscription object.
        Tries metadata first, falls back to customer email lookup.
        """
        # Check metadata on subscription
        user_id = subscription.get('metadata', {}).get('postpilot_user_id')
        if user_id:
            return user_id

        # Fall back to customer metadata
        try:
            customer = stripe.Customer.retrieve(subscription['customer'])
            user_id  = customer.get('metadata', {}).get('postpilot_user_id')
            if user_id:
                return user_id
            # Last resort: match by email
            user = UserManager.get_user_by_email(customer.get('email', ''))
            return user.id if user else None
        except Exception as e:
            logger.error('_resolve_user error: %s', e)
            return None

    @staticmethod
    def _on_subscription_created(sub):
        """New subscription — activate tier."""
        user_id = BillingManager._resolve_user(sub)
        if not user_id:
            logger.error('subscription.created: cannot resolve user for sub=%s', sub['id'])
            return

        price_id   = sub['items']['data'][0]['price']['id']
        tier       = tier_from_price_id(price_id)
        period_end = datetime.utcfromtimestamp(
            sub['current_period_end']
        ).isoformat()

        UserManager.update_subscription(
            user_id,
            tier               = tier,
            stripe_customer_id = sub['customer'],
            stripe_sub_id      = sub['id'],
            sub_status         = 'active',
            period_end         = period_end,
        )
        logger.info('Subscription created: user=%s tier=%s', user_id, tier)

    @staticmethod
    def _on_subscription_updated(sub):
        """Plan change (upgrade or downgrade) — update tier."""
        user_id = BillingManager._resolve_user(sub)
        if not user_id:
            return

        price_id   = sub['items']['data'][0]['price']['id']
        tier       = tier_from_price_id(price_id)
        status     = sub['status']   # 'active' | 'past_due' | 'cancelled' etc.
        period_end = datetime.utcfromtimestamp(
            sub['current_period_end']
        ).isoformat()

        UserManager.update_subscription(
            user_id,
            tier       = tier,
            sub_status = status,
            period_end = period_end,
        )
        logger.info('Subscription updated: user=%s tier=%s status=%s', user_id, tier, status)

    @staticmethod
    def _on_subscription_deleted(sub):
        """
        Subscription cancelled (end of period or immediate).
        Graceful downgrade: tier → free, data kept, sub_status → 'cancelled'.
        """
        user_id = BillingManager._resolve_user(sub)
        if not user_id:
            return

        UserManager.update_subscription(
            user_id,
            tier       = 'free',
            sub_status = 'cancelled',
        )
        logger.info('Subscription deleted: user=%s → downgraded to free', user_id)

    @staticmethod
    def _on_payment_failed(invoice):
        """
        Payment failed — mark past_due, lock paid features.
        Does NOT delete data. User sees a banner to update payment method.
        Stripe will retry automatically per the retry schedule.
        """
        customer_id = invoice.get('customer')
        if not customer_id:
            return
        try:
            customer = stripe.Customer.retrieve(customer_id)
            user_id  = customer.get('metadata', {}).get('postpilot_user_id')
            if not user_id:
                user = UserManager.get_user_by_email(customer.get('email', ''))
                user_id = user.id if user else None
            if not user_id:
                return

            user = UserManager.get_user(user_id)
            UserManager.update_subscription(
                user_id,
                tier       = user.subscription_tier,  # Keep tier label
                sub_status = 'past_due',               # Lock features
            )
            logger.warning('Payment failed: user=%s → past_due', user_id)
        except Exception as e:
            logger.error('_on_payment_failed error: %s', e)

    @staticmethod
    def _on_payment_succeeded(invoice):
        """
        Payment succeeded (including after a retry).
        Re-activates the subscription if it was past_due.
        """
        sub_id = invoice.get('subscription')
        if not sub_id:
            return
        try:
            sub     = stripe.Subscription.retrieve(sub_id)
            user_id = BillingManager._resolve_user(sub)
            if not user_id:
                return

            price_id   = sub['items']['data'][0]['price']['id']
            tier       = tier_from_price_id(price_id)
            period_end = datetime.utcfromtimestamp(
                sub['current_period_end']
            ).isoformat()

            UserManager.update_subscription(
                user_id,
                tier       = tier,
                sub_status = 'active',
                period_end = period_end,
            )
            logger.info('Payment succeeded: user=%s → active', user_id)
        except Exception as e:
            logger.error('_on_payment_succeeded error: %s', e)

    # ── Subscription info (for billing page) ──────────────────────────────
    @staticmethod
    def get_subscription_info(user_id: str) -> dict:
        """
        Return current subscription details for the billing page.

        Returns:
            {
              tier, sub_status, period_end,
              stripe_customer_id, stripe_sub_id,
              cancel_at_period_end (bool)
            }
        """
        user = UserManager.get_user(user_id)
        if not user:
            return {}

        info = {
            'tier':               user.subscription_tier,
            'sub_status':         user.sub_status,
            'period_end':         user.sub_current_period_end,
            'stripe_customer_id': user.stripe_customer_id,
            'stripe_sub_id':      user.stripe_sub_id,
            'cancel_at_period_end': False,
        }

        # Fetch live cancel_at_period_end from Stripe if sub exists
        if user.stripe_sub_id and stripe.api_key:
            try:
                sub = stripe.Subscription.retrieve(user.stripe_sub_id)
                info['cancel_at_period_end'] = sub.get('cancel_at_period_end', False)
            except Exception:
                pass  # Non-fatal — fall back to DB values

        return info

    # ── Cancel at period end ──────────────────────────────────────────────
    @staticmethod
    def cancel_subscription(user_id: str) -> bool:
        """
        Schedule cancellation at end of current billing period.
        Does NOT cancel immediately — user keeps access until period_end.

        Returns:
            True on success, False on failure.
        """
        user = UserManager.get_user(user_id)
        if not user or not user.stripe_sub_id:
            return False
        try:
            stripe.Subscription.modify(
                user.stripe_sub_id,
                cancel_at_period_end = True,
            )
            logger.info('Subscription cancel-at-period-end set: user=%s', user_id)
            return True
        except stripe.error.StripeError as e:
            logger.error('cancel_subscription error for user=%s: %s', user_id, e)
            return False
