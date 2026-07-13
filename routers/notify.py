"""
routers/notify.py — Hệ thống thông báo push tới khách hàng
GET  /notify/latest        — app poll thông báo mới nhất
POST /admin/notify/send    — admin gửi thông báo
GET  /admin/notify/list    — admin xem lịch sử
"""

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from datetime import datetime

from database import get_db, Base
from config import get_settings

router_public = APIRouter(prefix="/notify",       tags=["notify"])
router_admin  = APIRouter(prefix="/admin/notify", tags=["notify-admin"])


# ── Model ─────────────────────────────────────────────────────

class Notification(Base):
    __tablename__ = "notifications"
    id         = Column(Integer, primary_key=True, autoincrement=True)
    title      = Column(String(200), nullable=False)
    message    = Column(Text,        nullable=False)
    type       = Column(String(20),  default="info")   # info | warning | success
    is_active  = Column(Boolean,     default=True)
    created_at = Column(DateTime,    default=datetime.utcnow)
    created_by = Column(String(100), nullable=True)
    # NULL = gửi cho tất cả khách hàng (broadcast).
    # Có giá trị = chỉ khách hàng có đúng license_key này mới thấy.
    target_key = Column(String(20),  nullable=True, index=True)


# ── Auth ──────────────────────────────────────────────────────

def require_admin(x_admin_token: str = Header(...)):
    if x_admin_token != get_settings().admin_token:
        raise HTTPException(401, "Invalid admin token")


# ── Schemas ───────────────────────────────────────────────────

class SendRequest(BaseModel):
    title:      str
    message:    str
    type:       str = "info"      # info | warning | success


# ── Public ────────────────────────────────────────────────────

@router_public.get("/latest")
def get_latest(key: str = "", db: Session = Depends(get_db)):
    """
    App gọi endpoint này để lấy thông báo đang active.
    Trả về thông báo broadcast (target_key rỗng) + thông báo riêng
    cho đúng license key của app đó (nếu có truyền `key`).
    """
    q = db.query(Notification).filter(Notification.is_active == True)
    if key:
        q = q.filter(
            (Notification.target_key.is_(None)) | (Notification.target_key == key)
        )
    else:
        q = q.filter(Notification.target_key.is_(None))
    items = q.order_by(Notification.created_at.desc()).limit(10).all()
    return [
        {
            "id":         n.id,
            "title":      n.title,
            "message":    n.message,
            "type":       n.type,
            "created_at": n.created_at.isoformat() if n.created_at else "",
        }
        for n in items
    ]


# ── Admin ─────────────────────────────────────────────────────

@router_admin.post("/send", dependencies=[Depends(require_admin)])
def send_notification(body: SendRequest, db: Session = Depends(get_db)):
    """Gửi thông báo tới toàn bộ khách hàng."""
    n = Notification(
        title=body.title,
        message=body.message,
        type=body.type,
    )
    db.add(n)
    db.commit()
    db.refresh(n)
    return {"ok": True, "id": n.id, "title": n.title}


@router_admin.get("/list", dependencies=[Depends(require_admin)])
def list_notifications(db: Session = Depends(get_db)):
    items = (
        db.query(Notification)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id":         n.id,
            "title":      n.title,
            "message":    n.message,
            "type":       n.type,
            "is_active":  n.is_active,
            "target_key": n.target_key or "",
            "created_at": n.created_at.isoformat() if n.created_at else "",
        }
        for n in items
    ]


@router_admin.delete("/{notify_id}", dependencies=[Depends(require_admin)])
def delete_notification(notify_id: int, db: Session = Depends(get_db)):
    """Xóa / ẩn thông báo (khách sẽ không thấy nữa)."""
    n = db.query(Notification).filter_by(id=notify_id).first()
    if not n:
        raise HTTPException(404, "Notification not found")
    n.is_active = False
    db.commit()
    return {"ok": True, "deleted": notify_id}
