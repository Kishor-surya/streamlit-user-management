def test_init_db_starts_empty(temp_db):
    assert temp_db.get_all_users() == []


def test_add_and_get_user(temp_db):
    temp_db.add_user("Alice Smith", "alice@example.com", "1234567890", 30, "Engineering", "Manager")

    users = temp_db.get_all_users()
    assert len(users) == 1

    user = users[0]
    assert user["full_name"] == "Alice Smith"
    assert user["email"] == "alice@example.com"
    assert user["status"] == "Active"
    assert user["created_at"] == user["updated_at"]

    fetched = temp_db.get_user(user["id"])
    assert fetched["email"] == "alice@example.com"


def test_get_user_missing_returns_none(temp_db):
    assert temp_db.get_user(999) is None


def test_update_user(temp_db):
    temp_db.add_user("Bob Jones", "bob@example.com", "5551234", 40, "Sales", "Employee")
    user = temp_db.get_all_users()[0]

    temp_db.update_user(
        user["id"], "Bob J. Jones", "bob.j@example.com", "5559999",
        41, "Sales", "Manager", "Inactive",
    )

    updated = temp_db.get_user(user["id"])
    assert updated["full_name"] == "Bob J. Jones"
    assert updated["email"] == "bob.j@example.com"
    assert updated["age"] == 41
    assert updated["role"] == "Manager"
    assert updated["status"] == "Inactive"


def test_delete_user(temp_db):
    temp_db.add_user("Carol White", "carol@example.com", "", 22, "HR", "Intern")
    user = temp_db.get_all_users()[0]

    temp_db.delete_user(user["id"])

    assert temp_db.get_all_users() == []
    assert temp_db.get_user(user["id"]) is None


def test_email_exists(temp_db):
    temp_db.add_user("Dan Green", "dan@example.com", "", 28, "Finance", "Employee")

    assert temp_db.email_exists("dan@example.com") is True
    assert temp_db.email_exists("nobody@example.com") is False


def test_email_exists_excludes_given_id(temp_db):
    temp_db.add_user("Dan Green", "dan@example.com", "", 28, "Finance", "Employee")
    user = temp_db.get_all_users()[0]

    assert temp_db.email_exists("dan@example.com", exclude_id=user["id"]) is False


def test_get_all_users_orders_newest_first(temp_db):
    temp_db.add_user("First", "first@example.com", "", 20, "Engineering", "Employee")
    temp_db.add_user("Second", "second@example.com", "", 21, "Engineering", "Employee")

    users = temp_db.get_all_users()

    assert users[0]["full_name"] == "Second"
    assert users[1]["full_name"] == "First"
