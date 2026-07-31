from flask import Blueprint, request, g
from app.extensions import db
from app.models import Category
from app.utils import ok, err, require_auth, require_admin, paginate_query, slugify

categories_bp = Blueprint("categories", __name__)


@categories_bp.get("")
def list_categories():
    """Full category tree (active only unless admin)."""
    flat = request.args.get("flat", "false").lower() == "true"
    q = Category.query
    if request.args.get("include_inactive") != "true":
        q = q.filter_by(is_active=True)
    if flat:
        return ok(paginate_query(q.order_by(Category.sort_order, Category.name)))
    # Tree: top-level only, children embedded
    roots = q.filter_by(parent_id=None).order_by(Category.sort_order, Category.name).all()
    return ok([c.to_dict(include_children=True) for c in roots])


@categories_bp.get("/<int:cat_id>")
def get_category(cat_id):
    cat = Category.query.get_or_404(cat_id)
    return ok(cat.to_dict(include_children=True))


@categories_bp.get("/slug/<slug>")
def get_category_by_slug(slug):
    cat = Category.query.filter_by(slug=slug).first()
    if not cat:
        return err("Category not found", 404)
    return ok(cat.to_dict(include_children=True))


@categories_bp.post("")
@require_admin
def create_category():
    body = request.get_json(silent=True) or {}
    if not body.get("name"):
        return err("name is required")
    slug = body.get("slug") or slugify(body["name"])
    if Category.query.filter_by(slug=slug).first():
        slug = slug + "-" + str(db.session.query(db.func.count(Category.id)).scalar())
    cat = Category(
        name=body["name"], slug=slug,
        description=body.get("description"),
        parent_id=body.get("parent_id"),
        image_url=body.get("image_url"),
        sort_order=body.get("sort_order", 0),
        is_active=body.get("is_active", True),
    )
    db.session.add(cat)
    db.session.commit()
    return ok(cat.to_dict(), "Category created", 201)


@categories_bp.put("/<int:cat_id>")
@require_admin
def update_category(cat_id):
    cat = Category.query.get_or_404(cat_id)
    body = request.get_json(silent=True) or {}
    for field in ("name", "description", "parent_id", "image_url", "sort_order", "is_active"):
        if field in body:
            setattr(cat, field, body[field])
    if "slug" in body:
        cat.slug = body["slug"]
    db.session.commit()
    return ok(cat.to_dict())


@categories_bp.delete("/<int:cat_id>")
@require_admin
def delete_category(cat_id):
    cat = Category.query.get_or_404(cat_id)
    if cat.products.count() > 0:
        return err("Cannot delete category with products. Reassign products first.", 409)
    db.session.delete(cat)
    db.session.commit()
    return ok(msg="Category deleted")


@categories_bp.get("/<int:cat_id>/products")
def category_products(cat_id):
    from app.models import Product
    cat = Category.query.get_or_404(cat_id)
    q = Product.query.filter_by(category_id=cat_id, is_active=True)
    sort = request.args.get("sort", "created_at_desc")
    q = _apply_product_sort(q, sort)
    return ok(paginate_query(q))


def _apply_product_sort(q, sort):
    from app.models import Product
    mapping = {
        "price_asc": Product.price.asc(), "price_desc": Product.price.desc(),
        "name_asc": Product.name.asc(), "rating_desc": Product.avg_rating.desc(),
        "created_at_desc": Product.created_at.desc(),
    }
    return q.order_by(mapping.get(sort, Product.created_at.desc()))
