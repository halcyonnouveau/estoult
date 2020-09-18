r"""
Lightweight connection pooling. This is heavily recommended for multi-threaded
applications (e.g webservers).

In a multi-threaded application, up to `max_connections` will be opened. Each
thread (or, if using gevent, greenlet) will have it's own connection.

In a single-threaded application, only one connection will be created. It will
be continually recycled until either it exceeds the stale timeout or is closed
explicitly (using `.manual_close()`).

Note: `autoconnect` is disabled so your application needs to ensure that
connections are opened and closed when you are finished with them, so they can be
returned to the pool.
"""

import heapq
import random
import time
import threading

from collections import namedtuple

try:
    from psycopg2.extensions import TRANSACTION_STATUS_IDLE
    from psycopg2.extensions import TRANSACTION_STATUS_INERROR
    from psycopg2.extensions import TRANSACTION_STATUS_UNKNOWN
except ImportError:
    TRANSACTION_STATUS_IDLE = (
        TRANSACTION_STATUS_INERROR
    ) = TRANSACTION_STATUS_UNKNOWN = None

from estoult import MySQLDatabase, PostgreSQLDatabase, SQLiteDatabase


def make_int(val):
    if val is not None and not isinstance(val, (int, float)):
        return int(val)
    return val


class MaxConnectionsExceeded(ValueError):
    pass


PoolConnection = namedtuple(
    "PoolConnection", ("timestamp", "connection", "checked_out", "cursor")
)


