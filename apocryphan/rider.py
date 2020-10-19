#!/usr/bin/env python
r"""
``rider`` is a simple tool to help manage database migrations using the existing
Estoult database object.

Start by creating a ``rider.py`` file to tell ``rider`` about your database object.

.. code-block:: python

    from src.schemas.base import db

    # Export the db
    # Not actually needed, but my linter screams at me otherwise
    db = db

    # Default config
    config = {
        # Path where migrations are stored
        "source": "./migrations",
        # Table name for migrations
        "table_name": "_rider_migrations",
        # Table name of migration logs
        "log_name": "_rider_logs",
    }

Create a new migration with a description.

.. code-block:: bash

    rider create -m "add contacts table"

This will create the bellow scaffold file in which you can add your migration steps too.

.. code-block:: bash

    '''
    create table
    '''

    from apocryphan.rider import step

    __depends__ = {"1602721237-add-pg-extensions"}

    steps = [
        step("")
    ]

The ``step`` function takes 3 arguments:

* ``migreate``: a SQL query or function to apply the migration step.
* ``rollback``: (optional) a SQL query or function to rollback the migration step.
* ``ignore_errors``: (optional, one of "migrate", "rollback" or "all") causes rider to
    ignore database errors in either migrate, rollback, or both stages.

.. code-block:: bash

    steps = [
        # Steps with sql queries
        step(
            migrate="create table contacts (id int not null);",
            rollback="drop table contacts;",
            ignore_errors="all",
        ),

        # Arguments don't need to be kwargs
        step("alter table contacts add column name varchar(256) not null")
    ]

You can supply a function to ``migrate`` or ``rolllback``. Each function takes your db
object.

.. code-block:: bash

    def migrate_step(db):
        db.sql(...)

    def rollback_step(db):
        db.sql(...)

    steps = [
        step(migrate_step, rollback_step),
    ]

View migrations:

.. code-block:: bash

    rider migrations

Apply migrations:

.. code-block:: bash

    rider migrate
"""

import os
import re
import glob
import types
import sys
import argparse
import time
import uuid
import ast
import getpass
import socket

from datetime import datetime
from pathlib import Path
from collections import namedtuple

from estoult import Query, Schema, Field

__all__ = ["Rider", "step"]


class RiderError(Exception):
    pass


class MigrateError(RiderError):
    pass


class RollbackError(RiderError):
    pass


SCAFFOLD = """
\"""
%s
\"""

from apocryphan.rider import step

__depends__ = {"%s"}

steps = [
    step("")
]
""".strip()

step = namedtuple("Step", ["migrate", "rollback", "ignore_errors"])
step.__new__.__defaults__ = (None, None, None)


def _read_migration(path):
    with open(path, "r") as f:
        tree = ast.parse(f.read())

    mod = {
        "id": Path(path).name.replace(".py", ""),
        "path": path,
        "doc": ast.get_docstring(tree).replace("\n", " "),
    }

    exec(open(str(path)).read(), mod)
    return mod


def _print_table(rows):
    if len(rows) > 1:
        headers = rows[0]._fields
        lens = []

        for i in range(len(rows[0])):
            lens.append(
                len(max([x[i] for x in rows] + [headers[i]], key=lambda x: len(str(x))))
            )

        formats = []
        hformats = []

        for i in range(len(rows[0])):
            if isinstance(rows[0][i], int):
                formats.append("%%%dd" % lens[i])
            else:
                formats.append("%%-%ds" % lens[i])
            hformats.append("%%-%ds" % lens[i])

        pattern = " | ".join(formats)
        hpattern = " | ".join(hformats)
        separator = "-+-".join(["-" * n for n in lens])

        print(hpattern % tuple(headers))
        print(separator)

        for line in rows:
            print(pattern % tuple(t for t in line))

    elif len(rows) == 1:
        row = rows[0]
        hwidth = len(max(row._fields, key=lambda x: len(x)))

        for i in range(len(row)):
            print("%*s = %s" % (hwidth, row._fields[i], row[i]))


def _atomic(func):
    def wrapper(self, *args, **kwargs):
        self.db.connect()

        with self.db.atomic():
            func(self, *args, **kwargs)

        self.db.close()

    return wrapper


class RiderLog(Schema):
    id = Field(str, "id", null=False, primary_key=True)
    migration = Field(str, "migration", null=False)
    operation = Field(str, "operation", null=False)
    username = Field(str, "username", null=False)
    hostname = Field(str, "hostname", null=False)
    time = Field(str, "time", null=False)

    @classmethod
    def new(cls, migration, operation):
        return cls.insert(
            {
                "id": str(uuid.uuid4()),
                "migration": migration,
                "operation": "apply",
                "username": getpass.getuser(),
                "hostname": socket.gethostname(),
                "time": datetime.now(),
            }
        )


class RiderMigration(Schema):
    migration = Field(str, "migration", null=False, primary_key=True)
    applied_at = Field(str, "applied_at")

    @classmethod
    def new(cls, migration):
        return cls.insert({"migration": migration, "applied_at": datetime.now()})


