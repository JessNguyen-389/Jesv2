"""
routers/update.py — Quản lý phiên bản app
GET  /update/check?version=1.0.0  — kiểm tra có bản mới không
POST /admin/update/release         — admin đăng bản mới
"""

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import Column, String, Boolean, DateTime, Text
from datetime import datetime

from database import get_db, Base
from config import get_settings

router_public = APIRouter(prefix="/update", tags=["update"])
router_admin  = APIRouter(prefix="/admin/update", tags=["update-admin"])


class AppVersion(Base):
    __tablename__ = "app_versions"
    version      = Column(String(20),  primary_key=True)
    download_url = Column(String(500), nullable=False)
    release_note = Column(Text,        nullable=True)
    is_mandatory = Column(Boolean,     default=False)
    created_at   = Column(DateTime,    default=datetime.utcnow)


def require_admin(x_admin_token: str = Header(...)):
    if x_admin_token != get_settings().admin_token:
        raise HTTPException(401, "Invalid admin token")


class ReleaseRequest(BaseModel):
    version:      str
    download_url: str
    release_note: str = ""
    is_mandatory: bool = False


def _ver(v: str):
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except Exception:
        return (0,)


@router_public.get("/check")
def check_update(version: str, db: Session = Depends(get_db)):
    latest = (
        db.query(AppVersion)
        .order_by(AppVersion.created_at.desc())
        .first()
    )
    if not latest:
        return {"has_update": False}

    if _ver(latest.version) > _ver(version):
        return {
            "has_update":      True,
            "latest_version":  latest.version,
            "current_version": version,
            "download_url":    latest.download_url,
            "release_note":    latest.release_note or "",
            "is_mandatory":    latest.is_mandatory,
        }
    return {"has_update": False, "latest_version": latest.version}


@router_admin.post("/release", dependencies=[Depends(require_admin)])
def release_version(body: ReleaseRequest, db: Session = Depends(get_db)):
    existing = db.query(AppVersion).filter_by(version=body.version).first()
    if existing:
        existing.download_url = body.download_url
        existing.release_note = body.release_note
        existing.is_mandatory = body.is_mandatory
        existing.created_at   = datetime.utcnow()
    else:
        db.add(AppVersion(**body.model_dump()))
    db.commit()
    return {"ok": True, "version": body.version}


@router_admin.get("/list", dependencies=[Depends(require_admin)])
def list_versions(db: Session = Depends(get_db)):
    versions = (
        db.query(AppVersion)
        .order_by(AppVersion.created_at.desc())
        .all()
    )
    return [
        {
            "version":      v.version,
            "download_url": v.download_url,
            "release_note": v.release_note,
            "is_mandatory": v.is_mandatory,
            "created_at":   v.created_at,
        }
        for v in versions
    ]
