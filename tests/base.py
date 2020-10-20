import os

from apocryphan.pool import PooledSQLiteDatabase
from estoult import Field, Query

_sql_file = "estoult.test.db"
# Pytest is multithreded so we need a pool
db = PooledSQLiteDatabase(database=_sql_file)


class User(db.Schema):

    __tablename__ = "users"

    id = Field(int, "id", null=False)
    organistaion_id = Field(int, "organistaion_id", null=True)

    name = Field(str, "name", null=False)

    @classmethod
    def new(cls, org_id, name):
        return cls.insert({cls.organistaion_id: org_id, cls.name: name})

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
            organistaion_id integer null,
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
