from estoult import Query
from .base import User, Organisation


def test_query():
    results = Query(User).select().execute()
    assert isinstance(results, list)


def test_left_join():
    results = (
        Query(User)
        .select()
        .left_join(Organisation, on=[User.organistaion_id, Organisation.id])
        .execute()
    )
    assert isinstance(results, list)


def test_order_by():
    results = (
        Query(User)
        .select()
        .order_by({User.name: "desc"}, User.id)
        .execute()
    )
    assert isinstance(results, list)
