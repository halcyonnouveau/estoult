r"""
A migration tool for Estoult.
"""

import __main__
import os
import sys
import argparse
import time

from pathlib import Path

__all__ = ["Rider", "step"]

SCAFFOLD = """
\"""
%s
\"""

from apocryphan.rider import step

__depends__ = {%s}

steps = [
    step("")
]
""".strip()


def step(st):
    return st


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
        self._mig_path = Path(self._scr_path) / self.default_config["source"]

        self.init_tables()

    def init_tables(self):
        self.db.sql(
            """
            create table if not exists %s (
                id varchar(256) primary key not null,
                migration varchar(256),
                operation varchar(56) not null,
                username varchar(128),
                hostname varchar(128),
                time timestamp
            );
        """
            % (self.config["log_name"]), ()
        )

        self.db.sql(
            """
            create table if not exists %s (
                id varchar(256) primary key not null,
                migration varchar(256),
                applied_at timestamp
            );
        """
            % (self.config["table_name"]), ()
        )

    def create(self, args):
        name = args.name

        filename = f"{int(time.time())}-{'-'.join(name.split(' ')).lower()}.py"
        self._mig_path.mkdir(parents=True, exist_ok=True)

        path = str(self._mig_path / filename)
        script = SCAFFOLD % (name, "")

        with open(path, "w") as f:
            f.write(script)

        print(f"Created migration scaffold in {path}")

    def migrate(self):
        pass

    def migrations(self):
        pass

    def rollback(self):
        pass

    def parse_args(self):
        parser = argparse.ArgumentParser(description="Rider migration tool for Estoult")
        subparsers = parser.add_subparsers(
            title="positional arguments", dest="subcommand"
        )

        create_parser = subparsers.add_parser("create", help="create a new migration")
        create_parser.add_argument("-n", "--name", help="migration name", required=True)

        subparsers.add_parser("migrate", help="migrate a repo")

        subparsers.add_parser("migrations", help="show all migrations")

        rollback_parser = subparsers.add_parser(
            "rollback", help="rollback to a migration"
        )
        rollback_parser.add_argument(
            "-i" "--id", help="migration id", required=True
        )

        with self.db.atomic():
            args = parser.parse_args()

            if args.subcommand is None:
                parser.print_help(sys.stderr)
                return

            getattr(self, args.subcommand)(args)
