.. estoult documentation master file, created by
   sphinx-quickstart on Sat Aug 15 22:49:51 2020.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Estoult
=======

Estoult is a Python toolkit for data mapping with an integrated query builder for SQL databases. It currently supports MySQL, PostgreSQL, and SQLite.

Features:

- Not an ORM: Estoult treats the data, not objects, as first class citizens.
- No DSL: Query building is done using functions instead of overriding Python operators.
- Composable (sub)queries: Create subqueries and store them for later use.
- Easy debugging: Display any generated SQL in a readable format.
- Performant as raw SQL: Estoult is NOT an ORM.

Estoult's source code is located at `GitHub <https://github.com/halcyonnouveau/estoult>`_.
