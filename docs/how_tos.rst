How To's
========

Joins
-----

Use a ``join`` function in your ``Query``. Example:

.. code-block:: python

    (Query(Contact)
        .select(Contact.id, Person.name)
        .left_join(Person, on=[Person.contact_id, Contact.id])
        .execute())

Currently, the supported joins are:

- ``inner_join``
- ``left_join``
- ``left_outer_join``
- ``right_join``
- ``right_outer_join``
- ``full_join``
- ``full_outer_join``

Validation
----------

Estoult by default only validates the type of a field. You can easily extend this by adding a ``classmethod`` called ``validate`` to the schema.

.. code-block:: python

    class Person(db.Schema):
        __tablename__ = "people"

        id = Field(str, "id")
        name = Field(str, "name")
        dob = Field(str, "dob")
        country = Field(str, "country")

        @classmethod
        def validate(cls, row):
            if row["country"] == "France":
                raise Exception("No French allowed")

Query operators
---------------

Common query operators can be used as overloaded python operators in every ``Field``/``Clause``. These are:

======== =======
Operator Meaning
-------- -------
``==``   x equals y
``<``    x is less than y
``<=``   x is less than or equal to y
``>``    x is greater than y
``>=``   x is greater than or equal to y
``!=``   x is not equal to y
======== =======

.. code-block:: python

    >>> from estoult import Query, op
    >>> query = Query(Meal).select()
    >>> query.where(Meal.name != "Pizza")
    >>> query.where(Meal.calories > 400)

Other operators are available as methods from the ``op`` module.:

.. list-table::
   :widths: 20 80

   * - Function
     - Example
   * - ``op.or_``
     - ``.where(op.or_(Person.id == 1, Person.id == 2))``
   * - ``op.and_``
     - ``.where(op.and_(Person.id == 1, Person.id == 2))``
   * - ``op.in_``
     - ``.where(op.in_(Person.id, [1, 2, 3, 4]))``
   * - ``op.like``
     - ``.where(op.like(Person.name, "Astol%"))``
   * - ``op.ilike``
     - ``.where(op.ilike(Person.name, "%StOL%"))``
   * - ``op.not``
     - ``.where(op.not_(Person.name == "Name"))``
   * - ``op.is_null``
     - ``.where(op.is_null(Person.dob))``
   * - ``op.not_null``
     - ``.where(op.not_null(Person.dob))``

.. code-block:: python

    >>> query = Query(Car).select()
    # name = "Ferrari" OR engine = "GP2"
    >>> query.where(op.or_(Car.name == "Ferrari", Car.engine == "GP2"))
    # name like '%Renault%'
    >>> query.where(op.like(Car.name, "%Renault%"))

Function operators
------------------

Function operators are imported with the ``fn`` module.

.. list-table::
   :widths: 20 80

   * - Function
     - Example
   * - ``fn.count``
     - ``.select(fn.count(Person.id))``
   * - ``fn.sum``
     - ``.select(fn.sum(Person.weight))``
   * - ``fn.avg``
     - ``.select(fn.avg(Person.age))``
   * - ``fn.ceil``
     - ``.where(fn.ceil(Person.height) == 180)``
   * - ``fn.distinct``
     - ``.select(fn.distinct(Person.email))``
   * - ``fn.concat``
     - ``.where(fn.concat(Person.first_name, "' '", Person.last_name) == "Carlos Sainz")``
   * - ``fn.alias``
     - ``.select(fn.alias(fn.sum(Person.weight), "weight"))``
   * - ``fn.cast``
     - ``.select(fn.cast(Person.dob, "datetime"))``

Adding Ops/Fns
--------------

Estoult comes with the most important and commonly used functions/operators for SQL. However, Estoult is not an ORM and is inherently hackable which means you can easily add additional functionality if you need.

If you wanted to add the ``<->`` operator from PostgreSQL's `pg_trgm <https://www.postgresql.org/docs/current/pgtrgm.html>`_ extension, you would use the ``add_op`` from ``op`` anywhere Estoult is always imported from (most likely where your database object is).


.. code-block:: python

    from estoult import PostgreSQLDatabase, op

    db = PostgreSQLDatabase(...)

    # Add the <-> operator here and call it "trgm"
    op.add_op("trgm", "<->")

Now we can use it anywhere:

.. code-block:: python

    from estoult import Query, op

    # select * from customers order by name <-> 'glgamish' limit 10;
    print(Query(Customer).select()
        .order_by(op.trgm(cls.name, "glgamish"))
        .limit(10)
        .execute())

The same can be done for the ``fn`` module using ``add_fn``.

Display generated query
-----------------------

You can ``print`` any un-executed ``Query`` to display the generated SQL.

.. code-block:: python

    >>> print(Query(Animal).select().where(Animal.name == "Red Panda"))
    select * from animals where animals.name = "Red Panda"

To format the query parameters, Estoult uses the ``mogrify`` function for PostgreSQL and just runs it for the other sources. This means it will fail if there is a syntax error in the SQL. To see it unformatted you will need to use ``repr`` as well.
