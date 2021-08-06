Advanced Examples
=================

These are examples of some of the more advanced features that Estoult has.

Associations
------------

Currently only two kinds of associations are supported: one-to-one and one-to-many. You can create them with the ``Association`` class.

Here's an example where we have an ``Organisation`` that has many ``Users`` and one ``Admin``. Where an ``Admin`` is also a ``User``.

.. code-block:: python

   from esoult import Field, Association


   class User(db.Schema):

       __tablename__ = "users"

       id = Field(int, null=False)
       organisation_id = Field(int)
       name = Field(str)

   class Admin(db.Schema):

       __tablename__ = "admins"

       id = Field(int, null=False)
       organisation_id = Field(int)
       user_id = Field(int)

       user = Association.has_one(User, on=["user_id", "id"])

   class Organisation(db.Schema):

       __tablename__ = "organisations"

       id = Field(int, null=False)
       name = Field(str)

       admin = Association.has_one(Admin, on=["id", "organisation_id"])
       users = Association.has_many(User, on=["id", "organisation_id"])

If you need to create a relationship on a schema that has not yet been defined, you supply a string of the module path of the schema, instead of the schema path itself:

.. code-block:: python

   class Organisation(db.Schema):
       # ...
       admin = Association.has_one("schemas.base.Admin", on=["id", "organisation_id"])
       # ...

With associations we can now ``preload`` to retrieve all the data from ``Organisation`` to ``User`` without having to construct multiple queries.

