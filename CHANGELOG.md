# CHANGELOG.md

## v0.7.8 [Not Released]

- Fix inserting on tables without primary keys.

## v0.7.7 [2021-05-19]

- **Minor breaking change:** Add `is_updating` argument to user validate function.

## v0.7.6 [2021-05-12]

- Rider rollback fix.
- Add sql ops: `+`, `-`, `*`, `/`, `%`.

## v0.7.5 [2021-05-11]

- Actual fix.

## v0.7.4 [2021-05-11]

- Fix rider migrate `depends`.

## v0.7.3 [2021-05-07]

- Fix checking if field is an association.

## v0.7.2 [2021-05-06]

- Fix `has_many` associations error when preload queried is empty.

## v0.7.1 [2021-04-26]

- Fix query `union` to accept schema and actually work.

## v0.7.0 [2021-04-10]

- **BREAKING CHANGE:** rename `apocryphan` to `apocryphes`.
- **BREAKING CHANGE:** `update`/`insert` now returns the changeset of the operation instead of the primary key.
- **BREAKING CHANGE:** rename `QF` to `qf`.
- Add association for `insert`/`update` on `Schema`.

## v0.6.6 [2021-04-09]

- Add `min` and `max` functions.
- Field `default` can now be a function.

## v0.6.5 [2021-03-16]

- Fix wrong errors being called with pooled database.

## v0.6.4 [2021-02-16]

- Add `allow_wildcard_select` to schemas.

## v0.6.3 [2021-02-12]

- Fix associations with `None` values.

## v0.6.2 [2021-02-08]

- Fix `delete_by_pk`.
- Add type hinting for `execute`.

## v0.6.1 [2020-12-16]

- Fix rider depends on variable again.

## v0.6.0 [2020-12-04]

- Add associations for schema definitions.
  - Basic usage for preloading queries.
- Fix atomic for autoconnect.

## v0.5.3 [2020-11-30]

- Fix rider depends on variable.

## v0.5.2 [2020-11-20]

- Fix inserting.

## v0.5.1 [2020-11-09]

- Change rider public functions.
- Remove backticks from Query because of postgres.

## v0.5.0 [2020-10-30]

- Adds a new `QF` class to help reference aliases in a query.
- Bug fixes for rider.

## v0.4.8 [2020-10-27]

- Fix setting defaults for insert.
- Change fields to use backticks in query.
- Change default null from `False` to `True` for fields.

## v0.4.7 [2020-10-22]

- Remove need to specify name arg in Field.

## v0.4.6 [2020-10-21]

- Fix connection issues with non-pooled databases.
- Fix `mogrify` for SQLite.

## v0.4.5 [2020-10-19]

- Fix `rider migrate`.
- Fix `Query.order_by`.

## v0.4.4 [2020-10-16]

- Add rollbacks to rider with additional params to `step`.
- Change `rider create` arg from `-n, --name` to `-m, --message`.

## v0.4.3 [2020-10-15]

- Add `repr` to view unformatted queries.

## v0.4.2 [2020-10-14]

- Add rider as a console script.

## v0.4.1 [2020-10-14]

- Add `add_op` and `add_fn` to extend `op`/`fn` modules.
- Add `ilike` function for MySQL and SQLite.
- Require `ilike` and `like` to specify placeholders.
  - E.g `op.like(Contact.name, "astolfo")` becomes `op.like(Contact.name, "%astolfo%")`.
- Fix characters being stripped unintentionally.

## v0.4.0 [2020-10-13]

Release for Rider migration tool.

- Add docs for Rider.
- Fix update/insert by pk.

## v0.3.3 [2020-10-12]

- Add update + delete by pk.
- Fix updating a schemas' field to `None`.

## v0.3.2 [2020-09-10]

- Fix `Query.delete` to accept correct amount of arguments.

## v0.3.1 [2020-09-09]

- Fix Schema update and insert.

## v0.3.0 [2020-09-09]

First stable release for Estoult.

- Add all necessary functions.
- Add `apocryphan` connection pool.
