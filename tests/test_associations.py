from estoult import Query
from .base import Organisation, Admin, User


def test_has_one_get():
    org = (
        Query(Organisation)
        .get()
        .preload({Organisation.admin: [{Admin.user: [User.name]}]})
        .execute()
    )

    assert org.get("admin") is not None
    assert org["admin"].get("user") is not None


def test_has_many_get():
    org = Query(Organisation).get().preload(Organisation.users).execute()
    assert len(org.get("users")) > 0


def test_has_one_select():
    Query(Organisation).select().preload(Organisation.admin).execute()
    assert True


def test_has_many_select():
    Query(Organisation).select().preload(Organisation.users).execute()
    assert True
