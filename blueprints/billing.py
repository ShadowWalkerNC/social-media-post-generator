"""
blueprints/billing.py
Billing routes: Stripe checkout, portal, cancel.
Stripe webhook lives in its own blueprint so CSRF can be exempted cleanly.
"""

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, jsonify
)
from flask_login import login_required, current_user

from modules.billing_manager import BillingManager

billing_bp        = Blueprint('billing', __name__)
stripe_webhook_bp = Blueprint('stripe_webhook', __name__)


@billing_bp.route('/billing')
@login_required
def billing():
    sub_info     = BillingManager.get_subscription_info(current_user.id)
    current_tier = current_user.subscription_tier
    return render_template('billing.html', sub_info=sub_info, current_tier=current_tier)


@billing_bp.route('/billing/checkout')
@login_required
def billing_checkout():
    plan        = request.args.get('plan', '')
    base        = request.host_url.rstrip('/')
    success_url = f'{base}/billing?upgraded=1'
    cancel_url  = f'{base}/billing'
    url         = BillingManager.create_checkout_session(
        current_user.id, plan, success_url, cancel_url
    )
    if not url:
        flash('Could not start checkout. Please try again.')
        return redirect(url_for('billing.billing'))
    return redirect(url)


@billing_bp.route('/billing/portal')
@login_required
def billing_portal():
    base       = request.host_url.rstrip('/')
    return_url = f'{base}/billing'
    url        = BillingManager.create_customer_portal_session(current_user.id, return_url)
    if not url:
        flash('Could not open billing portal. Please contact support.')
        return redirect(url_for('billing.billing'))
    return redirect(url)


@billing_bp.route('/billing/cancel', methods=['POST'])
@login_required
def billing_cancel():
    ok = BillingManager.cancel_subscription(current_user.id)
    if ok:
        flash('Your plan will cancel at the end of the billing period.', 'success')
    else:
        flash('Could not cancel. Please use Manage Plan or contact support.')
    return redirect(url_for('billing.billing'))


@stripe_webhook_bp.route('/webhooks/stripe', methods=['POST'])
def stripe_webhook():
    payload    = request.data
    sig_header = request.headers.get('Stripe-Signature', '')
    body, code = BillingManager.handle_webhook(payload, sig_header)
    return jsonify(body), code
