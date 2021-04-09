from .base import User


def test_insert():
    u = User.new()
    assert u["name"] == "default name"


def test_update():
    u = User.new()
    # Update with value
    u = User.update(u, {"name": "astolfo"})
    # Update with nothing
    u = User.update(u, {})
    assert u["name"] == "astolfo"
