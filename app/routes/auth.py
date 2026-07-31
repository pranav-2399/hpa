from datetime import datetime
from flask import Blueprint, request, g
from app.extensions import db
from app.models import User, UserSession, Notification
from app.utils import ok, err, require_auth, slugify

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/register")
def register():
    body = request.get_json(silent=True) or {}
    required = ("username", "email", "password")
    missing = [f for f in required if not body.get(f)]
    if missing:
        return err(f"Missing fields: {', '.join(missing)}")

    if User.query.filter_by(email=body["email"]).first():
        return err("Email already registered", 409)
    if User.query.filter_by(username=body["username"]).first():
        return err("Username already taken", 409)
    if len(body["password"]) < 8:
        return err("Password must be at least 8 characters")

    user = User(
        username=body["username"].strip(),
        email=body["email"].lower().strip(),
        first_name=body.get("first_name", ""),
        last_name=body.get("last_name", ""),
        phone=body.get("phone"),
    )
    user.set_password(body["password"])
    db.session.add(user)
    db.session.flush()

    # Welcome notification
    notif = Notification(
        user_id=user.id, type="system",
        title="Welcome!",
        message=f"Hi {user.username}, welcome to the platform.",
    )
    db.session.add(notif)
    db.session.commit()
    return ok(user.to_dict(), "Registration successful", 201)


@auth_bp.post("/login")
def login():
    body = request.get_json(silent=True) or {}
    email = body.get("email", "").lower().strip()
    password = body.get("password", "")
    if not email or not password:
        return err("Email and password required")

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return err("Invalid credentials", 401)
    if not user.is_active:
        return err("Account is disabled", 403)
    if user.banned_at:
        return err(f"Account banned: {user.ban_reason}", 403)

    cfg = request.app.config if hasattr(request, "app") else {}
    session = UserSession.create(
        user_id=user.id,
        ip=request.remote_addr,
        ua=request.user_agent.string[:300] if request.user_agent.string else None,
        expiry_hours=24,
        refresh_days=30,
    )
    user.last_login_at = datetime.utcnow()
    db.session.add(session)
    db.session.commit()

    return ok({
        "user": user.to_dict(),
        "token": session.token,
        "refresh_token": session.refresh_token,
        "expires_at": session.expires_at.isoformat(),
    }, "Login successful")


@auth_bp.post("/logout")
@require_auth
def logout():
    g.current_session.is_revoked = True
    db.session.commit()
    return ok(msg="Logged out")


@auth_bp.post("/logout-all")
@require_auth
def logout_all():
    UserSession.query.filter_by(user_id=g.current_user.id, is_revoked=False).update({"is_revoked": True})
    db.session.commit()
    return ok(msg="All sessions revoked")


@auth_bp.post("/refresh")
def refresh():
    body = request.get_json(silent=True) or {}
    rt = body.get("refresh_token")
    if not rt:
        return err("refresh_token required")
    session = UserSession.query.filter_by(refresh_token=rt, is_revoked=False).first()
    if not session or session.is_refresh_expired():
        return err("Refresh token invalid or expired", 401)

    new_session = UserSession.create(
        user_id=session.user_id,
        ip=request.remote_addr,
        ua=request.user_agent.string[:300] if request.user_agent.string else None,
    )
    session.is_revoked = True
    db.session.add(new_session)
    db.session.commit()
    return ok({
        "token": new_session.token,
        "refresh_token": new_session.refresh_token,
        "expires_at": new_session.expires_at.isoformat(),
    })


@auth_bp.get("/me")
@require_auth
def me():
    return ok(g.current_user.to_dict(include_private=True))


@auth_bp.put("/me")
@require_auth
def update_me():
    body = request.get_json(silent=True) or {}
    user = g.current_user
    for field in ("first_name", "last_name", "bio", "phone", "avatar_url", "email_notifications"):
        if field in body:
            setattr(user, field, body[field])
    db.session.commit()
    return ok(user.to_dict())


@auth_bp.post("/change-password")
@require_auth
def change_password():
    body = request.get_json(silent=True) or {}
    old_pw = body.get("old_password", "")
    new_pw = body.get("new_password", "")
    if not old_pw or not new_pw:
        return err("old_password and new_password required")
    if not g.current_user.check_password(old_pw):
        return err("Current password incorrect", 401)
    if len(new_pw) < 8:
        return err("New password must be at least 8 characters")
    g.current_user.set_password(new_pw)
    # Revoke all other sessions
    UserSession.query.filter(
        UserSession.user_id == g.current_user.id,
        UserSession.id != g.current_session.id,
    ).update({"is_revoked": True})
    db.session.commit()
    return ok(msg="Password changed")


@auth_bp.get("/sessions")
@require_auth
def list_sessions():
    sessions = UserSession.query.filter_by(user_id=g.current_user.id, is_revoked=False).all()
    return ok([{
        "id": s.id, "ip_address": s.ip_address, "created_at": s.created_at.isoformat(),
        "expires_at": s.expires_at.isoformat(), "last_used_at": s.last_used_at.isoformat() if s.last_used_at else None,
        "is_current": s.id == g.current_session.id,
    } for s in sessions])
