"""
blueprints/__init__.py
Register all Flask blueprints onto the app in one call.
"""

def register_blueprints(app, csrf):
    from .auth    import auth_bp
    from .billing import billing_bp, stripe_webhook_bp
    from .api     import api_bp
    from .website import website_bp
    from .pages   import pages_bp
    from modules.api_manager import v1 as v1_blueprint

    app.register_blueprint(auth_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(stripe_webhook_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(website_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(v1_blueprint)

    # Exempt the v1 API blueprint and Stripe webhook from CSRF
    csrf.exempt(v1_blueprint)
    csrf.exempt(stripe_webhook_bp)
