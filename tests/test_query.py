import pytest
from estoult import Query, QueryError, fn
from .base import assertSQL, User, Organisation, Data


def test_query():
    s = "select * from users"
    q = Query(User).select()
    assertSQL(q, s)


def test_query_specify():
    s = "select users.name from users"
    q = Query(User).select(User.name)
    assertSQL(q, s)


def test_left_join():
    s = (
        "select * from users left join organisations "
        "on users.organisation_id = organisations.id"
    )
    q = (
        Query(User)
        .select()
        .left_join(Organisation, on=[User.organisation_id, Organisation.id])
    )
    assertSQL(q, s)


def test_query_union():
    s = (
        "select * from users union select users.* from organisations "
        "left join users on users.organisation_id = organisations.id"
    )
    q = (
        Query(User)
        .select()
        .union(Organisation)
        .select(fn.wild(User))
        .left_join(User, on=[User.organisation_id, Organisation.id])
    )
    assertSQL(q, s)


def test_order_by():
    s = "select * from users order by users.name desc, users.id limit 10 offset 2"
    q = Query(User).select().order_by({User.name: "desc"}, User.id).limit(10, 2)
    assertSQL(q, s)


def test_wildcard_fail():
    with pytest.raises(QueryError):
        Query(Data).select().execute()


def test_wildcard_pass():
    Query(Data).select(Data.value).execute()


def test_wildcard_preload_fail():
    with pytest.raises(QueryError):
        Query(User).select().preload(User.data).execute()


def test_wildcard_preload_pass():
    Query(User).select().preload({User.data: [Data.value]}).execute()


def test_query_update():
    Query(User).update({"name": "Astolfo"}).where(User.name == "Charlemagne").execute()


def test_query_delete():
    Query(User).delete().where(User.name == "Charlemagne").execute()