class Rider:

    default_config = {
        "source": "./migrations",
        "table_name": "_rider_migrations",
        "log_name": "_rider_logs",
    }

    def __init__(self, db, config={}):
        self.db = db
        self.db.autoconnect = False

        self.config = {**Rider.default_config, **config}
        self._mig_path = Path(os.getcwd()) / self.config["source"]

        RiderLog._database_ = db
        RiderMigration._database_ = db
        RiderLog.__tablename__ = self.config["log_name"]
        RiderMigration.__tablename__ = self.config["table_name"]

        self.init_tables()

    @_atomic
    def init_tables(self):
        self.db.sql(
            """
            create table if not exists %s (
                id varchar(256) primary key not null,
                migration varchar(256) not null,
                operation varchar(56) not null,
                username varchar(128),
                hostname varchar(128),
                time timestamp
            );
        """
            % (self.config["log_name"]),
            (),
        )

        self.db.sql(
            """
            create table if not exists %s (
                migration varchar(256) primary key not null,
                applied_at timestamp
            );
        """
            % (self.config["table_name"]),
            (),
        )

    def _get_migrations(self):
        pattern = r".+\d+-.+\.py"
        globs = sorted(glob.glob(str(self._mig_path) + "/*"))
        files = filter(re.compile(pattern).match, globs)

        return [_read_migration(f) for f in files]

    def create(self, args):
        name = args.message

        filename = f"{int(time.time())}-{'-'.join(name.split(' ')).lower()}.py"
        self._mig_path.mkdir(parents=True, exist_ok=True)

        path = str(self._mig_path / filename)
        migs = self._get_migrations()

        if len(migs) > 0:
            last_migration = migs[-1]["id"]
        else:
            last_migration = ""

        script = SCAFFOLD % (name, last_migration)

        with open(path, "w") as f:
            f.write(script)

        print(f"Created migration scaffold in {path}")

    def _applied(self, id):
        return (
            Query(RiderMigration)
            .get_or_none()
            .where(RiderMigration.migration == id)
            .execute()
            or {}
        ).get("applied_at")

    @_atomic
    def migrate(self, _args):
        migs = self._get_migrations()

        applied = [
            s["migration"]
            for s in self.db.select(
                "select * from %s" % (self.config["table_name"]), ()
            )
        ]

        for m in migs:
            if m["id"] in applied:
                continue

            depends = m["__depends__"]

            if depends:
                name = depends.pop()

                if self._applied(name) is None:
                    raise Exception(
                        f"""
                        {m['id']} depends on {name} but is not applied.
                        """.strip()
                    )

            steps = m["steps"]

            for step in steps:
                if step.migrate is None:
                    raise MigrateError("Migration step is empty")

                try:
                    if isinstance(step.migrate, types.FunctionType):
                        step.migrate(self.db)
                    else:
                        self.db.sql(step.migrate, ())
                except Exception as e:
                    if step.ignore_errors not in ["migrate", "all"]:
                        raise e

            RiderMigration.new(m["id"])
            RiderLog.new(m["id"], "apply")

            print(f"Applied migration: {m['id']}")

    @_atomic
    def migrations(self, _args):
        migs = self._get_migrations()

        Row = namedtuple("Row", ["index", "message", "applied"])
        rows = []

        for idx, m in enumerate(migs):
            applied = self._applied(m["id"])

            if applied:
                applied = applied.strftime("%Y-%m-%d %H:%M:%S.%f")

            rows.append(Row(idx, m["doc"], str(applied)))

        _print_table(rows)

    @_atomic
    def rollback(self, args):
        migs = self._get_migrations()

        roll_to = migs[int(args.index) :]
        roll_to.reverse()

        for roll in roll_to:
            if self._applied(roll["id"]) is None:
                continue

            steps = roll["steps"]
            steps.reverse()

            for step in steps:
                if step.rollback is None:
                    continue

                try:
                    if isinstance(step.rollback, types.functionType):
                        step.rollback(self.db)
                    else:
                        self.db.sql(step.rollback, ())
                except Exception as e:
                    if step.ignore_errors not in ["rollback", "all"]:
                        raise e

            RiderMigration.delete({"migration": roll["id"]})
            RiderLog.new(roll["id"], "rollback")

    def parse_args(self):
        parser = argparse.ArgumentParser(description="Rider migration tool for Estoult")
        subparsers = parser.add_subparsers(
            title="positional arguments", dest="subcommand"
        )

        create_parser = subparsers.add_parser("create", help="create a new migration")
        create_parser.add_argument(
            "-m", "--message", help="migration description message", required=True
        )

        subparsers.add_parser("migrate", help="migrate a repo")

        subparsers.add_parser("migrations", help="show all migrations")

        rollback_parser = subparsers.add_parser(
            "rollback", help="rollback to a migration"
        )
        rollback_parser.add_argument(
            "-i", "--index", help="migration index", required=True
        )

        args = parser.parse_args()

        if args.subcommand is None:
            parser.print_help(sys.stderr)
            return

        getattr(self, args.subcommand)(args)


def entry():
    path = os.getcwd()

    try:
        r = open(path + "/rider.py").read()
    except FileNotFoundError:
        print("Error: No rider.py file found")
        sys.exit()

    sys.path.append(path)

    mod = {}
    exec(r, mod)

    try:
        db = mod["db"]
    except KeyError:
        print("`db` object not exported")
        sys.exit()

    config = mod.get("config") or {}

    Rider(db, config).parse_args()


if __name__ == "__main__":
    entry()
