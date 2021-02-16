![la black luna](https://raw.githubusercontent.com/halcyonnouveau/estoult/master/docs/la_black_luna.png)

# Estoult

[![PyPI](https://img.shields.io/pypi/v/estoult)](https://pypi.org/project/estoult/)
[![Documentation Status](https://readthedocs.org/projects/estoult/badge/?version=latest)](https://estoult.readthedocs.io/en/latest/?badge=latest)

Estoult is a Python toolkit for data mapping with an integrated query builder for SQL databases. It currently supports MySQL, PostgreSQL, and SQLite.

Features:

- Not an ORM. Estoult doesn't attempt to apply relational algebra to objects.
- Concise and composable (sub)queries.
- Easy debugging by displaying any generated SQL in a readable format.
- Performant as raw SQL. Estoult is **NOT** an ORM.

Estoult only works with Python 3.6+ and is primarily tested on Python 3.8+.

## Installation

Install Estoult through pip:

```
pip install estoult
```

## Documentation

Check the [documentation](https://estoult.readthedocs.io/en/latest/) for help and [getting started](https://estoult.readthedocs.io/en/latest/getting_started.html).

## Contributing

If you have found a bug or would like to see a feature added to Estoult, please submit an issue or a pull request! Likewise if you found something in the documentation unclear or imprecise.

## Tests

Tests are run with [pytest](https://docs.pytest.org/en/stable/). Install it using pip:

```
pip install pytest
```

Run tests from the shell:

```
pytest
```

## License

Estoult is licensed under the MIT license (see [LICENSE file](/LICENSE)).
