from estoult import Query, qf, fn
from .base import assertSQL, User


def test_count():
    s = "select count(users.id) from users"
    q = Query(User).select(fn.count(User.id))
    assertSQL(q, s)


def test_sum():
    s = "select sum(users.id) from users"
    q = Query(User).select(fn.sum(User.id))
    assertSQL(q, s)


def test_avg():
    s = "select avg(users.id) from users"
    q = Query(User).select(fn.avg(User.id))
    assertSQL(q, s)


def test_alias():
    s = "select sum(users.id) as sum from users order by sum"
    q = Query(User).select(fn.alias(fn.sum(User.id), "sum")).order_by(qf("sum"))
    assertSQL(q, s)
