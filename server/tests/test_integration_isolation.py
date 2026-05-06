import uuid
from types import SimpleNamespace

import auth as auth_module
import pytest

import main as main_module
from models import APIKey
from tests.conftest import TEST_PASSWORD, create_test_user


class _FakeMemory:
    def __init__(self, collection_name: str, store: dict[str, list[dict]]):
        self.collection_name = collection_name
        self.store = store
        self.vector_store = SimpleNamespace(list=self._list)

    def add(self, messages, **kwargs):
        entry = {
            "id": str(uuid.uuid4()),
            "memory": messages[0]["content"] if messages else "",
            "user_id": kwargs.get("user_id"),
            "agent_id": kwargs.get("agent_id"),
            "run_id": kwargs.get("run_id"),
            "metadata": kwargs.get("metadata") or {},
        }
        self.store.setdefault(self.collection_name, []).append(entry)
        return {"results": [entry]}

    def search(self, query, **kwargs):
        items = list(self.store.get(self.collection_name, []))
        filters = kwargs.get("filters") or {}
        for key, value in filters.items():
            items = [item for item in items if item.get(key) == value]
        return {"results": items}

    def get_all(self, filters=None):
        items = list(self.store.get(self.collection_name, []))
        filters = filters or {}
        for key, value in filters.items():
            items = [item for item in items if item.get(key) == value]
        return {"results": items}

    def update(self, memory_id, data, metadata=None):
        return {"id": memory_id, "memory": data, "metadata": metadata or {}}

    def history(self, memory_id):
        return {"id": memory_id, "history": []}

    def get(self, memory_id):
        return {"id": memory_id}

    def delete(self, memory_id):
        return None

    def delete_all(self, **kwargs):
        return None

    def reset(self):
        self.store[self.collection_name] = []

    def _list(self, top_k=1000):
        rows = [
            SimpleNamespace(
                id=item["id"],
                payload={
                    "data": item.get("memory"),
                    "user_id": item.get("user_id"),
                    "agent_id": item.get("agent_id"),
                    "run_id": item.get("run_id"),
                },
            )
            for item in self.store.get(self.collection_name, [])[:top_k]
        ]
        return [rows]


@pytest.fixture()
def fake_memory_backend(monkeypatch):
    store: dict[str, list[dict]] = {}

    def _get_memory_for_project(collection_name: str):
        return _FakeMemory(collection_name=collection_name, store=store)

    monkeypatch.setattr(main_module, "get_memory_for_project", _get_memory_for_project)
    return store


def _api_key_headers(db_session, user_id, project_id=None, label="test-key"):
    full_key, prefix, key_hash = auth_module.generate_api_key()
    db_session.add(
        APIKey(
            key_prefix=prefix,
            key_hash=key_hash,
            label=label,
            created_by=user_id,
            project_id=uuid.UUID(project_id) if isinstance(project_id, str) else project_id,
        )
    )
    db_session.commit()
    return {"X-API-Key": full_key}


def _create_project(client, headers, name):
    response = client.post("/projects", json={"name": name}, headers=headers)
    assert response.status_code == 201
    return response.json()


def test_cross_project_memory_isolation(client, db_session, admin_user, fake_memory_backend):
    bootstrap_headers = _api_key_headers(db_session, admin_user.id)
    project_a = _create_project(client, bootstrap_headers, "Project A")
    project_b = _create_project(client, bootstrap_headers, "Project B")

    project_a_headers = _api_key_headers(db_session, admin_user.id, project_id=project_a["id"], label="proj-a")
    project_b_headers = _api_key_headers(db_session, admin_user.id, project_id=project_b["id"], label="proj-b")

    add_response = client.post(
        "/memories",
        json={"messages": [{"role": "user", "content": "Only project A memory"}], "user_id": "user-a"},
        headers=project_a_headers,
    )
    assert add_response.status_code == 200

    search_a = client.post("/search", json={"query": "project", "user_id": "user-a"}, headers=project_a_headers)
    assert search_a.status_code == 200
    assert len(search_a.json()["results"]) == 1

    search_b = client.post("/search", json={"query": "project", "user_id": "user-a"}, headers=project_b_headers)
    assert search_b.status_code == 200
    assert search_b.json()["results"] == []

    assert project_a["collection_name"] in fake_memory_backend
    assert project_b["collection_name"] not in fake_memory_backend or fake_memory_backend[project_b["collection_name"]] == []


