import os
from hashlib import md5

from apocryphan.pool import PooledSQLiteDatabase
from estoult import Field, Query

_sql_file = "estoult.test.db"
# Pytest is multithreded so we need a pool
db = PooledSQLiteDatabase(database=_sql_file)


class User(db.Schema):

    __tablename__ = "users"

    id = Field(int, "id", null=False)
    organisation_id = Field(int, "organisation_id", null=True)

    name = Field(str, "name", null=False)

    @classmethod
    def new(cls, org_id, name):
        return cls.insert({cls.organisation_id: org_id, cls.name: name})

    @classmethod
    def get_by_name(cls, name):
        return Query(cls).get_or_none().where(cls.name == name).execute()


class Organisation(db.Schema):

    __tablename__ = "organisations"

    id = Field(int, "id", null=False)
    name = Field(str, "name", null=False)


def db_create():
    db.connect()

    db.sql(
        """
        create table if not exists users (
            id integer primary key autoincrement not null,
            organisation_id integer null,
            name varchar(256) not null
        );
    """,
        (),
    )

    db.sql(
        """
        create table if not exists organisations (
            id integer primary key autoincrement not null,
            name varchar(256) not null
        );
    """,
        (),
    )

    db.close()


def db_clean():
    if os.path.exists(_sql_file):
        os.unlink(_sql_file)


def assertSQL(query, sql):
    # String comparisons are stupid
    q = md5(str(query).encode("utf-8")).hexdigest()
    s = md5(sql.encode("utf-8")).hexdigest()
    assert q == s