.. code-block:: python

   organisations = (
      Query(Organisation)
      .select()
      .preload({Organisation.admin: [Admin.user])
      .preload(Organisation.users)
      .execute()
   )

To retrieve all the fields in the associated schema you can have the association field by itself, like with ``.preload(Organisation.users)``. To define specific fields and associations in the schema (Estoult will not recursively go through every association by default for performance reasons, so they must be specified), pass in a dictionary with the key as the owner field and the value as a list of fields.

This ``select`` will return a list of rows looking something like this:

.. code-block:: python

   [
      {
         "id": 1,
         "name": "Org Name",
         "admin": {
            "user": {"id": 2, "name": "Real Name"}
         },
         "users": [
            {"id": 3, "name": "Fake Name"}
            ...
         ]
      }
      ...
   ]

Note that we aren't getting the ``id`` in the ``admin`` field because we only specified ``Admin.user``. If instead, we wanted the ``id`` of ``admin`` but not of ``user`` we would need to change the preload:

.. code-block:: python

   # From this
   .preload({Organisation.admin: [Admin.user])
   # To this
   .preload({Organisation.admin: [Admin.id, {Admin.user: [User.name]}]})

For creating and updating with associations you pass in the same structure you would get from a ``preload``.

.. code-block:: python

   new_org = {
      "name": "Les Fans D'Astolfo",
      "admin": {
         "user": {"name": "Test Account"}
      },
      "users": [
         # This is updated
         {"id": 4, "name": "Justin Duch"},
         # This is inserted
         {"name": "Emilie Rousseau"}
      ],
   }

   org = Organisation.insert(new_org)

For each association, if there is a primary key supplied it will update the row, otherwise it will do an insert. This is the same no matter if the parent is  inserting or updating.


Disabling wildcard selects on a schema
--------------------------------------

If performance is of importance to you, it is recommended to never use a wildcard (``*``) in your SQL select queries. For larger tables a ``select *`` is often `detrimental to performance <https://tanelpoder.com/posts/reasons-why-select-star-is-bad-for-sql-performance>`_. Unfortunately, most ORMs (and Estoult) make wildcards too easy to do, as they are the default when no fields are specifically provided in a query.

But unlike most ORMs, Estoult doesn't suck and actually cares about performant SQL, so you can easily remove the ability to use a ``*`` with the class variable ``allow_wildcard_select`` in your schema.

.. code-block:: python

    class VeryBigTable(db.schema):
        __tablename__ = "very_big_table"
        allow_wildcard_select = False

        id = Field(str)
        field1 = Field(str)
        field2 = Field(str)

Because wildcards can still be useful for prototyping, and aren't a big of a problem for smaller tables, this allows you to pick and choose which schemas can use wildcards. You could also disallow them on every schema by default by using a base class, and separately allow them in each schema for smaller tables.

Now running a select query without specifying fields will raise an error:

.. code-block:: python

    # ILLEGAL! GO TO GAOL!
    Query(VeryBigTable).select().execute()

    # Do this instead :3
    Query(VeryBigTable).select(VeryBigTable.field2).execute()

This also applies to preloading associations:

.. code-block:: python

    # BIG NO NO!
    Query(VeryBigTableParent)
        .select()
        .preload(VeryBigTableParent.very_big_tables)
        .execute()

    # Very fast and correct, good job!
    Query(VeryBigTableParent)
        .select()
        .preload({VeryBigTableParent.very_big_tables: [VeryBigTable.field1]})
        .execute()

Procedurally building queries
-----------------------------

Imagine you have a service to sync your music library between multiple streaming platforms.

You'd have one ``Schema`` to keep track of your general music collection and several links to each of your services.

.. code-block:: python

    class Song(db.schema):
        __tablename__ = "songs"

        id = Field(str)
        title = Field(str)
        artist = Field(str)


    class Spotfiy(db.schema):
        __tablename__ = "spotify"

        song_id = Field(str, "song_id", primary_key=True)
        spotify_id = Field(str, "spotify_id")


    class AppleMusic(db.schema):
        __tablename__ = "applemusic"

        song_id = Field(str, "song_id", primary_key=True)
        applemusic_id = Field(str, "applemusic_id")


    class Soundcloud(db.schema):
        __tablename__ = "soundcloud"

        song_id = Field(str, "song_id", primary_key=True)
        soundcloud_id = Field(str, "soundcloud_id")

To populate the tables, you use each of the services API's to fetch all your music, add each song to the ``Song`` table and the service's corresponding ``id`` to it's table with the ``song_id`` we made.

.. note::

    I have no idea if any of these services let you do this.

But for some reason, because you are a terrible programmer, this process creates a bunch of "orphaned" songs, where a row in the ``Song`` table has no rows in either ``Spotify``, ``AppleMusic``, or ``Soundcloud`` pointing to it. And instead of fixing the underlying issue, you just decide to write a SQL statement to remove orphaned songs to run every once in a while.

The SQL would look like this.

.. code-block:: sql

    delete from songs
    where song.id in (
        select song.id
        from songs
                 left join spotify on spotify.song_id = songs.id
                 left join applemusic on applemusic.song_id = songs.id
                 left join soundcloud on soundcloud.song_id = songs.id
        where spotify.spotify_id is null
          and applemusic.applemusic_id is null
          and soundcloud.soundcloud_id is null
    )

You'd easily be able to write this in Estoult, but you know that you are intending to add more streaming services in the future and wont be bothered to keep having to change the query.

Instead we can create this query procedurally to minimise the amount of things you'll have to change.

First, let's make a mapping for our tables.

.. code-block:: python

    links = {
        "spotify": Spotfiy
        "applemusic": AppleMusic,
        "soundcloud": Soundcloud,
    }

Now let's start on the "select" subquery. We first start by selecting the ``Song.id``.

.. code-block:: python

    select_query = Query(Song).select(Song.id)

And we can add our left joins for every service.

.. code-block:: python

    for schema in links.values():
        select_query.left_join(schema, on=[Song.id, schema.song_id])

For our ``where`` we would use list comprehension and then de-construct the list into function arguments.

.. code-block:: python

    select_query.where(
        *[op.is_null(s[f"{n}_id"]) for n, s in links.items()]
    )

You can access a ``Schema``'s fields as if they were a dict. In ``op.is_null(s[f"{n}_id"])`` we are doing just that, where ``s`` and ``n`` are the schema and name we get from ``links.items()``.

Finally, we can add it to a ``delete`` function.

.. code-block:: python

    Query(Song).delete().where(op.in_(Song.id, select_query)).execute()

Now we only need to change the ``links`` dictionary instead of messing around with the query.

This is what it looks like all together for reference:

.. code-block:: python

    links = {
        "spotify": Spotfiy
        "applemusic": AppleMusic,
        "soundcloud": Soundcloud,
    }

    select_query = Query(Song).select(Song.id)

    for schema in links.values():
        select_query.left_join(schema, on=[Song.id, schema.song_id])

    select_query.where(
        *[op.is_null(s[f"{n}_id"]) for n, s in links.items()]
    )

    Query(Song).delete().where(op.in_(Song.id, select_query)).execute()
