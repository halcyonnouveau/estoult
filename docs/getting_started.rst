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
        __tablename__ = "authors"

        id = Field(int)
        first_name = Field(str)
        last_name = Field(str)

    class Book(db.Schema):
        __tablename__ = "books"

        id = Field(int)
        name = Field(str)
        author_id = Field(int)

This defines the schema from the database that this schema maps to. In this case, we're saying that the ``Author`` schema maps to the ``authors`` table in the database, and the ``id``, ``first_name`` and ``last_name`` are fields in that table.

.. note::

   It is good practice to have your database table be named as a plural noun but schema as a singular noun.

Inserting and updating data
---------------------------

We can insert new rows into our tables like this:

.. code-block:: python

    new_author = {"first_name": "Kurt", "last_name": "Vonnegut"}
    new_author = Author.insert(new_author)

    new_book = {"name": "Player Piano", "author_id": new_author["id"]}
    new_book = Book.insert(new_book)

To update the row, we use ``update``:

.. code-block:: python

    new_book = Book.update(new_book, {"name": "Slaughterhouse-Five"})

Here we updated the row ``new_book`` with a new ``name``.

``update`` and ``insert`` return the "changeset" of the row. That is, it returns the row that is executed in database (after ``default``, ``caster``, ``null``, etc... has been applied). For inserting it also returns the added ``primary_key`` to the set if missing.

Fetching a single record
------------------------

``Schema`` is for inserting/updating rows. When retrieving data or working with multiple rows we use the ``Query`` class.

.. code-block:: python

    my_book = (
        Query(Book)
        .get()
        .where(Book.id == 1)
        .execute()
    )

    print(my_book["id"])

``Query`` builds your SQL query using a wide range of functions. We are using ``get`` to only retrieve one row and ``where`` to specify which. ``where`` accepts a number of clauses (or ``op``, but that is for later) to send as arguments. When the query is built we call ``execute`` to run it.

Fetching multiple records
-------------------------

Instead of using ``get``, use ``select`` to get multiple records.

.. code-block:: python

   my_books = (
        Query(Book)
        .select()
        .execute()
   )

This will get all books.


Updating multiple records
-------------------------

You can do basic updates of records with ``Schema``.

.. code-block:: python

    book_to_update = {"id": "123", "name": "Book"}
    update = {"name": "New Book"}

    Book.update(book_to_update, update)

This updates books where ``id`` is ``123`` and ``name`` is ``Book``. You actually only need to pass in a unique field if you want to update a single book, but passing other fields aswell is fine.

``Query`` can be used to make more complicated updates.

.. code-block:: python

    update_books = {"name": "Casseur de Logistille"}

    (Query(Book)
        .update(update_books)
        .where(Book.id > 0)
        .execute())

This is updating all books with an ``id`` greater than ``0``.

Deleting records
----------------

Now that we've covered inserting, reading and updaing. The last thing is how to delete records in Estoult.

Similar to updating, we can use ``Schema`` or ``Query``. Let's delete ``my_book`` which we retrieved earlier.

.. code-block:: python

    # Single book
    Book.delete(my_book)

    # Multiple books
    (Query(Book)
        .delete()
        .where(Book.id >= my_book["id"])
        .execute())

The ``Query`` is deleting all books which have an ``id`` greater or equal to ``my_book["id"]``.
