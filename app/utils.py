import json
from datetime import datetime
from functools import wraps
from flask import request, jsonify, g
from app.extensions import db


# ── Response helpers ──────────────────────────────────────────────────────────
def ok(data=None, msg="OK", status=200):
    return jsonify({"success": True, "message": msg, "data": data}), status


def err(msg, status=400, details=None):
    body = {"success": False, "message": msg}
    if details:
        body["details"] = details
    return jsonify(body), status


# ── Pagination helper ─────────────────────────────────────────────────────────
def paginate_query(query, serializer=None):
    page = max(1, request.args.get("page", 1, int))
    per_page = min(request.args.get("per_page", 20, int), 100)
    p = query.paginate(page=page, per_page=per_page, error_out=False)
    items = [serializer(i) if serializer else i.to_dict() for i in p.items]
    return {
        "items": items, "total": p.total, "page": p.page,
        "per_page": p.per_page, "pages": p.pages,
        "has_next": p.has_next, "has_prev": p.has_prev,
    }


# ── Shared auth check ────────────────────────────────────────────────────────
def _do_auth() :
    """
    Validate Bearer token, populate g.current_user / g.current_session.
    Returns an error response tuple on failure, or None on success.
    """
    token = _extract_token()
    if not token:
        return err("Authentication required", 401)
    from app.models import UserSession, User
    session = UserSession.query.filter_by(token=token, is_revoked=False).first()
    if not session or session.is_expired():
        return err("Token invalid or expired", 401)
    user = User.query.get(session.user_id)
    if not user or not user.is_active:
        return err("Account not found or inactive", 401)
    session.last_used_at = datetime.utcnow()
    db.session.commit()
    g.current_user = user
    g.current_session = session
    return None


# ── Auth decorators ───────────────────────────────────────────────────────────
def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        error = _do_auth()
        if error:
            return error
        return f(*args, **kwargs)
    return decorated


def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        error = _do_auth()
        if error:
            return error
        if g.current_user.role != "admin":
            return err("Admin access required", 403)
        return f(*args, **kwargs)
    return decorated


def require_moderator(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        error = _do_auth()
        if error:
            return error
        if g.current_user.role not in ("admin", "moderator"):
            return err("Moderator access required", 403)
        return f(*args, **kwargs)
    return decorated


def optional_auth(f):
    """Attach user to g if token present, but don't reject unauthenticated."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = _extract_token()
        g.current_user = None
        if token:
            from app.models import UserSession, User
            session = UserSession.query.filter_by(token=token, is_revoked=False).first()
            if session and not session.is_expired():
                g.current_user = User.query.get(session.user_id)
        return f(*args, **kwargs)
    return decorated


def _extract_token():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return request.args.get("token")


# ── Slug helper ───────────────────────────────────────────────────────────────
def slugify(text):
    import re
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text


# ── Order number ──────────────────────────────────────────────────────────────
def generate_order_number():
    import random, string
    return "ORD-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=10))
