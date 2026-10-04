from book2skill.auth import create_user, authenticate_user, list_users


def test_auth_flow():
    users = []
    user = create_user(users, "alice@example.com", "secret123")
    assert user["email"] == "alice@example.com"
    assert "password" not in user
    assert "password_hash" in users[0]
    assert users[0]["password_hash"] != "secret123"

    authenticated = authenticate_user(users, "alice@example.com", "secret123")
    assert authenticated is not None
    assert authenticated["email"] == "alice@example.com"

    assert len(list_users(users)) == 1
    assert "password_hash" not in list_users(users)[0]
