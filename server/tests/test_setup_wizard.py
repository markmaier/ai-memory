import auth as auth_module
from models import APIKey, Organization, Project, ProjectMember


TEST_PASSWORD = "password123"


def _register(client, email="admin@example.com", name="Admin", password=TEST_PASSWORD):
    return client.post("/auth/register", json={"name": name, "email": email, "password": password})


def _api_key_headers(db_session, user_id):
    full_key, prefix, key_hash = auth_module.generate_api_key()
    db_session.add(APIKey(key_prefix=prefix, key_hash=key_hash, label="test-key", created_by=user_id))
    db_session.commit()
    return {"X-API-Key": full_key}


def test_first_registration_creates_org_project_and_membership(client, db_session):
    resp = _register(client, email="first@example.com", name="First Admin")
    assert resp.status_code == 200

    orgs = db_session.query(Organization).all()
    assert len(orgs) == 1
    assert orgs[0].name == "My Organization"

    projects = db_session.query(Project).all()
    assert len(projects) == 1
    assert projects[0].name == "Default"
    assert projects[0].collection_name == "memories"
    assert projects[0].org_id == orgs[0].id

    members = db_session.query(ProjectMember).all()
    assert len(members) == 1
    assert members[0].project_id == projects[0].id
    assert members[0].role == "owner"


def test_first_registration_project_visible_via_api(client, db_session):
    resp = _register(client, email="first@example.com", name="First Admin")
    assert resp.status_code == 200

    from models import User

    user = db_session.query(User).filter_by(email="first@example.com").one()
    headers = _api_key_headers(db_session, user.id)

    projects_resp = client.get("/projects", headers=headers)
    assert projects_resp.status_code == 200
    data = projects_resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Default"
    assert data[0]["role"] == "owner"


def test_second_registration_does_not_create_org_or_project(client, db_session):
    _register(client, email="first@example.com", name="First Admin")

    resp = _register(client, email="second@example.com", name="Second User")
    assert resp.status_code == 200

    orgs = db_session.query(Organization).all()
    assert len(orgs) == 1

    projects = db_session.query(Project).all()
    assert len(projects) == 1

    members = db_session.query(ProjectMember).all()
    assert len(members) == 1


def test_first_registration_uses_env_collection_name(client, db_session, monkeypatch):
    monkeypatch.setenv("POSTGRES_COLLECTION_NAME", "custom_memories")

    resp = _register(client, email="first@example.com", name="First Admin")
    assert resp.status_code == 200

    project = db_session.query(Project).one()
    assert project.collection_name == "custom_memories"
