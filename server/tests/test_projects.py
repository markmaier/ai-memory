import auth as auth_module
from models import APIKey


def _api_key_headers(db_session, user_id):
    full_key, prefix, key_hash = auth_module.generate_api_key()
    db_session.add(APIKey(key_prefix=prefix, key_hash=key_hash, label="test-key", created_by=user_id))
    db_session.commit()
    return {"X-API-Key": full_key}


def _create_project(client, headers, name="Project A", description="desc"):
    return client.post("/projects", json={"name": name, "description": description}, headers=headers)


def test_create_project_happy_path(client, db_session, admin_user):
    headers = _api_key_headers(db_session, admin_user.id)
    response = _create_project(client, headers, name="Acme")

    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "Acme"
    assert payload["description"] == "desc"
    assert payload["collection_name"].startswith("memories_")
    assert payload["role"] == "owner"

    details = client.get(f"/projects/{payload['id']}", headers=headers)
    assert details.status_code == 200
    members = details.json()["members"]
    assert len(members) == 1
    assert members[0]["role"] == "owner"
    assert members[0]["user_id"] == str(admin_user.id)


def test_create_project_missing_name_returns_422(client, db_session, admin_user):
    headers = _api_key_headers(db_session, admin_user.id)
    response = client.post("/projects", json={"description": "no name"}, headers=headers)
    assert response.status_code == 422


def test_list_projects_only_shows_users_projects(client, db_session, admin_user):
    my_headers = _api_key_headers(db_session, admin_user.id)
    _create_project(client, my_headers, name="Mine")

    outsider = create_test_user(db_session, "other@example.com", "password123", role="member")
    outsider_headers = _api_key_headers(db_session, outsider.id)
    _create_project(client, outsider_headers, name="Theirs")

    response = client.get("/projects", headers=my_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Mine"
    assert data[0]["role"] == "owner"


def test_get_project_member_vs_non_member(client, db_session, admin_user):
    owner_headers = _api_key_headers(db_session, admin_user.id)
    project = _create_project(client, owner_headers, name="Shared")
    project_id = project.json()["id"]

    owner_get = client.get(f"/projects/{project_id}", headers=owner_headers)
    assert owner_get.status_code == 200
    assert owner_get.json()["project"]["name"] == "Shared"
    assert len(owner_get.json()["members"]) == 1

    outsider = create_test_user(db_session, "outsider@example.com", "password123", role="member")
    outsider_headers = _api_key_headers(db_session, outsider.id)
    outsider_get = client.get(f"/projects/{project_id}", headers=outsider_headers)
    assert outsider_get.status_code == 403


def test_update_project_owner_vs_reader(client, db_session, admin_user):
    owner_headers = _api_key_headers(db_session, admin_user.id)
    project = _create_project(client, owner_headers, name="NeedsUpdate")
    project_id = project.json()["id"]

    reader = create_test_user(db_session, "reader@example.com", "password123", role="member")
    add_member = client.post(
        f"/projects/{project_id}/members",
        json={"email": reader.email, "role": "reader"},
        headers=owner_headers,
    )
    assert add_member.status_code == 201
    reader_headers = _api_key_headers(db_session, reader.id)

    owner_update = client.patch(
        f"/projects/{project_id}",
        json={"name": "Updated", "description": "new"},
        headers=owner_headers,
    )
    assert owner_update.status_code == 200
    assert owner_update.json()["name"] == "Updated"

    reader_update = client.patch(f"/projects/{project_id}", json={"name": "Nope"}, headers=reader_headers)
    assert reader_update.status_code == 403


def test_delete_project_owner_only(client, db_session, admin_user):
    owner_headers = _api_key_headers(db_session, admin_user.id)
    first_project = _create_project(client, owner_headers, name="First")
    second_project = _create_project(client, owner_headers, name="Second")
    second_id = second_project.json()["id"]

    reader = create_test_user(db_session, "reader2@example.com", "password123", role="member")
    add_reader = client.post(
        f"/projects/{second_id}/members",
        json={"email": reader.email, "role": "reader"},
        headers=owner_headers,
    )
    assert add_reader.status_code == 201
    reader_headers = _api_key_headers(db_session, reader.id)

    reader_delete = client.delete(f"/projects/{second_id}", headers=reader_headers)
    assert reader_delete.status_code == 403

    owner_delete = client.delete(f"/projects/{second_id}", headers=owner_headers)
    assert owner_delete.status_code == 200

    remaining = client.delete(f"/projects/{first_project.json()['id']}", headers=owner_headers)
    assert remaining.status_code == 400
    assert remaining.json()["detail"] == "Cannot delete the last project"


def create_test_user(db, email, password, role="admin"):
    from models import User

    user = User(
        name=email.split("@")[0],
        email=email,
        password_hash=auth_module.hash_password(password),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
