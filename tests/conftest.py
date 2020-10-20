import pytest

from .base import db_create, db_clean, db


@pytest.hookimpl()
def pytest_sessionstart(session):
    db_create()


@pytest.hookimpl()
def pytest_sessionfinish(session):
    db_clean()


@pytest.hookimpl()
def pytest_runtest_setup(item):
    db.connect()


@pytest.hookimpl()
def pytest_runtest_teardown(item):
    db.close()
