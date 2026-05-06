import uuid

import pytest

from tests.conftest import TEST_PASSWORD, create_test_user, get_auth_headers
from models import Organization, Project, ProjectMember


@pytest.fixture()
def owner_user(db_session):
    return create_test_user(db_session, "owner@example.com", TEST_PASSWORD)


@pytest.fixture()
def reader_user(db_session):
    return create_test_user(db_session, "reader@example.com", TEST_PASSWORD)


@pytest.fixture()
def outsider_user(db_session):
    return create_test_user(db_session, "outsider@example.com", TEST_PASSWORD)


@pytest.fixture()
def project(db_session, owner_user, reader_user):
    org = Organization(name="Test Org")
    db_session.add(org)
    db_session.flush()

    proj = Project(org_id=org.id, name="Test Project", collection_name="test_coll")
    db_session.add(proj)
    db_session.flush()

    db_session.add(ProjectMember(project_id=proj.id, user_id=owner_user.id, role="owner"))
    db_session.add(ProjectMember(project_id=proj.id, user_id=reader_user.id, role="reader"))
    db_session.commit()
    db_session.refresh(proj)
    return proj


@pytest.fixture()
def owner_headers(client, owner_user):
    return get_auth_headers(client, owner_user.email, TEST_PASSWORD)


@pytest.fixture()
def reader_headers(client, reader_user):
    return get_auth_headers(client, reader_user.email, TEST_PASSWORD)


@pytest.fixture()
def outsider_headers(client, outsider_user):
    return get_auth_headers(client, outsider_user.email, TEST_PASSWORD)


class TestCreateKeyWithProject:
    def test_create_key_as_owner(self, client, owner_headers, project):
        resp = client.post(
            "/api-keys",
            json={"label": "my-key", "project_id": str(project.id)},
            headers=owner_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["label"] == "my-key"
        assert data["key"].startswith(data["key_prefix"])

    def test_create_key_as_reader_returns_403(self, client, reader_headers, project):
        resp = client.post(
            "/api-keys",
            json={"label": "my-key", "project_id": str(project.id)},
            headers=reader_headers,
        )
        assert resp.status_code == 403
        assert "owner" in resp.json()["detail"].lower()

    def test_create_key_as_non_member_returns_403(self, client, outsider_headers, project):
        resp = client.post(
            "/api-keys",
            json={"label": "my-key", "project_id": str(project.id)},
            headers=outsider_headers,
        )
        assert resp.status_code == 403

    def test_create_key_missing_project_id_returns_422(self, client, owner_headers):
        resp = client.post(
            "/api-keys",
            json={"label": "my-key"},
            headers=owner_headers,
        )
        assert resp.status_code == 422


class TestListKeysWithProject:
    def test_list_keys_filtered_by_project(self, client, owner_headers, project, db_session):
        client.post(
            "/api-keys",
            json={"label": "proj-key", "project_id": str(project.id)},
            headers=owner_headers,
        )

        resp = client.get(f"/api-keys?project_id={project.id}", headers=owner_headers)
        assert resp.status_code == 200
        keys = resp.json()
        assert len(keys) == 1
        assert keys[0]["label"] == "proj-key"
        assert keys[0]["project_id"] == str(project.id)
        assert keys[0]["project_name"] == "Test Project"

    def test_list_keys_no_filter_returns_all(self, client, owner_headers, project):
        client.post(
            "/api-keys",
            json={"label": "proj-key", "project_id": str(project.id)},
            headers=owner_headers,
        )

        resp = client.get("/api-keys", headers=owner_headers)
        assert resp.status_code == 200
        keys = resp.json()
        assert len(keys) >= 1

    def test_list_keys_filter_nonexistent_project_returns_empty(self, client, owner_headers, project):
        client.post(
            "/api-keys",
            json={"label": "proj-key", "project_id": str(project.id)},
            headers=owner_headers,
        )

        fake_id = str(uuid.uuid4())
        resp = client.get(f"/api-keys?project_id={fake_id}", headers=owner_headers)
        assert resp.status_code == 200
        assert resp.json() == []


class TestApiKeyResolvesProject:
    def test_key_stores_project_id_on_request_state(self, client, owner_headers, project):
        create_resp = client.post(
            "/api-keys",
            json={"label": "state-key", "project_id": str(project.id)},
            headers=owner_headers,
        )
        assert create_resp.status_code == 201
        api_key_value = create_resp.json()["key"]

        resp = client.get("/api-keys", headers={"X-API-Key": api_key_value})
        assert resp.status_code == 200
