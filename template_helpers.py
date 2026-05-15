from datetime import date, datetime, timedelta

from markupsafe import Markup


def parse_due_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def due_date_label(value):
    due = parse_due_date(value)
    if not due:
        return Markup("&mdash;")

    today = date.today()
    if due == today:
        return "Today"
    if due == today + timedelta(days=1):
        return "Tomorrow"
    return due.strftime("%b %d").replace(" 0", " ")


def is_overdue(value, status="todo"):
    due = parse_due_date(value)
    return bool(due and due < date.today() and status != "done")


def configure_templates(templates):
    templates.env.filters["due_date_label"] = due_date_label
    templates.env.globals["is_overdue"] = is_overdue
    return templates
