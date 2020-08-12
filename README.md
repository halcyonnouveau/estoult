# Estoult

Estoult is a Python data mapper language integrated query for SQL databases.

It is **NOT** an ORM.

## Example

```python
from estoult import Database, Query, Field

db = Database(
    user='user',
    password='pass',
    port='port',
    database='database'
)


class BaseSchema(db.Schema):
    archive = Field(int, 'archive', default=0)
    created = Field(str, 'created', default='0000-00-00')
    updated = Field(str, 'updated', default='0000-00-00')


class User(BaseSchema):
    table_name = "Users"

    id = Field(int, 'id')
    person_id = Field(int, 'person_id')
    password = Field(str, 'password')


class Person(BaseSchema):
    table_name = "Persons"

    id = Field(int, 'id')
    email = Field(str, 'email')
    first_name = Field(str, 'first_name')
    last_name = Field(str, 'last_name')

    @classmethod
    def validate(cls, **kwargs):
        pk, changeset = super().validate(**kwargs)
        # Do some additional validation here
        return pk, changeset


# Select all users
Query(User)
    .select()
    .execute()

# Left join with Person
Query(User, Person)
    .select(User.email, Person.first_name, Person.last_name)
    .left_join(Person, on=[Person.id, User.person_id])
    .where(**{str(Person.archive): 0})
    .execute()

# Get single user
Query(User)
    .get()
    .where(**{str(User.id): 1})
    .execute()

# Create a person
person_id = Person.insert({"first_name": "Matthew", "last_name": "Rousseau"})

# Update the person
Person.update({"id": person_id}, {"email": "astolfo@waifu.church"})
```
