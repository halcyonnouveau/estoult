# Estoult

Estoult is a Python data mapper and language integrated query for SQL databases.

It is **NOT** an ORM.

## Example

```python
from estoult import Database, Query, Field

db = Database(
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
            .where(**{str(cls.id): 1})
            .execute())


class Person(BaseSchema):
    table_name = "Persons"

    email = Field(str, "email")
    first_name = Field(str, "first_name")
    last_name = Field(str, "last_name")

    @classmethod
    def validate(cls, row):
        pk, changeset = super().validate(row)

        # Do some additional validation here
        if changeset["email"].endswith(".fr")
            raise Exception("The French are banned.")

        return pk, changeset


# Select all users
users = (
    Query(User)
    .select()
    .execute()
)

# Join users with persons
users_join = (
    Query(User, Person)
    .select(User.id, Person.first_name, Person.last_name)
    .left_join(Person, on=[Person.id, User.person_id])
    .where(**{str(Person.archive): 0})
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
```