def test_role_enforcement_reader_can_read_but_cannot_write(client, db_session, admin_user, fake_memory_backend):
    owner_headers = _api_key_headers(db_session, admin_user.id)
    project = _create_project(client, owner_headers, "Role Enforcement")

    reader = create_test_user(db_session, "reader-isolation@example.com", TEST_PASSWORD, role="member")
    add_member = client.post(
        f"/projects/{project['id']}/members",
        json={"email": reader.email, "role": "reader"},
        headers=owner_headers,
    )
    assert add_member.status_code == 201

    reader_headers = _api_key_headers(db_session, reader.id, project_id=project["id"], label="reader-key")

    read_memories = client.get("/memories", headers=reader_headers)
    assert read_memories.status_code == 200

    search_memories = client.post("/search", json={"query": "anything"}, headers=reader_headers)
    assert search_memories.status_code == 200

    create_memory = client.post(
        "/memories",
        json={"messages": [{"role": "user", "content": "blocked"}], "user_id": "reader-user"},
        headers=reader_headers,
    )
    assert create_memory.status_code == 403

    update_memory = client.put(
        "/memories/some-memory-id",
        json={"text": "updated"},
        headers=reader_headers,
    )
    assert update_memory.status_code == 403

    delete_memory = client.delete("/memories/some-memory-id", headers=reader_headers)
    assert delete_memory.status_code == 403

    delete_all = client.delete("/memories?user_id=reader-user", headers=reader_headers)
    assert delete_all.status_code == 403

    reset = client.post("/reset", headers=reader_headers)
    assert reset.status_code == 403


def test_api_key_without_project_uses_default_project(client, db_session, admin_user, fake_memory_backend):
    bootstrap_headers = _api_key_headers(db_session, admin_user.id)
    default_project = _create_project(client, bootstrap_headers, "Default Project")

    legacy_key_headers = _api_key_headers(db_session, admin_user.id, project_id=None, label="legacy-null-project")

    create_memory = client.post(
        "/memories",
        json={"messages": [{"role": "user", "content": "legacy key write"}], "user_id": "legacy-user"},
        headers=legacy_key_headers,
    )
    assert create_memory.status_code == 200

    response = client.post("/search", json={"query": "legacy", "user_id": "legacy-user"}, headers=legacy_key_headers)
    assert response.status_code == 200
    assert len(response.json()["results"]) == 1
    assert default_project["collection_name"] in fake_memory_backend


def test_admin_api_key_header_uses_default_project(
    client,
    db_session,
    admin_user,
    fake_memory_backend,
    monkeypatch,
):
    monkeypatch.setenv("ADMIN_API_KEY", "legacy-admin-api-key-test")
    monkeypatch.setattr(auth_module, "ADMIN_API_KEY", "legacy-admin-api-key-test")

    default_headers = _api_key_headers(db_session, admin_user.id)
    default_project = _create_project(client, default_headers, "Admin Key Default")

    response = client.post(
        "/memories",
        json={"messages": [{"role": "user", "content": "admin key write"}], "user_id": "admin-api-key-user"},
        headers={"X-API-Key": "legacy-admin-api-key-test"},
    )
    assert response.status_code == 200
    assert default_project["collection_name"] in fake_memory_backend


def test_auth_disabled_uses_default_project(
    client,
    db_session,
    admin_user,
    fake_memory_backend,
    monkeypatch,
):
    monkeypatch.setenv("AUTH_DISABLED", "true")
    monkeypatch.setattr(auth_module, "AUTH_DISABLED", True)

    default_headers = _api_key_headers(db_session, admin_user.id)
    default_project = _create_project(client, default_headers, "Auth Disabled Default")

    response = client.post(
        "/memories",
        json={"messages": [{"role": "user", "content": "auth disabled write"}], "user_id": "auth-disabled-user"},
    )
    assert response.status_code == 200

    read_back = client.get("/memories")
    assert read_back.status_code == 200
    assert default_project["collection_name"] in fake_memory_backend
