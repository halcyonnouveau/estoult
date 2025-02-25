import os
from hashlib import md5

from apocryphes.pool import PooledSQLiteDatabase
from estoult import Field, Query, Association

_sql_file = "estoult.test.db"
# Pytest is multithreded so we need a pool
db = PooledSQLiteDatabase(database=_sql_file)


class NoPK(db.Schema):
    """Table without primary key"""

    __tablename__ = "nopk"

    not_id = Field(int)


class Data(db.Schema):
    """For testing wildcard select."""

    __tablename__ = "data"

    _allow_wildcard_select = False

    id = Field(int, null=False)
    user_id = Field(int)
    value = Field(str)


class User(db.Schema):
    __tablename__ = "users"

    id = Field(int, null=False)
    organisation_id = Field(int, null=True)
    name = Field(str, null=False, default="default name")

    data = Association.has_many(Data, on=["id", "user_id"])

    @classmethod
    def new(cls, org_id=None, name=None):
        return cls.insert({cls.organisation_id: org_id, cls.name: name})

    @classmethod
    def get_by_name(cls, name):
        return Query(cls).get_or_none().where(cls.name == name).execute()


class Organisation(db.Schema):
    __tablename__ = "organisations"

    id = Field(int, null=False)
    name = Field(str, null=False)

    admin = Association.has_one("tests.base.Admin", on=["id", "organisation_id"])
    users = Association.has_many(User, on=["id", "organisation_id"])


class Admin(db.Schema):
    __tablename__ = "admins"

    id = Field(int, null=False)
    organisation_id = Field(int)
    user_id = Field(int)

    user = Association.has_one(User, on=["user_id", "id"])


def db_create():
    db.connect()

    db.sql(
        """
        create table if not exists nopk (
            not_id integer
        );
    """,
        (),
    )

    db.sql(
        """
        create table if not exists data (
            id integer primary key autoincrement not null,
            user_id integer,
            value varchar(256)

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

    db.sql("insert into organisations (name) values ('Astolfo Inc')", ())
    db.sql("insert into organisations (name) values ('Micrapple PTY LTD')", ())

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

    db.sql("insert into users (organisation_id, name) values (1, 'My Name')", ())
    db.sql("insert into users (organisation_id, name) values (2, 'Your Name')", ())

    db.sql(
        """
        create table if not exists admins (
            id integer primary key autoincrement not null,
            organisation_id integer,
            user_id integer

        );
    """,
        (),
    )

    db.sql("insert into admins (organisation_id, user_id) values (1, 1)", ())

    db.close()


def db_clean():
    if os.path.exists(_sql_file):
        os.unlink(_sql_file)


def assertSQL(query, sql):
    # String comparisons are stupid
    q = md5(str(query).encode("utf-8")).hexdigest()
    s = md5(sql.encode("utf-8")).hexdigest()
    assert q == s


def recurse_replace(row):
    for key in row.keys():
        if isinstance(row[key], list):
            for obj in row[key]:
                recurse_replace(obj)
        if isinstance(row[key], dict):
            recurse_replace(row[key])

        if key.endswith("id"):
            row[key] = None

    return row
