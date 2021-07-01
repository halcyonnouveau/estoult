from .base import User, NoPK


def test_insert():
    u = User.new()
    assert u["name"] == "default name"


def test_insert_no_pk():
    row = NoPK.insert({"not_id": 69})
    assert row["not_id"] == 69


def test_update():
    u = User.new()
    # Update with value
    u = User.update(u, {"name": "astolfo"})
    # Update with nothing
    u = User.update(u, {})
    assert u["name"] == "astolfo"
