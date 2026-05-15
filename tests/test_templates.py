def test_home_redirects_to_login(client):
    response = client.get("/")

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_root_head_probe_succeeds(client):
    response = client.head("/")

    assert response.status_code == 204


def test_dashboard_renders(authenticated_client):
    response = authenticated_client.get("/dashboard")

    assert response.status_code == 200
    assert "Solo" in response.text


def test_tasks_renders(authenticated_client):
    response = authenticated_client.get("/tasks")

    assert response.status_code == 200
    assert "Tasks" in response.text


def test_schedule_renders(authenticated_client):
    response = authenticated_client.get("/schedule")

    assert response.status_code == 200
    assert "Brain dump" in response.text


def test_chat_renders(authenticated_client):
    response = authenticated_client.get("/chat")

    assert response.status_code == 200
    assert "What is on your mind" in response.text


def test_team_renders(authenticated_client):
    response = authenticated_client.get("/team")

    assert response.status_code == 200
    assert "Team" in response.text


def test_login_renders(client):
    response = client.get("/login")

    assert response.status_code == 200
    assert "Welcome back" in response.text


def test_signup_renders(client):
    response = client.get("/signup")

    assert response.status_code == 200
    assert "Create your account" in response.text
