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

   >>> print(Query(Animal).select().where({Animal.name: "Red Panda"}))
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

Import the ``op`` class to use operators.

.. code-block:: python

   >>> from estoult import Query, op
   >>> query = Query(Meal).select()
   # name = "Pizza" OR name = "Fish"
   >>> query.where(op.or_({Meal.name: "Pizza"}, {Meal.name: "Fish"}))
   # calories < 400
   >>> query.where({Meal.calories: op.lt(400)})
