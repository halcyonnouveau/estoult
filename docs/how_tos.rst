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

- inner join
- left join
- left outer join
- right join
- right outer join
- full join
- full outer join

Display generated query
-----------------------

You can ``print`` any unexecuted ``Query`` to display the generated SQL.

.. code-block:: python

   >>> print(Query(Animal).select().where(Animal.name == "Red Panda"))
   select * from animals where animals.name = "Red Panda"

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

Common query operators can be used as overloaded python operators in every ``Field``. These are:

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

Other operators are avaliable as methods:

.. code-block:: python

   >>> query = Query(Car).select()
   # name = "Ferrari" OR engine = "GP2"
   >>> query.where(op.or_(Car.name == "Ferrari", Meal.name == "GP2"))
   # name like '%Renault%'
   >>> query.where(op.like(Meal.cook, op.like("Renault")))
