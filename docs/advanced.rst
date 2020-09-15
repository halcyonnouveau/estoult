Advanced Examples
=================

Examples of things the pros do with Estoult ;)

Procedurally creating queries
-----------------------------

Imagine you have a service to sync your music library between multiple streaming platforms.

You'd have one ``Schema`` to keep track of your general music collection and several links to each of your services.

.. code-block:: python

    class Song(db.schema):
        __tablename__ = "songs"

        id = Field(str, "id")
        title = Field(str, "title")
        artist = Field(str, "title")


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
