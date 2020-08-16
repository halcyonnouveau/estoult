# Estoult

[![PyPI](https://img.shields.io/pypi/v/estoult)](https://pypi.org/project/estoult/)
[![Documentation Status](https://readthedocs.org/projects/estoult/badge/?version=latest)](https://estoult.readthedocs.io/en/latest/?badge=latest)

Estoult is a Python toolkit for data mapping with an integrated query builder for SQL databases. It currently supports MySQL, PostgreSQL, and SQLite.

Features:

- **Not an ORM:** Estoult treats the data, not objects, as first class citizens.
- **No DSL:** Query building is done using functions instead of overriding Python operators.
- **Composable (sub)queries:** Create subqueries and store them for later use.
- **Easy debugging:** Display any generated SQL in a readable format.
- **Performant as raw SQL:** Estoult is **NOT** an ORM.

Estoult only works with Python 3.6+.

## Installation

Install Estoult through pip:

```
pip install estoult
```

## Documentation

Check the [documentation](https://estoult.readthedocs.io/en/latest/) for help.

## License

Estoult is licensed under the MIT license (see [LICENSE file](/LICENSE)).
