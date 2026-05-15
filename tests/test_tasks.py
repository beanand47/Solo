from models import Task, User
from routers.auth import hash_password


def _current_user(db):
    return db.query(User).filter(User.email == "test@example.com").first()


def test_create_task(authenticated_client, db):
    user = _current_user(db)
    response = authenticated_client.post(
        "/tasks",
        data={"title": "Write launch plan", "priority": "urgent"},
    )

    task = db.query(Task).filter(Task.title == "Write launch plan").first()
    assert response.status_code == 200
    assert task is not None
    assert task.user_id == user.id
    assert task.priority == "urgent"


def test_create_task_unauthenticated(client):
    response = client.post("/tasks", data={"title": "No auth", "priority": "medium"})

    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_get_tasks(authenticated_client, db):
    user = _current_user(db)
    for index in range(3):
        db.add(Task(user_id=user.id, title=f"Task {index}", priority="medium"))
    db.commit()

    response = authenticated_client.get("/tasks")

    assert response.status_code == 200
    assert "Task 0" in response.text
    assert "Task 1" in response.text
    assert "Task 2" in response.text


def test_tasks_scoped_to_user(authenticated_client, db):
    user = _current_user(db)
    other = User(name="Other User", email="other@example.com", password_hash=hash_password("otherpass123"))
    db.add(other)
    db.commit()
    db.refresh(other)
    db.add(Task(user_id=user.id, title="Visible task", priority="medium"))
    db.add(Task(user_id=other.id, title="Hidden task", priority="urgent"))
    db.commit()

    response = authenticated_client.get("/tasks")

    assert "Visible task" in response.text
    assert "Hidden task" not in response.text


def test_update_task_status(authenticated_client, db):
    user = _current_user(db)
    task = Task(user_id=user.id, title="Cycle status", priority="medium", status="todo")
    db.add(task)
    db.commit()
    db.refresh(task)

    response_one = authenticated_client.patch(f"/tasks/{task.id}/status")
    db.refresh(task)
    response_two = authenticated_client.patch(f"/tasks/{task.id}/status")
    db.refresh(task)

    assert response_one.status_code == 200
    assert "in progress" in response_one.text
    assert response_two.status_code == 200
    assert task.status == "done"


def test_delete_task(authenticated_client, db):
    user = _current_user(db)
    task = Task(user_id=user.id, title="Delete me", priority="medium")
    db.add(task)
    db.commit()
    db.refresh(task)

    response = authenticated_client.delete(f"/tasks/{task.id}")

    assert response.status_code == 200
    assert db.query(Task).filter(Task.id == task.id).first() is None


def test_delete_other_users_task(authenticated_client, db):
    other = User(name="Other User", email="other-delete@example.com", password_hash=hash_password("otherpass123"))
    db.add(other)
    db.commit()
    db.refresh(other)
    task = Task(user_id=other.id, title="Other task", priority="medium")
    db.add(task)
    db.commit()
    db.refresh(task)

    response = authenticated_client.delete(f"/tasks/{task.id}")

    assert response.status_code == 200
    assert db.query(Task).filter(Task.id == task.id).first() is not None


def test_task_filter_by_status(authenticated_client, db):
    user = _current_user(db)
    db.add(Task(user_id=user.id, title="Todo task", priority="medium", status="todo"))
    db.add(Task(user_id=user.id, title="Done task", priority="medium", status="done"))
    db.commit()

    response = authenticated_client.get("/tasks?status=todo")

    assert "Todo task" in response.text
    assert "Done task" not in response.text


def test_task_filter_by_priority(authenticated_client, db):
    user = _current_user(db)
    db.add(Task(user_id=user.id, title="Urgent task", priority="urgent"))
    db.add(Task(user_id=user.id, title="Low task", priority="low"))
    db.commit()

    response = authenticated_client.get("/tasks?priority=urgent")

    assert "Urgent task" in response.text
    assert "Low task" not in response.text
