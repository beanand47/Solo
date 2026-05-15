import json

from models import DayPlan, User


PLAN_FIXTURE = {
    "summary": "Test day summary",
    "time_blocks": [{"time": "9:00-10:00", "label": "Deep work", "category": "deep_work", "note": ""}],
    "top_3": ["Task one", "Task two", "Task three"],
    "avoid": "Checking email constantly",
}


def _current_user(db):
    return db.query(User).filter(User.email == "test@example.com").first()


def test_get_schedule_page(authenticated_client):
    response = authenticated_client.get("/schedule")

    assert response.status_code == 200
    assert "Brain dump" in response.text


def test_schedule_page_unauthenticated(client):
    response = client.get("/schedule")

    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_save_reflection(authenticated_client, db):
    user = _current_user(db)
    plan = DayPlan(user_id=user.id, date="2099-01-01", brain_dump="Dump", ai_schedule=json.dumps(PLAN_FIXTURE))
    db.add(plan)
    db.commit()

    import routers.schedule as schedule_router

    schedule_router._today_key = lambda: "2099-01-01"
    response = authenticated_client.post("/schedule/reflect", data={"reflection": "Good progress"})
    db.refresh(plan)

    assert response.status_code == 200
    assert plan.reflection == "Good progress"


def test_plan_generation_no_brain_dump(authenticated_client, monkeypatch):
    import routers.schedule as schedule_router

    monkeypatch.setattr(schedule_router.ai_service, "generate_day_plan", lambda brain_dump, tasks: (_ for _ in ()).throw(ValueError("empty")))

    response = authenticated_client.post("/schedule/plan", data={"brain_dump": ""})

    assert response.status_code == 200
    assert "Something went wrong" in response.text or "taking too long" in response.text


def test_plan_generation_with_mock(authenticated_client, db, monkeypatch):
    user = _current_user(db)
    import routers.schedule as schedule_router

    monkeypatch.setattr(schedule_router.ai_service, "generate_day_plan", lambda brain_dump, tasks: PLAN_FIXTURE.copy())
    monkeypatch.setattr(schedule_router.ai_service, "generate_reflection_questions", lambda day_plan: ["What worked?"])
    monkeypatch.setattr(schedule_router, "_today_key", lambda: "2099-01-02")

    response = authenticated_client.post("/schedule/plan", data={"brain_dump": "Plan my day"})
    day_plan = db.query(DayPlan).filter(DayPlan.user_id == user.id, DayPlan.date == "2099-01-02").first()

    assert response.status_code == 200
    assert day_plan is not None
    assert "Test day summary" in response.text
