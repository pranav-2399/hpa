from flask import Flask
from app.config import Config
from app.extensions import db


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Init extensions
    db.init_app(app)

    # Initialize Prometheus metrics exporter for Flask routes
    try:
        from prometheus_flask_exporter import PrometheusMetrics
        PrometheusMetrics(app)
    except Exception:
        pass

    with app.app_context():
        # Import models so SQLAlchemy registers them
        from app import models  # noqa: F401
        db.create_all()

    # Register blueprints
    from app.routes.health import health_bp
    from app.routes.auth import auth_bp
    from app.routes.users import users_bp
    from app.routes.products import products_bp
    from app.routes.categories import categories_bp
    from app.routes.orders import orders_bp
    from app.routes.cart import cart_bp
    from app.routes.reviews import reviews_bp
    from app.routes.search import search_bp
    from app.routes.analytics import analytics_bp
    from app.routes.notifications import notifications_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(users_bp, url_prefix="/api/users")
    app.register_blueprint(products_bp, url_prefix="/api/products")
    app.register_blueprint(categories_bp, url_prefix="/api/categories")
    app.register_blueprint(orders_bp, url_prefix="/api/orders")
    app.register_blueprint(cart_bp, url_prefix="/api/cart")
    app.register_blueprint(reviews_bp, url_prefix="/api/reviews")
    app.register_blueprint(search_bp, url_prefix="/api/search")
    app.register_blueprint(analytics_bp, url_prefix="/api/analytics")
    app.register_blueprint(notifications_bp, url_prefix="/api/notifications")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")

    return app
