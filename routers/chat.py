import json
from pathlib import Path
from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import SessionLocal, get_db
from models import DayPlan, Message, User
from routers.auth import require_auth
from services import ai_service, task_service
from template_helpers import configure_templates


router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent
templates = configure_templates(Jinja2Templates(directory=BASE_DIR / "templates"))


def _today_key():
    return date.today().isoformat()


def _last_messages(db, user_id, limit):
    messages = (
        db.query(Message)
        .filter(Message.user_id == user_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(messages))


def _open_tasks(db, user_id):
    return task_service.get_all_tasks(
        db, user_id, status="todo"
    ) + task_service.get_all_tasks(
        db, user_id, status="in_progress"
    )


def _today_plan_text(db, user_id):
    day_plan = (
        db.query(DayPlan)
        .filter(DayPlan.user_id == user_id, DayPlan.date == _today_key())
        .first()
    )
    if day_plan is None:
        return None
    return day_plan.ai_schedule


def _sse(payload):
    lines = str(payload).splitlines() or [""]
    return "".join(f"data: {line}\n" for line in lines) + "\n"


def _execute_tool(db, user_id, name, arguments):
    try:
        args = json.loads(arguments or "{}")
    except json.JSONDecodeError:
        return "I tried to update your workspace, but the tool arguments were invalid."

    if name == "create_task":
        task = task_service.create_task(
            db,
            user_id=user_id,
            title=args.get("title", "Untitled task"),
            priority=args.get("priority", "medium"),
            due_date=args.get("due_date") or None,
            project=args.get("project") or None,
        )
        return f"Task created: {task.title}"

    if name == "update_task_status":
        task = task_service.set_task_status(
            db,
            user_id=user_id,
            task_id=args.get("task_id"),
            status=args.get("status"),
        )
        if task is None:
            return "Task update failed: task not found."
        return f"Task updated: {task.title} is now {task.status.replace('_', ' ')}"

    return f"Tool not recognized: {name}"


@router.get("/chat")
def chat_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    messages = _last_messages(db, current_user.id, 40)
    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
            "title": "Chat - Solo",
            "messages": messages,
            "tasks": _open_tasks(db, current_user.id),
            "day_plan": _today_plan_text(db, current_user.id),
            "current_user": current_user,
        },
    )


@router.post("/chat/message")
def send_message(
    user_message: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    message = Message(user_id=current_user.id, role="user", content=user_message)
    db.add(message)
    db.commit()

    history = [
        {"role": item.role, "content": item.content}
        for item in _last_messages(db, current_user.id, 20)
        if item.role in {"user", "assistant"}
    ]
    tasks = _open_tasks(db, current_user.id)
    day_plan = _today_plan_text(db, current_user.id)
    user_id = current_user.id

    def event_stream():
        assistant_response = []
        tool_results = []
        stream_db = SessionLocal()
        try:
            try:
                for chunk in ai_service.stream_chat(history, tasks, day_plan):
                    marker = "__TOOL_CALL__:"
                    if marker in chunk:
                        before, tool_marker = chunk.split(marker, 1)
                        if before:
                            assistant_response.append(before)
                            yield _sse(before)

                        name, _, arguments = tool_marker.partition(":")
                        result = _execute_tool(stream_db, user_id, name.strip(), arguments.strip())
                        tool_results.append(result)
                        yield _sse(f"__TOOL_CALL__:{result}")
                    else:
                        assistant_response.append(chunk)
                        yield _sse(chunk)
            except Exception as exc:
                yield _sse(f"Sorry, I could not complete that: {exc}")

            final_content = "".join(assistant_response).strip()
            if not final_content and tool_results:
                final_content = "\n".join(tool_results)
            if final_content:
                stream_db.add(Message(user_id=user_id, role="assistant", content=final_content))
                stream_db.commit()
            yield _sse("[DONE]")
        finally:
            stream_db.close()

    return StreamingResponse(event_stream(), media_type="text/event-stream")
