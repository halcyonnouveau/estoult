Apocryphan
==========

Estoult includes a number of extensions in the ``apocryphan`` namespace.

Connection pooling
------------------

The ``pool`` module contains a number of ``Database`` classes that provide connection pooling for PostgreSQL, MySQL and SQLite databases. The pool works by overriding the methods on the ``Database`` class that open and close connections to the backend. The pool can specify a timeout after which connections are recycled, as well as an upper bound on the number of open connections.

This is heavily recommended for multi-threaded applications (e.g webservers).

In a multi-threaded application, up to ``max_connections`` will be opened. Each thread (or, if using gevent, greenlet) will have it's own connection.

In a single-threaded application, only one connection will be created. It will be continually recycled until either it exceeds the stale timeout or is closed explicitly (using ``.manual_close()``).

.. code-block:: python

    from apocryphan.pool import PooledPostgreSQLDatabase

    db = PooledPostgreSQLDatabase(
        max_connections=32,
        stale_timeout=300,
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
        host=os.getenv("POSTGRES_HOST", "localhost"),
        database=os.getenv("POSTGRES_DB", "porg"),
    )


.. warning::

   ``autoconnect`` is disabled so your application needs to ensure that connections are opened and closed when you are finished with them, so they can be returned to the pool. With a Flask server, it could look like this:

   .. code-block:: python

       @app.before_request
       def open_connection():
           db.connect()

       @app.teardown_request
       def close_connection(exc):
           db.close()

Rider
-----

``rider`` is a simple tool to help manage database migrations using the existing Estoult database object.

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

This will create the bellow scaffold file you can add your migration steps too.

.. code-block:: bash

    """
    create table
    """

    from apocryphan.rider import step

    __depends__ = {"1602721237-add-pg-extensions"}

    steps = [
        step("")
    ]

The ``step`` function takes 3 arguments:

* ``migreate``: a SQL query or function to apply the migration step.
* ``rollback``: (optional) a SQL query or function to rollback the migration step.
* ``ignore_errors``: (optional, one of "migrate", "rollback" or "all") causes rider to ignore database errors in either migrate, rollback, or both stages.

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

You can supply a function to ``migrate`` or ``rolllback``. Each function takes your db object.

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
