from estoult import Query, op
from .base import assertSQL, User


_query = Query(User).select(User.id)


def test_or():
    s = (
        "select users.id from users "
        "where ((users.name) = ('Astolfo')) or ((users.id) = (1))"
    )
    q = _query.copy().where(op.or_(User.name == "Astolfo", User.id == 1))
    assertSQL(q, s)


def test_and():
    s = (
        "select users.id from users "
        "where ((users.name) = ('Astolfo')) and ((users.id) = (1))"
    )
    q = _query.copy().where(op.and_(User.name == "Astolfo", User.id == 1))
    assertSQL(q, s)


def test_in():
    s = "select users.id from users where (users.id) in (select users.id from users)"
    q = _query.copy().where(op.in_(User.id, _query))
    assertSQL(q, s)


def test_like():
    s = "select users.id from users where (users.name) like ('%stolf%')"
    q = _query.copy().where(op.like(User.name, "%stolf%"))
    assertSQL(q, s)


def test_not():
    s = "select users.id from users where not (users.organisation_id)"
    q = _query.copy().where(op.not_(User.organisation_id))
    assertSQL(q, s)


def test_is_null():
    s = "select users.id from users where (users.organisation_id) is null"
    q = _query.copy().where(op.is_null(User.organisation_id))
    assertSQL(q, s)


def test_not_null():
    s = "select users.id from users where (users.organisation_id) is not null"
    q = _query.copy().where(op.not_null(User.organisation_id))
    assertSQL(q, s)


def test_sub():
    s = "select users.id from users where (users.id) > ((users.id) - (users.id))"
    q = _query.copy().where(User.id > (User.id - User.id))
    assertSQL(q, s)


def test_add():
    s = "select users.id from users where (users.id) > ((users.id) + (users.id))"
    q = _query.copy().where(User.id > (User.id + User.id))
    assertSQL(q, s)


def test_mul():
    s = "select users.id from users where (users.id) > ((users.id) * (users.id))"
    q = _query.copy().where(User.id > (User.id * User.id))
    assertSQL(q, s)


def test_div():
    s = "select users.id from users where (users.id) > ((users.id) / (users.id))"
    q = _query.copy().where(User.id > (User.id / User.id))
    assertSQL(q, s)


def test_mod():
    s = "select users.id from users where (users.id) > ((users.id) % (users.id))"
    q = _query.copy().where(User.id > (User.id % User.id))
    assertSQL(q, s)