class PooledDatabase(object):
    def __init__(
        self, max_connections=20, stale_timeout=None, timeout=None, *args, **kwargs
    ):
        self._max_connections = make_int(max_connections)
        self._stale_timeout = make_int(stale_timeout)
        self._wait_timeout = make_int(timeout)

        if self._wait_timeout == 0:
            self._wait_timeout = float("inf")

        # Available / idle connections stored in a heap, sorted oldest first.
        self._connections = []

        # Mapping of connection id to PoolConnection. Ordinarily we would want
        # to use something like a WeakKeyDictionary, but Python typically won't
        # allow us to create weak references to connection objects.
        self._in_use = {}

        super(PooledDatabase, self).__init__(autoconnect=False, *args, **kwargs)

    @property
    def conn_key(self):
        return threading.get_ident()

    @property
    def conn(self):
        c = self._in_use[self.conn_key]
        return c.connection

    def connect(self):
        if not self._wait_timeout:
            return super(PooledDatabase, self).connect()

        expires = time.time() + self._wait_timeout

        while expires > time.time():
            try:
                ret = super(PooledDatabase, self).connect()
            except MaxConnectionsExceeded:
                time.sleep(0.1)
            else:
                return ret

        raise MaxConnectionsExceeded(
            "Max connections exceeded, timed out " "attempting to connect."
        )

    def _connect(self):
        while True:
            try:
                # Remove the oldest connection from the heap.
                ts, conn = heapq.heappop(self._connections)
            except IndexError:
                ts = conn = None
                break
            else:
                if self._is_closed(conn):
                    # This connecton was closed, but since it was not stale
                    # it got added back to the queue of available conns. We
                    # then closed it and marked it as explicitly closed, so
                    # it's safe to throw it away now.
                    # (Because Database.close() calls Database._close()).
                    ts = conn = None
                elif self._stale_timeout and self._is_stale(ts):
                    # If we are attempting to check out a stale connection,
                    # then close it. We don't need to mark it in the "closed"
                    # set, because it is not in the list of available conns
                    # anymore.
                    self._close(conn, True)
                    ts = conn = None
                else:
                    break

        if conn is None:
            if self._max_connections and (len(self._in_use) >= self._max_connections):
                raise MaxConnectionsExceeded("Exceeded maximum connections.")

            conn = super(PooledDatabase, self)._connect()
            ts = time.time() - random.random() / 1000

        self._in_use[self.conn_key] = PoolConnection(
            ts, conn, time.time(), conn.cursor()
        )

        return conn

    def _new_cursor(self):
        c = self._in_use[self.conn_key]
        self._in_use[self.conn_key] = PoolConnection(
            c.timestamp, c.connection, c.checked_out, c.connection.cursor()
        )

    @property
    def cursor(self):
        c = self._in_use[self.conn_key]
        return c.cursor

    def _is_stale(self, timestamp):
        # Called on check-out and check-in to ensure the connection has
        # not outlived the stale timeout.
        return (time.time() - timestamp) > self._stale_timeout

    def _is_closed(self, conn):
        return False

    def _can_reuse(self, conn):
        # Called on check-in to make sure the connection can be re-used.
        return True

    def _close(self, close_conn=False):
        conn = self.conn

        if close_conn:
            super(PooledDatabase, self)._close(conn)
        elif self.conn_key in self._in_use:
            pool_conn = self._in_use.pop(self.conn_key)

            if self._stale_timeout and self._is_stale(pool_conn.timestamp):
                super(PooledDatabase, self)._close(conn)
            elif self._can_reuse(conn):
                heapq.heappush(self._connections, (pool_conn.timestamp, conn))

    def manual_close(self):
        # Close the underlying connection without returning it to the pool.
        if self.is_closed():
            return False

        conn = self.connection()

        # A connection will only be re-added to the available list if it is
        # marked as "in use" at the time it is closed. We will explicitly
        # remove it from the "in use" list, call "close()" for the
        # side-effects, and then explicitly close the connection.
        self._in_use.pop(self.conn_key, None)
        self.close()
        self._close(conn, close_conn=True)

    def close_idle(self):
        # Close any open connections that are not currently in-use.
        with self._lock:
            for _, conn in self._connections:
                self._close(conn, close_conn=True)
            self._connections = []

    def close_stale(self, age=600):
        # Close any connections that are in-use but were checked out quite some
        # time ago and can be considered stale.
        with self._lock:
            in_use = {}
            cutoff = time.time() - age
            n = 0
            for key, pool_conn in self._in_use.items():
                if pool_conn.checked_out < cutoff:
                    self._close(pool_conn.connection, close_conn=True)
                    n += 1
                else:
                    in_use[key] = pool_conn
            self._in_use = in_use

        return n

    def close_all(self):
        # Close all connections -- available and in-use. Warning: may break any
        # active connections used by other threads.
        self.close()

        with self._lock:
            for _, conn in self._connections:
                self._close(conn, close_conn=True)
            for pool_conn in self._in_use.values():
                self._close(pool_conn.connection, close_conn=True)
            self._connections = []
            self._in_use = {}


class PooledMySQLDatabase(PooledDatabase, MySQLDatabase):
    def _is_closed(self, conn):
        try:
            conn.ping(False)
        except Exception:
            return True
        else:
            return False


class PooledPostgreSQLDatabase(PooledDatabase, PostgreSQLDatabase):
    def _is_closed(self, conn):
        if conn.closed:
            return True

        txn_status = conn.get_transaction_status()

        if txn_status == TRANSACTION_STATUS_UNKNOWN:
            return True
        elif txn_status != TRANSACTION_STATUS_IDLE:
            conn.rollback()

        return False

    def _can_reuse(self, conn):
        txn_status = conn.get_transaction_status()
        # Do not return connection in an error state, as subsequent queries
        # will all fail. If the status is unknown then we lost the connection
        # to the server and the connection should not be re-used.
        if txn_status == TRANSACTION_STATUS_UNKNOWN:
            return False
        elif txn_status == TRANSACTION_STATUS_INERROR:
            conn.reset()
        elif txn_status != TRANSACTION_STATUS_IDLE:
            conn.rollback()

        return True


class PooledSQLiteDatabase(PooledDatabase, SQLiteDatabase):
    def _is_closed(self, conn):
        try:
            conn.total_changes
        except Exception:
            return True
        else:
            return False
