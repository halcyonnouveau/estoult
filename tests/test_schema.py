from .base import User
from estoult import Query


def test_insert():
    u_id = User.new()
    u = Query(User).get().where(User.id == u_id).execute()
    assert u["name"] == "default name"


def test_update():
    u_id = User.new()
    # Update with value
    User.update_by_pk(u_id, {"name": "astolfo"})
    # Update with nothing
    User.update_by_pk(u_id, {})
    u = Query(User).get().where(User.id == u_id).execute()
    assert u["name"] == "astolfo"
