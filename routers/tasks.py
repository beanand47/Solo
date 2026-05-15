from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session
from starlette.templating import Jinja2Templates

from database import get_db
from models import TeamMember, User
from routers.auth import require_auth
from services import task_service
from template_helpers import configure_templates


router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent
templates = configure_templates(Jinja2Templates(directory=BASE_DIR / "templates"))


@router.get("/tasks")
def tasks_page(
    request: Request,
    status: str = "all",
    priority: str = "all",
    assignee: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    tasks = task_service.get_all_tasks(
        db,
        current_user.id,
        status=status,
        priority=priority,
        assignee=assignee,
    )
    members = (
        db.query(TeamMember)
        .filter(TeamMember.user_id == current_user.id)
        .order_by(TeamMember.name)
        .all()
    )
    return templates.TemplateResponse(
        "tasks.html",
        {
            "request": request,
            "title": "Tasks - Solo",
            "tasks": tasks,
            "members": members,
            "has_team": bool(members),
            "selected_status": status,
            "selected_priority": priority,
            "selected_assignee": assignee,
            "current_user": current_user,
        },
    )


@router.post("/tasks")
def create_task(
    request: Request,
    title: str = Form(...),
    priority: str = Form("medium"),
    due_date: str = Form(None),
    project: str = Form(None),
    source: str = Form("tasks"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    task = task_service.create_task(
        db,
        current_user.id,
        title=title,
        priority=priority,
        due_date=due_date,
        project=project,
    )
    if source == "dashboard":
        response = templates.TemplateResponse(
            "dashboard/partials/quick_add_success.html",
            {"request": request, "task": task, "current_user": current_user},
        )
        response.headers["HX-Trigger"] = "task-created"
        return response
    members = (
        db.query(TeamMember)
        .filter(TeamMember.user_id == current_user.id)
        .order_by(TeamMember.name)
        .all()
    )
    response = templates.TemplateResponse(
        "tasks/partials/row.html",
        {
            "request": request,
            "task": task,
            "members": members,
            "has_team": bool(members),
            "current_user": current_user,
        },
    )
    response.headers["HX-Trigger"] = "task-created"
    return response


@router.patch("/tasks/{task_id}/status")
def update_task_status(
    request: Request,
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    task = task_service.update_task_status(db, current_user.id, task_id)
    if task is None:
        return Response(status_code=404)
    response = templates.TemplateResponse(
        "tasks/partials/status_badge.html",
        {"request": request, "task": task, "current_user": current_user},
    )
    response.headers["HX-Trigger"] = "task-updated"
    return response


@router.patch("/tasks/{task_id}/assign")
def assign_task(
    request: Request,
    task_id: int,
    assignee: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    task = task_service.assign_task(db, current_user.id, task_id, assignee)
    if task is None:
        return Response(status_code=404)
    members = (
        db.query(TeamMember)
        .filter(TeamMember.user_id == current_user.id)
        .order_by(TeamMember.name)
        .all()
    )
    response = templates.TemplateResponse(
        "tasks/partials/row.html",
        {
            "request": request,
            "task": task,
            "members": members,
            "has_team": bool(members),
            "current_user": current_user,
        },
    )
    response.headers["HX-Trigger"] = "task-updated"
    return response


@router.delete("/tasks/{task_id}", response_class=HTMLResponse)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    task_service.delete_task(db, current_user.id, task_id)
    return Response(status_code=200, headers={"HX-Trigger": "task-deleted"})
