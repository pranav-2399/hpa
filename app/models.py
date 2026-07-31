import json
import secrets
from datetime import datetime, timedelta
from app.extensions import db
from werkzeug.security import generate_password_hash, check_password_hash


# ── Association table ────────────────────────────────────────────────────────
product_tags = db.Table(
    "product_tags",
    db.Column("product_id", db.Integer, db.ForeignKey("products.id"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tags.id"), primary_key=True),
)


# ── User / Auth ──────────────────────────────────────────────────────────────
class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    role = db.Column(db.String(20), default="user")   # admin | moderator | user
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    avatar_url = db.Column(db.String(500))
    bio = db.Column(db.Text)
    phone = db.Column(db.String(20))
    email_notifications = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = db.Column(db.DateTime)
    banned_at = db.Column(db.DateTime)
    ban_reason = db.Column(db.Text)

    sessions = db.relationship("UserSession", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    orders = db.relationship("Order", backref="user", lazy="dynamic")
    reviews = db.relationship("Review", backref="user", lazy="dynamic")
    wishlist_items = db.relationship("WishlistItem", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    addresses = db.relationship("Address", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    notifications = db.relationship("Notification", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    cart = db.relationship("Cart", backref="user", uselist=False, cascade="all, delete-orphan")
    review_votes = db.relationship("ReviewVote", backref="user", lazy="dynamic", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self, include_private=False):
        d = {
            "id": self.id, "username": self.username, "email": self.email,
            "first_name": self.first_name, "last_name": self.last_name,
            "role": self.role, "is_active": self.is_active, "is_verified": self.is_verified,
            "avatar_url": self.avatar_url, "bio": self.bio, "phone": self.phone,
            "email_notifications": self.email_notifications,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
        }
        if include_private:
            d["banned_at"] = self.banned_at.isoformat() if self.banned_at else None
            d["ban_reason"] = self.ban_reason
        return d


class UserSession(db.Model):
    __tablename__ = "user_sessions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    refresh_token = db.Column(db.String(64), unique=True, nullable=False)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    refresh_expires_at = db.Column(db.DateTime, nullable=False)
    last_used_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_revoked = db.Column(db.Boolean, default=False)

    def is_expired(self):
        return datetime.utcnow() > self.expires_at or self.is_revoked

    def is_refresh_expired(self):
        return datetime.utcnow() > self.refresh_expires_at or self.is_revoked

    @classmethod
    def create(cls, user_id, ip=None, ua=None, expiry_hours=24, refresh_days=30):
        return cls(
            user_id=user_id,
            token=secrets.token_urlsafe(48),
            refresh_token=secrets.token_urlsafe(48),
            ip_address=ip,
            user_agent=ua,
            expires_at=datetime.utcnow() + timedelta(hours=expiry_hours),
            refresh_expires_at=datetime.utcnow() + timedelta(days=refresh_days),
        )


# ── Catalogue ────────────────────────────────────────────────────────────────
class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)
    parent_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)
    image_url = db.Column(db.String(500))
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    children = db.relationship("Category", backref=db.backref("parent", remote_side=[id]), lazy="dynamic")
    products = db.relationship("Product", backref="category", lazy="dynamic")

    def to_dict(self, include_children=False):
        d = {
            "id": self.id, "name": self.name, "slug": self.slug,
            "description": self.description, "parent_id": self.parent_id,
            "image_url": self.image_url, "sort_order": self.sort_order,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_children:
            d["children"] = [c.to_dict() for c in self.children.filter_by(is_active=True)]
        return d


class Tag(db.Model):
    __tablename__ = "tags"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    slug = db.Column(db.String(60), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "slug": self.slug}


class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)
    short_description = db.Column(db.String(500))
    price = db.Column(db.Numeric(10, 2), nullable=False)
    compare_price = db.Column(db.Numeric(10, 2))
    cost_price = db.Column(db.Numeric(10, 2))
    sku = db.Column(db.String(100), unique=True, index=True)
    stock_quantity = db.Column(db.Integer, default=0)
    low_stock_threshold = db.Column(db.Integer, default=10)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"))
    is_active = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    weight = db.Column(db.Numeric(8, 3))
    dimensions = db.Column(db.String(100))
    avg_rating = db.Column(db.Numeric(3, 2), default=0)
    total_reviews = db.Column(db.Integer, default=0)
    total_sold = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    images = db.relationship("ProductImage", backref="product", lazy="dynamic", cascade="all, delete-orphan")
    tags = db.relationship("Tag", secondary=product_tags, lazy="dynamic")
    reviews = db.relationship("Review", backref="product", lazy="dynamic")
    wishlist_items = db.relationship("WishlistItem", backref="product", lazy="dynamic")

    def to_dict(self, include_images=True, include_tags=True):
        d = {
            "id": self.id, "name": self.name, "slug": self.slug,
            "description": self.description, "short_description": self.short_description,
            "price": float(self.price), "compare_price": float(self.compare_price) if self.compare_price else None,
            "sku": self.sku, "stock_quantity": self.stock_quantity,
            "low_stock_threshold": self.low_stock_threshold,
            "is_active": self.is_active, "is_featured": self.is_featured,
            "category_id": self.category_id,
            "weight": float(self.weight) if self.weight else None,
            "dimensions": self.dimensions,
            "avg_rating": float(self.avg_rating) if self.avg_rating else 0,
            "total_reviews": self.total_reviews, "total_sold": self.total_sold,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_images:
            d["images"] = [img.to_dict() for img in self.images.order_by(ProductImage.sort_order)]
        if include_tags:
            d["tags"] = [t.to_dict() for t in self.tags]
        return d


class ProductImage(db.Model):
    __tablename__ = "product_images"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    alt_text = db.Column(db.String(200))
    sort_order = db.Column(db.Integer, default=0)
    is_primary = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "url": self.url, "alt_text": self.alt_text,
                "sort_order": self.sort_order, "is_primary": self.is_primary}


# ── Cart ─────────────────────────────────────────────────────────────────────
class Cart(db.Model):
    __tablename__ = "carts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, unique=True)
    session_key = db.Column(db.String(64), unique=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    items = db.relationship("CartItem", backref="cart", lazy="dynamic", cascade="all, delete-orphan")

    def total(self):
        return sum(i.unit_price * i.quantity for i in self.items)

    def to_dict(self):
        items = [i.to_dict() for i in self.items]
        return {"id": self.id, "items": items, "item_count": len(items),
                "total": float(self.total()),
                "updated_at": self.updated_at.isoformat() if self.updated_at else None}


class CartItem(db.Model):
    __tablename__ = "cart_items"
    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey("carts.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    product = db.relationship("Product")

    def to_dict(self):
        return {"id": self.id, "product_id": self.product_id, "quantity": self.quantity,
                "unit_price": float(self.unit_price),
                "line_total": float(self.unit_price * self.quantity),
                "product": self.product.to_dict(include_images=False, include_tags=False) if self.product else None}


class Coupon(db.Model):
    __tablename__ = "coupons"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    description = db.Column(db.String(200))
    discount_type = db.Column(db.String(20), nullable=False)  # percentage | fixed
    discount_value = db.Column(db.Numeric(10, 2), nullable=False)
    min_order_amount = db.Column(db.Numeric(10, 2), default=0)
    max_uses = db.Column(db.Integer)
    used_count = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    starts_at = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def is_valid(self):
        now = datetime.utcnow()
        if not self.is_active:
            return False, "Coupon is inactive"
        if self.starts_at and now < self.starts_at:
            return False, "Coupon not yet active"
        if self.expires_at and now > self.expires_at:
            return False, "Coupon has expired"
        if self.max_uses and self.used_count >= self.max_uses:
            return False, "Coupon usage limit reached"
        return True, "OK"

    def to_dict(self):
        return {"id": self.id, "code": self.code, "description": self.description,
                "discount_type": self.discount_type, "discount_value": float(self.discount_value),
                "min_order_amount": float(self.min_order_amount or 0),
                "is_active": self.is_active,
                "expires_at": self.expires_at.isoformat() if self.expires_at else None}


# ── Orders ───────────────────────────────────────────────────────────────────
class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    order_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    status = db.Column(db.String(20), default="pending")   # pending|processing|shipped|delivered|cancelled|refunded
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    tax_amount = db.Column(db.Numeric(10, 2), default=0)
    shipping_amount = db.Column(db.Numeric(10, 2), default=0)
    discount_amount = db.Column(db.Numeric(10, 2), default=0)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    shipping_address = db.Column(db.Text)   # JSON
    billing_address = db.Column(db.Text)    # JSON
    payment_method = db.Column(db.String(50))
    payment_status = db.Column(db.String(20), default="pending")  # pending|paid|failed|refunded
    payment_reference = db.Column(db.String(100))
    coupon_id = db.Column(db.Integer, db.ForeignKey("coupons.id"), nullable=True)
    coupon_code = db.Column(db.String(50))
    notes = db.Column(db.Text)
    shipped_at = db.Column(db.DateTime)
    delivered_at = db.Column(db.DateTime)
    cancelled_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items = db.relationship("OrderItem", backref="order", lazy="dynamic", cascade="all, delete-orphan")
    status_history = db.relationship("OrderStatusHistory", backref="order", lazy="dynamic", cascade="all, delete-orphan")

    def to_dict(self, include_items=False):
        d = {
            "id": self.id, "order_number": self.order_number, "status": self.status,
            "subtotal": float(self.subtotal), "tax_amount": float(self.tax_amount),
            "shipping_amount": float(self.shipping_amount),
            "discount_amount": float(self.discount_amount),
            "total_amount": float(self.total_amount),
            "shipping_address": json.loads(self.shipping_address) if self.shipping_address else None,
            "billing_address": json.loads(self.billing_address) if self.billing_address else None,
            "payment_method": self.payment_method, "payment_status": self.payment_status,
            "coupon_code": self.coupon_code, "notes": self.notes,
            "shipped_at": self.shipped_at.isoformat() if self.shipped_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_items:
            d["items"] = [i.to_dict() for i in self.items]
        return d


class OrderItem(db.Model):
    __tablename__ = "order_items"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
    product_name = db.Column(db.String(200), nullable=False)
    product_sku = db.Column(db.String(100))
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    total_price = db.Column(db.Numeric(10, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "product_id": self.product_id,
                "product_name": self.product_name, "product_sku": self.product_sku,
                "quantity": self.quantity, "unit_price": float(self.unit_price),
                "total_price": float(self.total_price)}


class OrderStatusHistory(db.Model):
    __tablename__ = "order_status_history"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    old_status = db.Column(db.String(20))
    new_status = db.Column(db.String(20), nullable=False)
    note = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "old_status": self.old_status, "new_status": self.new_status,
                "note": self.note, "created_at": self.created_at.isoformat()}


# ── Reviews ──────────────────────────────────────────────────────────────────
class Review(db.Model):
    __tablename__ = "reviews"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=True)
    rating = db.Column(db.Integer, nullable=False)   # 1-5
    title = db.Column(db.String(200))
    body = db.Column(db.Text)
    helpful_count = db.Column(db.Integer, default=0)
    report_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default="approved")   # pending|approved|rejected
    is_verified_purchase = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    votes = db.relationship("ReviewVote", backref="review", lazy="dynamic", cascade="all, delete-orphan")

    def to_dict(self):
        return {"id": self.id, "user_id": self.user_id, "product_id": self.product_id,
                "rating": self.rating, "title": self.title, "body": self.body,
                "helpful_count": self.helpful_count, "report_count": self.report_count,
                "status": self.status, "is_verified_purchase": self.is_verified_purchase,
                "created_at": self.created_at.isoformat() if self.created_at else None}


class ReviewVote(db.Model):
    __tablename__ = "review_votes"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    review_id = db.Column(db.Integer, db.ForeignKey("reviews.id"), nullable=False)
    is_helpful = db.Column(db.Boolean, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("user_id", "review_id"),)


# ── Wishlist / Address ────────────────────────────────────────────────────────
class WishlistItem(db.Model):
    __tablename__ = "wishlist_items"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("user_id", "product_id"),)

    def to_dict(self):
        return {"id": self.id, "product_id": self.product_id,
                "product": self.product.to_dict(include_images=False, include_tags=False) if self.product else None,
                "created_at": self.created_at.isoformat()}


class Address(db.Model):
    __tablename__ = "addresses"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    label = db.Column(db.String(50), default="Home")
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    line1 = db.Column(db.String(200), nullable=False)
    line2 = db.Column(db.String(200))
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100))
    postal_code = db.Column(db.String(20))
    country = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "label": self.label, "first_name": self.first_name,
                "last_name": self.last_name, "line1": self.line1, "line2": self.line2,
                "city": self.city, "state": self.state, "postal_code": self.postal_code,
                "country": self.country, "phone": self.phone, "is_default": self.is_default}


# ── Notifications ────────────────────────────────────────────────────────────
class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    type = db.Column(db.String(50), nullable=False)   # order_update|review_reply|promo|system
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    data = db.Column(db.Text)   # JSON
    is_read = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "type": self.type, "title": self.title, "message": self.message,
                "data": json.loads(self.data) if self.data else None,
                "is_read": self.is_read,
                "read_at": self.read_at.isoformat() if self.read_at else None,
                "created_at": self.created_at.isoformat() if self.created_at else None}


# ── Analytics ────────────────────────────────────────────────────────────────
class AnalyticsEvent(db.Model):
    __tablename__ = "analytics_events"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    session_key = db.Column(db.String(64), index=True)
    event_type = db.Column(db.String(80), nullable=False, index=True)  # page_view|product_view|add_to_cart|purchase|search
    event_data = db.Column(db.Text)   # JSON
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(300))
    page_url = db.Column(db.String(500))
    referrer = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {"id": self.id, "user_id": self.user_id, "event_type": self.event_type,
                "event_data": json.loads(self.event_data) if self.event_data else None,
                "page_url": self.page_url, "created_at": self.created_at.isoformat()}
