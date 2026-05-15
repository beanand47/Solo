import json

from database import SessionLocal
from models import DayPlan, Task, TeamMember
from services.ai_service import generate_day_plan, generate_onboarding_brief


def job_generate_onboarding_brief(member_id: int, user_id: int):
    db = SessionLocal()
    try:
        member = (
            db.query(TeamMember)
            .filter(TeamMember.id == member_id, TeamMember.user_id == user_id)
            .first()
        )
        tasks = (
            db.query(Task)
            .filter(Task.user_id == user_id, Task.status != "done")
            .order_by(Task.created_at.desc())
            .limit(20)
            .all()
        )
        if not member:
            return
        brief = generate_onboarding_brief(member.name, tasks, [])
        member.onboarding_brief = brief
        db.commit()
    except Exception as e:
        print(f"Job failed job_generate_onboarding_brief: {e}")
    finally:
        db.close()


def job_generate_day_plan(day_plan_id: int, user_id: int, brain_dump: str):
    db = SessionLocal()
    try:
        plan = (
            db.query(DayPlan)
            .filter(DayPlan.id == day_plan_id, DayPlan.user_id == user_id)
            .first()
        )
        tasks = db.query(Task).filter(Task.user_id == user_id, Task.status != "done").all()
        if not plan:
            return
        result = generate_day_plan(brain_dump, tasks)
        plan.ai_schedule = json.dumps(result)
        db.commit()
    except Exception as e:
        print(f"Job failed job_generate_day_plan: {e}")
    finally:
        db.close()
