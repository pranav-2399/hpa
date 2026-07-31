from flask import Blueprint, request, g
from app.extensions import db
from app.models import Notification
from app.utils import ok, err, require_auth, paginate_query
from datetime import datetime

notifications_bp = Blueprint("notifications", __name__)


@notifications_bp.get("")
@require_auth
def list_notifications():
    q = Notification.query.filter_by(user_id=g.current_user.id)
    if request.args.get("unread_only") == "true":
        q = q.filter_by(is_read=False)
    if request.args.get("type"):
        q = q.filter_by(type=request.args["type"])
    q = q.order_by(Notification.created_at.desc())
    result = paginate_query(q)
    result["unread_count"] = Notification.query.filter_by(
        user_id=g.current_user.id, is_read=False
    ).count()
    return ok(result)


@notifications_bp.put("/<int:notif_id>/read")
@require_auth
def mark_read(notif_id):
    notif = Notification.query.filter_by(id=notif_id, user_id=g.current_user.id).first()
    if not notif:
        return err("Notification not found", 404)
    notif.is_read = True
    notif.read_at = datetime.utcnow()
    db.session.commit()
    return ok(notif.to_dict())


@notifications_bp.put("/read-all")
@require_auth
def mark_all_read():
    now = datetime.utcnow()
    Notification.query.filter_by(user_id=g.current_user.id, is_read=False).update(
        {"is_read": True, "read_at": now}
    )
    db.session.commit()
    return ok(msg="All notifications marked as read")


@notifications_bp.delete("/<int:notif_id>")
@require_auth
def delete_notification(notif_id):
    notif = Notification.query.filter_by(id=notif_id, user_id=g.current_user.id).first()
    if not notif:
        return err("Notification not found", 404)
    db.session.delete(notif)
    db.session.commit()
    return ok(msg="Notification deleted")


@notifications_bp.delete("")
@require_auth
def delete_all_notifications():
    Notification.query.filter_by(user_id=g.current_user.id).delete()
    db.session.commit()
    return ok(msg="All notifications deleted")
