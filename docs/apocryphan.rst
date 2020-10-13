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

Start by creating a script (eg. ``rider.py``) to invoke the command line tools using your ``db`` object.

.. code-block:: python

    from apocryphan.rider import Rider
    from src.schemas.base import db

    if __name__ == "__main__":
        db.connect()  # For manual connection management
        Rider(db).parse_args()
        db.close()

Create a new migration with a description.

.. code-block:: bash

    python3 rider.py create -d "init db"

This will create a scaffold in the ``./migrations`` directory. You can change the source directory by passing a dictionary to ``Rider``.

.. code-block:: python

     Rider(db, {"source": "./my_dir"}).parse_args()

View migrations:

.. code-block:: bash

    python3 rider.py migrations

Apply migrations:

.. code-block:: bash

    python3 rider.py migrate
