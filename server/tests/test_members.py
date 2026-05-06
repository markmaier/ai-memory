import auth as auth_module
from models import APIKey


def _api_key_headers(db_session, user_id):
    full_key, prefix, key_hash = auth_module.generate_api_key()
    db_session.add(APIKey(key_prefix=prefix, key_hash=key_hash, label="test-key", created_by=user_id))
    db_session.commit()
    return {"X-API-Key": full_key}


def _create_project(client, headers, name="Members Project"):
    response = client.post("/projects", json={"name": name}, headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


def test_add_member_happy_duplicate_and_missing_user(client, db_session, admin_user):
    owner_headers = _api_key_headers(db_session, admin_user.id)
    project_id = _create_project(client, owner_headers)
    invitee = create_test_user(db_session, "invitee@example.com", "password123", role="member")

    add_response = client.post(
        f"/projects/{project_id}/members",
        json={"email": invitee.email, "role": "reader"},
        headers=owner_headers,
    )
    assert add_response.status_code == 201
    assert add_response.json()["user_email"] == invitee.email
    assert add_response.json()["role"] == "reader"

    duplicate = client.post(
        f"/projects/{project_id}/members",
        json={"email": invitee.email, "role": "owner"},
        headers=owner_headers,
    )
    assert duplicate.status_code == 409

    missing = client.post(
        f"/projects/{project_id}/members",
        json={"email": "missing@example.com", "role": "reader"},
        headers=owner_headers,
    )
    assert missing.status_code == 404


def test_list_members(client, db_session, admin_user):
    owner_headers = _api_key_headers(db_session, admin_user.id)
    project_id = _create_project(client, owner_headers)
    member = create_test_user(db_session, "listme@example.com", "password123", role="member")

    add = client.post(
        f"/projects/{project_id}/members",
        json={"email": member.email, "role": "reader"},
        headers=owner_headers,
    )
    assert add.status_code == 201

    response = client.get(f"/projects/{project_id}/members", headers=owner_headers)
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    emails = {row["user_email"] for row in payload}
    assert member.email in emails


def test_update_role_and_last_owner_protection(client, db_session, admin_user):
    owner_headers = _api_key_headers(db_session, admin_user.id)
    project_id = _create_project(client, owner_headers)
    member = create_test_user(db_session, "rolechange@example.com", "password123", role="member")

    add = client.post(
        f"/projects/{project_id}/members",
        json={"email": member.email, "role": "owner"},
        headers=owner_headers,
    )
    assert add.status_code == 201
    added_member_id = add.json()["id"]

    demote_added_owner = client.patch(
        f"/projects/{project_id}/members/{added_member_id}",
        json={"role": "reader"},
        headers=owner_headers,
    )
    assert demote_added_owner.status_code == 200

    current_members = client.get(f"/projects/{project_id}/members", headers=owner_headers).json()
    last_owner = next(item for item in current_members if item["role"] == "owner")

    block_last_owner_demote = client.patch(
        f"/projects/{project_id}/members/{last_owner['id']}",
        json={"role": "reader"},
        headers=owner_headers,
    )
    assert block_last_owner_demote.status_code == 400
    assert block_last_owner_demote.json()["detail"] == "Cannot remove the last owner"


def test_remove_member_happy_and_last_owner_protection(client, db_session, admin_user):
    owner_headers = _api_key_headers(db_session, admin_user.id)
    project_id = _create_project(client, owner_headers)
    removable = create_test_user(db_session, "removable@example.com", "password123", role="member")

    add_reader = client.post(
        f"/projects/{project_id}/members",
        json={"email": removable.email, "role": "reader"},
        headers=owner_headers,
    )
    assert add_reader.status_code == 201
    reader_member_id = add_reader.json()["id"]

    remove_reader = client.delete(f"/projects/{project_id}/members/{reader_member_id}", headers=owner_headers)
    assert remove_reader.status_code == 200

    members = client.get(f"/projects/{project_id}/members", headers=owner_headers).json()
    owner_member = next(item for item in members if item["role"] == "owner")
    remove_last_owner = client.delete(f"/projects/{project_id}/members/{owner_member['id']}", headers=owner_headers)
    assert remove_last_owner.status_code == 400
    assert remove_last_owner.json()["detail"] == "Cannot remove the last owner"


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
