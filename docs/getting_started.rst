Getting Started
===============

In this guide, we're going to learn some basics of Estoult, such as creating, reading, updating and destroying records from a PostgreSQL database.

This guide will require you to have setup PostgreSQL beforehand.

Installing
----------

To install the latest version, hosted on PyPI:

.. code-block:: text

   pip install estoult

If you are using SQLite you don't need to install anything else. Otherwise you need to have the correct database driver installed:

* PostgreSQL: `psycopg2 <http://initd.org/psycopg/docs/install.html#installation>`_
* MySQL: `mysqlclient <https://pypi.python.org/pypi/mysqlclient/>`_

Creating the database object
----------------------------

Estoult has different database classes for each database driver: ``SQLiteDatabase``, ``PostgreSQLDatabase`` and ``MySQLDatabase``. We will use ``PostgreSQLDatabase`` here:

.. code-block:: python

   from estoult import *

   db = PostgreSQLDatabase(
      database="my_db",
      user="postgres",
      password="postgres"
   )

Creating schemas
----------------

The schema is a representation of data from our database. We create schemas by inheriting from the database ``Schema`` attribute.

.. code-block:: python

   class Author(db.Schema):
      table_name = "authors"

      id = Field(int, "id")
      first_name = Field(str, "first_name")
      last_name = Field(str, "last_name")

   class Book(db.Schema):
      table_name = "books"

      id = Field(int, "id")
      name = Field(str, "name")
      author_id = Field(int, "author_id")

This defines the schema from the database that this schema maps to. In this case, we're saying that the ``Author`` schema maps to the ``authors`` table in the database, and the ``id``, ``first_name`` and ``last_name`` are fields in that table.

**Note:** It is good practice to have your database table be named plural but schema as singular.

Inserting and updating data
---------------------------

We can insert new rows into our tables like this:

.. code-block:: python

   new_author = {"first_name": "Kurt", "last_name": "Vonnegut"}

   # `insert` returns the id of the new row
   new_author["id"] = Author.insert(new_author)

   new_book = {"name": "Player Piano", "author_id": new_author["id"]}

   new_book["id"] = Book.insert(new_book)

To update the row, we use ``update``:

.. code-block:: python

   Book.update(new_book, {"name": "Slaughterhouse-Five"})

Here we updated the row ``new_book`` with a new ``name``.
