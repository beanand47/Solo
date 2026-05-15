from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from fastapi.templating import Jinja2Templates
from redis.exceptions import RedisError
from sqlalchemy.orm import Session

from database import get_db
from models import Task, TeamMember, User
from routers.auth import require_auth
from services import ai_service
from services.jobs import job_generate_onboarding_brief
from services.worker import get_queue
from template_helpers import configure_templates


router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent
templates = configure_templates(Jinja2Templates(directory=BASE_DIR / "templates"))


def _member_stats(db, member):
    assigned = (
        db.query(Task)
        .filter(Task.user_id == member.user_id, Task.assignee == member.name)
        .all()
    )
    return {
        "assigned": len(assigned),
        "open": sum(1 for task in assigned if task.status != "done"),
    }


def _brief_or_fallback(name, tasks):
    try:
        return ai_service.generate_onboarding_brief(name, tasks, [])
    except Exception:
        return (
            f"What we're building\n"
            f"We're building Solo as a focused operating system for solo founders. "
            f"The goal is to turn scattered work into clear tasks, plans, and handoffs.\n\n"
            f"Right now\n"
            f"- Review the active task list and pick the highest-leverage work.\n"
            f"- Keep updates short, specific, and tied to outcomes.\n"
            f"- Ask for context early when anything is unclear.\n\n"
            f"How we work\n"
            f"- We favor clarity over noise.\n"
            f"- We keep ownership explicit.\n"
            f"- We move in small, useful increments."
        )


@router.get("/team")
def team_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    members = (
        db.query(TeamMember)
        .filter(TeamMember.user_id == current_user.id)
        .order_by(TeamMember.invited_at.desc())
        .all()
    )
    stats = {member.id: _member_stats(db, member) for member in members}
    return templates.TemplateResponse(
        "team.html",
        {
            "request": request,
            "title": "Team - Solo",
            "members": members,
            "stats": stats,
            "current_user": current_user,
        },
    )


@router.post("/team/invite")
def invite_member(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    role: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    member = TeamMember(
        user_id=current_user.id,
        name=name.strip(),
        email=email.strip(),
        role=role,
        onboarding_brief=None,
    )
    db.add(member)
    db.commit()
    db.refresh(member)

    try:
        queue = get_queue()
        queue.enqueue(job_generate_onboarding_brief, member.id, current_user.id)
    except RedisError as exc:
        print(f"Warning: Redis unavailable, generating onboarding brief inline: {exc}")
        tasks = (
            db.query(Task)
            .filter(Task.user_id == current_user.id)
            .order_by(Task.created_at.desc())
            .all()
        )
        member.onboarding_brief = _brief_or_fallback(member.name, tasks)
        db.commit()
        db.refresh(member)

    response = templates.TemplateResponse(
        "team/partials/member_card.html",
        {
            "request": request,
            "member": member,
            "stat": _member_stats(db, member),
            "current_user": current_user,
        },
    )
    response.headers["HX-Trigger"] = "team-member-invited"
    return response


@router.get("/team/brief-status/{member_id}")
def brief_status(
    member_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    member = (
        db.query(TeamMember)
        .filter(TeamMember.id == member_id, TeamMember.user_id == current_user.id)
        .first()
    )
    if member is None:
        return JSONResponse(status_code=404, content={"brief_ready": False, "brief": None})
    return {"brief_ready": bool(member.onboarding_brief), "brief": member.onboarding_brief or None}


@router.get("/team/members/{member_id}/brief", response_class=PlainTextResponse)
def member_brief(
    member_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    member = (
        db.query(TeamMember)
        .filter(TeamMember.id == member_id, TeamMember.user_id == current_user.id)
        .first()
    )
    if member is None:
        return Response(status_code=404)
    return PlainTextResponse(member.onboarding_brief or "")


@router.post("/team/members/{member_id}/brief/regenerate")
def regenerate_brief(
    request: Request,
    member_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    member = (
        db.query(TeamMember)
        .filter(TeamMember.id == member_id, TeamMember.user_id == current_user.id)
        .first()
    )
    if member is None:
        return Response(status_code=404)

    tasks = (
        db.query(Task)
        .filter(Task.user_id == current_user.id)
        .order_by(Task.created_at.desc())
        .all()
    )
    member.onboarding_brief = _brief_or_fallback(member.name, tasks)
    db.commit()
    db.refresh(member)
    response = templates.TemplateResponse(
        "team/partials/brief.html",
        {"request": request, "member": member, "current_user": current_user},
    )
    response.headers["HX-Trigger"] = "brief-regenerated"
    return response
