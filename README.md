# Estoult

Estoult is a Python toolkit for data mapping with an integrated query builder for SQL databases. It currently supports MySQL, PostgreSQL, and SQLite.

Features:

- **Not an ORM:** Estoult treats the data, not objects, as first class citizens.
- **No DSL:** Query building is done using functions instead of overriding Python operators.
- **Composable (sub)queries:** Create subqueries and store them for later use.
- **Easy debugging:** Display any generated SQL in a readable format.
- **Performant as raw SQL:** Estoult is **NOT** an ORM.

## Example

```python
from estoult import MySQLDatabase, Query, Field, fn, op

db = MySQLDatabase(
    user="user",
    password="pass",
    port="port",
    database="database"
)


class BaseSchema(db.Schema):
    id = Field(int, "id")
    archive = Field(int, "archive", default=0)
    created = Field(str, "created", default="0000-00-00")
    updated = Field(str, "updated", default="0000-00-00")


class User(BaseSchema):
    table_name = "Users"
    person_id = Field(int, "person_id", null=False)
    password = Field(str, "password", null=False)

    @classmethod
    def get_by_id(cls, id)
        # Get single user
        return (Query(cls)
            .get()
            .where({cls.id: id})
            .execute())


class Person(BaseSchema):
    table_name = "Persons"
    email = Field(str, "email")
    first_name = Field(str, "first_name")
    last_name = Field(str, "last_name")

    @classmethod
    def validate(cls, row):
        # Changeset is the row to be inserted/updated after any defaults
        # have been applied
        changeset = super().validate(row)

        # Do some additional validation here
        if changeset.get("email", "").endswith(".fr"):
            raise Exception("The French are banned.")

        return changeset


# Select all users
users = (
    Query(User)
    .select()
    .execute()
)

# Count all users
users_count = (
    Query(User)
    .get(fn.alias(fn.count(User.id), "count"))
    .execute()
)["count"]

# Left join with person where id > 2
users_join = (
    Query(User, Person)
    .select(User.id, Person.first_name, Person.last_name)
    .left_join(Person, on=[Person.id, User.person_id])
    .where({Person.id: op.gt(2)})
    .execute()
)

# Use classmethod we made
user = User.get_by_id(1)

# Create a person
person_id = Person.insert({
    "first_name": "Matthew", "last_name": "Rousseau", "email": "fake@mail.com"
})

# Update the person
Person.update({"id": person_id}, {"email": "astolfo@waifu.church"})

# Bulk update
(Query(Person)
    .update({Person.first_name: "Fake Name"})
    .where({Person.last_name: "Last Name"})
    .execute())
```

## Documentation

Documentation is in progress.
