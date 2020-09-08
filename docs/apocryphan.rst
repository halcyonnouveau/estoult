Apocryphan
==========

Estoult includes a number of extentions in the ``apocryphan`` namespace.

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
