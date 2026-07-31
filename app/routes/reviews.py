from flask import Blueprint, request, g
from sqlalchemy import func
from app.extensions import db
from app.models import Review, ReviewVote, Product, Order, OrderItem
from app.utils import ok, err, require_auth, require_moderator, optional_auth, paginate_query

reviews_bp = Blueprint("reviews", __name__)


@reviews_bp.get("")
@require_moderator
def list_all_reviews():
    q = Review.query
    if request.args.get("status"):
        q = q.filter_by(status=request.args["status"])
    if request.args.get("product_id"):
        q = q.filter_by(product_id=int(request.args["product_id"]))
    q = q.order_by(Review.created_at.desc())
    return ok(paginate_query(q))


@reviews_bp.get("/product/<int:product_id>")
@optional_auth
def product_reviews(product_id):
    q = Review.query.filter_by(product_id=product_id, status="approved")
    sort = request.args.get("sort", "newest")
    if sort == "highest":
        q = q.order_by(Review.rating.desc())
    elif sort == "lowest":
        q = q.order_by(Review.rating.asc())
    elif sort == "helpful":
        q = q.order_by(Review.helpful_count.desc())
    else:
        q = q.order_by(Review.created_at.desc())
    result = paginate_query(q)
    # Aggregate rating distribution
    dist = db.session.query(Review.rating, func.count(Review.id)).filter_by(
        product_id=product_id, status="approved"
    ).group_by(Review.rating).all()
    result["rating_distribution"] = {str(r): c for r, c in dist}
    return ok(result)


@reviews_bp.post("")
@require_auth
def create_review():
    body = request.get_json(silent=True) or {}
    product_id = body.get("product_id")
    rating = body.get("rating")
    if not product_id or not rating:
        return err("product_id and rating required")
    if not (1 <= int(rating) <= 5):
        return err("rating must be between 1 and 5")

    # One review per user per product
    existing = Review.query.filter_by(user_id=g.current_user.id, product_id=product_id).first()
    if existing:
        return err("You have already reviewed this product", 409)

    # Check verified purchase
    verified = db.session.query(OrderItem).join(Order).filter(
        Order.user_id == g.current_user.id,
        OrderItem.product_id == product_id,
        Order.status.in_(["delivered"]),
    ).first() is not None

    review = Review(
        user_id=g.current_user.id, product_id=product_id,
        rating=int(rating), title=body.get("title"), body=body.get("body"),
        is_verified_purchase=verified, status="approved",
    )
    db.session.add(review)
    db.session.flush()
    _recalc_product_rating(product_id)
    db.session.commit()
    return ok(review.to_dict(), "Review submitted", 201)


@reviews_bp.get("/<int:review_id>")
def get_review(review_id):
    review = Review.query.get_or_404(review_id)
    return ok(review.to_dict())


@reviews_bp.put("/<int:review_id>")
@require_auth
def update_review(review_id):
    review = Review.query.get_or_404(review_id)
    if review.user_id != g.current_user.id and g.current_user.role not in ("admin", "moderator"):
        return err("Forbidden", 403)
    body = request.get_json(silent=True) or {}
    if "rating" in body:
        if not (1 <= int(body["rating"]) <= 5):
            return err("rating must be between 1 and 5")
        review.rating = int(body["rating"])
    for field in ("title", "body"):
        if field in body:
            setattr(review, field, body[field])
    _recalc_product_rating(review.product_id)
    db.session.commit()
    return ok(review.to_dict())


@reviews_bp.delete("/<int:review_id>")
@require_auth
def delete_review(review_id):
    review = Review.query.get_or_404(review_id)
    if review.user_id != g.current_user.id and g.current_user.role not in ("admin", "moderator"):
        return err("Forbidden", 403)
    product_id = review.product_id
    db.session.delete(review)
    _recalc_product_rating(product_id)
    db.session.commit()
    return ok(msg="Review deleted")


@reviews_bp.post("/<int:review_id>/vote")
@require_auth
def vote_review(review_id):
    review = Review.query.get_or_404(review_id)
    if review.user_id == g.current_user.id:
        return err("Cannot vote on your own review", 400)
    body = request.get_json(silent=True) or {}
    is_helpful = bool(body.get("is_helpful", True))
    existing = ReviewVote.query.filter_by(user_id=g.current_user.id, review_id=review_id).first()
    if existing:
        existing.is_helpful = is_helpful
    else:
        db.session.add(ReviewVote(user_id=g.current_user.id, review_id=review_id, is_helpful=is_helpful))
    # Recalculate helpful_count
    review.helpful_count = ReviewVote.query.filter_by(review_id=review_id, is_helpful=True).count()
    db.session.commit()
    return ok({"helpful_count": review.helpful_count})


@reviews_bp.post("/<int:review_id>/report")
@require_auth
def report_review(review_id):
    review = Review.query.get_or_404(review_id)
    review.report_count = (review.report_count or 0) + 1
    if review.report_count >= 5:
        review.status = "pending"   # flag for moderation
    db.session.commit()
    return ok(msg="Review reported")


@reviews_bp.put("/<int:review_id>/status")
@require_moderator
def set_review_status(review_id):
    review = Review.query.get_or_404(review_id)
    body = request.get_json(silent=True) or {}
    status = body.get("status")
    if status not in ("pending", "approved", "rejected"):
        return err("status must be pending|approved|rejected")
    review.status = status
    _recalc_product_rating(review.product_id)
    db.session.commit()
    return ok(review.to_dict())


def _recalc_product_rating(product_id):
    from sqlalchemy import func as _func
    result = db.session.query(
        _func.avg(Review.rating), _func.count(Review.id)
    ).filter_by(product_id=product_id, status="approved").first()
    product = Product.query.get(product_id)
    if product:
        product.avg_rating = round(float(result[0] or 0), 2)
        product.total_reviews = result[1] or 0
