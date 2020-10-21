from estoult import Query
from .base import assertSQL, User, Organisation


def test_query():
    s = "select * from users"
    q = Query(User).select()
    assertSQL(q, s)


def test_left_join():
    s = "select * from users left join organisations " \
        "on users.organisation_id = organisations.id"
    q = (
        Query(User)
        .select()
        .left_join(Organisation, on=[User.organisation_id, Organisation.id])
    )
    assertSQL(q, s)


def test_order_by():
    s = "select * from users order by 'users.name' desc, 'users.id' limit 10 offset 2"
    q = Query(User).select().order_by({User.name: "desc"}, User.id).limit(10, 2)
    assertSQL(q, s)
