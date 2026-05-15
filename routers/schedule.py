import json
import signal
from pathlib import Path
from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models import DayPlan, Task, User
from routers.auth import require_auth
from services import ai_service
from template_helpers import configure_templates


router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent
templates = configure_templates(Jinja2Templates(directory=BASE_DIR / "templates"))


def _today_key():
    return date.today().isoformat()


def _open_tasks(db, user_id):
    priority_rank = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
    tasks = (
        db.query(Task)
        .filter(Task.user_id == user_id, Task.status.in_(("todo", "in_progress")))
        .all()
    )
    return sorted(tasks, key=lambda task: (priority_rank.get(task.priority, 9), task.due_date or "9999-12-31"))


def _plan_payload(day_plan):
    if day_plan is None:
        return None, []

    plan = json.loads(day_plan.ai_schedule)
    questions = plan.get("reflection_questions", [])
    return plan, questions


def timeout_handler(signum, frame):
    raise TimeoutError("AI call timed out")


@router.get("/schedule")
def schedule_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    day_plan = (
        db.query(DayPlan)
        .filter(DayPlan.user_id == current_user.id, DayPlan.date == _today_key())
        .first()
    )
    plan, reflection_questions = _plan_payload(day_plan)
    return templates.TemplateResponse(
        "schedule.html",
        {
            "request": request,
            "title": "Schedule - Solo",
            "day_plan": day_plan,
            "plan": plan,
            "reflection_questions": reflection_questions,
            "tasks": _open_tasks(db, current_user.id),
            "current_user": current_user,
        },
    )


@router.post("/schedule/plan")
def create_plan(
    request: Request,
    brain_dump: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    tasks = _open_tasks(db, current_user.id)
    try:
        # SIGALRM only works on Linux and Mac. On Windows, use threading.Timer instead.
        supports_sigalrm = hasattr(signal, "SIGALRM")
        if supports_sigalrm:
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(25)
        try:
            plan = ai_service.generate_day_plan(brain_dump, tasks)
            reflection_questions = ai_service.generate_reflection_questions(json.dumps(plan))
        finally:
            if supports_sigalrm:
                signal.alarm(0)
    except TimeoutError:
        return templates.TemplateResponse(
            "schedule/partials/error.html",
            {
                "request": request,
                "message": "The AI is taking too long right now. Please try again in a moment.",
                "current_user": current_user,
            },
        )
    except Exception:
        return templates.TemplateResponse(
            "schedule/partials/error.html",
            {
                "request": request,
                "message": "Something went wrong generating your plan. Please try again.",
                "current_user": current_user,
            },
        )

    plan["reflection_questions"] = reflection_questions
    today = _today_key()
    day_plan = (
        db.query(DayPlan)
        .filter(DayPlan.user_id == current_user.id, DayPlan.date == today)
        .first()
    )

    if day_plan is None:
        day_plan = DayPlan(
            user_id=current_user.id,
            date=today,
            brain_dump=brain_dump,
            ai_schedule=json.dumps(plan),
        )
        db.add(day_plan)
    else:
        day_plan.brain_dump = brain_dump
        day_plan.ai_schedule = json.dumps(plan)

    db.commit()
    db.refresh(day_plan)
    return templates.TemplateResponse(
        "schedule/partials/plan.html",
        {
            "request": request,
            "day_plan": day_plan,
            "plan": plan,
            "reflection_questions": reflection_questions,
            "current_user": current_user,
        },
    )


@router.post("/schedule/reflect")
def save_reflection(
    request: Request,
    reflection: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    day_plan = (
        db.query(DayPlan)
        .filter(DayPlan.user_id == current_user.id, DayPlan.date == _today_key())
        .first()
    )
    if day_plan is None:
        return Response(status_code=404)

    day_plan.reflection = reflection
    db.commit()
    return templates.TemplateResponse(
        "schedule/partials/reflection_success.html",
        {"request": request, "current_user": current_user},
    )
