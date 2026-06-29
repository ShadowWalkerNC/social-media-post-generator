"""
blueprints/__init__.py
Register all Flask blueprints onto the app in one call.
"""


def register_blueprints(app, csrf):
    from .auth     import auth_bp
    from .billing  import billing_bp, stripe_webhook_bp
    from .api      import api_bp
    from .website  import website_bp
    from .pages    import pages_bp
    from .cron     import cron_bp
    from .specials import specials_bp
    from .events   import events_bp
    from .hours    import hours_bp
    from modules.api_manager import v1 as v1_blueprint

    app.register_blueprint(auth_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(stripe_webhook_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(website_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(cron_bp)
    app.register_blueprint(specials_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(hours_bp)
    app.register_blueprint(v1_blueprint)

    # Exempt API and webhook blueprints from CSRF
    # cron_bp is authenticated via CRON_SECRET (HMAC), not browser sessions
    csrf.exempt(v1_blueprint)
    csrf.exempt(stripe_webhook_bp)
    csrf.exempt(cron_bp)
    csrf.exempt(api_bp)
    csrf.exempt(specials_bp)
    csrf.exempt(events_bp)
    csrf.exempt(hours_bp)
