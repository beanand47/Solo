from datetime import date, datetime, time, timedelta

from models import Task


STATUS_ORDER = ("todo", "in_progress", "done")


def _parse_due_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _sort_key(task):
    due = _parse_due_date(task.due_date)
    due_key = due or date.max
    priority_rank = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
    return due_key, priority_rank.get(task.priority, 9), task.created_at


def get_all_tasks(db, user_id, status=None, priority=None, assignee=None):
    query = db.query(Task).filter(Task.user_id == user_id)
    if status and status != "all":
        query = query.filter(Task.status == status)
    if priority and priority != "all":
        query = query.filter(Task.priority == priority)
    if assignee:
        query = query.filter(Task.assignee == assignee)
    return sorted(query.all(), key=_sort_key)


def create_task(db, user_id, title, priority="medium", due_date=None, project=None):
    task = Task(
        user_id=user_id,
        title=title.strip(),
        priority=priority or "medium",
        due_date=due_date or None,
        project=project.strip() if project else None,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def update_task_status(db, user_id, task_id):
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
    if task is None:
        return None

    current_index = STATUS_ORDER.index(task.status) if task.status in STATUS_ORDER else 0
    task.status = STATUS_ORDER[(current_index + 1) % len(STATUS_ORDER)]
    db.commit()
    db.refresh(task)
    return task


def set_task_status(db, user_id, task_id, status):
    if status not in STATUS_ORDER:
        return None

    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
    if task is None:
        return None

    task.status = status
    db.commit()
    db.refresh(task)
    return task


def assign_task(db, user_id, task_id, assignee):
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
    if task is None:
        return None

    task.assignee = assignee or None
    db.commit()
    db.refresh(task)
    return task


def delete_task(db, user_id, task_id):
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
    if task is None:
        return None
    db.delete(task)
    db.commit()
    return task


def get_tasks_summary(db, user_id):
    tasks = db.query(Task).filter(Task.user_id == user_id).all()
    today = date.today()
    week_start = datetime.combine(today - timedelta(days=today.weekday()), time.min)

    return {
        "due_today": sum(
            1 for task in tasks if _parse_due_date(task.due_date) == today and task.status != "done"
        ),
        "overdue": sum(
            1
            for task in tasks
            if (due := _parse_due_date(task.due_date)) and due < today and task.status != "done"
        ),
        "in_progress": sum(1 for task in tasks if task.status == "in_progress"),
        "done_this_week": sum(
            1 for task in tasks if task.status == "done" and task.created_at >= week_start
        ),
    }
