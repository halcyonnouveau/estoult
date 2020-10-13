r"""
A migration tool for Estoult.
"""

import __main__
import os
import re
import glob
import sys
import argparse
import time
import uuid
import ast
import getpass
import socket

from pathlib import Path
from collections import namedtuple

__all__ = ["Rider", "step"]

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


def step(st):
    return st


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


class Rider:

    default_config = {
        "source": "./migrations",
        "table_name": "_rider_migrations",
        "log_name": "_rider_logs",
    }

    def __init__(self, db, config={}):
        self.db = db
        self.config = {**Rider.default_config, **config}

        # Script path
        self._scr_path = os.path.dirname(os.path.realpath(__main__.__file__))
        # Migration path
        self._mig_path = Path(self._scr_path) / self.config["source"]

        self.init_tables()

    def init_tables(self):
        self.db.sql(
            """
            create table if not exists %s (
                id varchar(256) primary key not null,
                migration varchar(256) not null,
                operation varchar(56) not null,
                username varchar(128),
                hostname varchar(128),
                time timestamp default current_timestamp
            );
        """
            % (self.config["log_name"]),
            (),
        )

        self.db.sql(
            """
            create table if not exists %s (
                migration varchar(256) primary key not null,
                applied_at timestamp default current_timestamp
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
        name = args.name

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

    def migrate(self, _args):
        migs = self._get_migrations()

        applied = [
            s["migration"]
            for s in self.db.select(
                "select * from %s" % (self.config["table_name"]), ()
            )
        ]

        with self.db.atomic():
            for m in migs:
                if m["id"] in applied:
                    continue

                depends = m["__depends__"]

                if depends:
                    name = depends.pop()
                    depends_applied = self.db.get_or_none(
                        "select * from %s where migration = %s"
                        % (self.config["table_name"], "%s"),
                        (name,),
                    )

                    if depends_applied is None:
                        raise Exception(
                            f"""
                            {m['id']} depends on {name} but is not applied.
                            """.strip()
                        )

                steps = m["steps"]

                for step in steps:
                    self.db.sql(step, ())

                self.db.sql(
                    "insert into %s (migration) values (%s)"
                    % (self.config["table_name"], "%s"),
                    (m["id"],),
                )

                self.db.sql(
                    """
                    insert into %s
                    (id, migration, operation, username, hostname)
                    values (%s, %s, %s, %s, %s)
                """
                    % (self.config["log_name"], "%s", "%s", "%s", "%s", "%s"),
                    (
                        str(uuid.uuid4()),
                        m["id"],
                        "apply",
                        getpass.getuser(),
                        socket.gethostname(),
                    ),
                )

                print(f"Applied migration: {m['id']}")

    def migrations(self, _args):
        migs = self._get_migrations()

        Row = namedtuple("Row", ["idx", "description", "applied"])
        rows = []

        for idx, m in enumerate(migs):
            applied = (
                self.db.get_or_none(
                    "select applied_at as at from %s where migration = %s"
                    % (self.config["table_name"], "%s"),
                    (m["id"],),
                )
                or False
            )

            if applied:
                applied = applied["at"].strftime("%Y-%m-%d %H:%M:%S.%f")

            rows.append(Row(idx, m["doc"], str(applied)))

        _print_table(rows)

    def rollback(self, args):
        pass

    def parse_args(self):
        parser = argparse.ArgumentParser(description="Rider migration tool for Estoult")
        subparsers = parser.add_subparsers(
            title="positional arguments", dest="subcommand"
        )

        create_parser = subparsers.add_parser("create", help="create a new migration")
        create_parser.add_argument(
            "-d", "--description", help="migration description", required=True
        )

        subparsers.add_parser("migrate", help="migrate a repo")

        subparsers.add_parser("migrations", help="show all migrations")

        # rollback_parser = subparsers.add_parser(
        #     "rollback", help="rollback to a migration"
        # )
        # rollback_parser.add_argument("-i" "--id", help="migration id", required=True)

        with self.db.atomic():
            args = parser.parse_args()

            if args.subcommand is None:
                parser.print_help(sys.stderr)
                return

            getattr(self, args.subcommand)(args)
