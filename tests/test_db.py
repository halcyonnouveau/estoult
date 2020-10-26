import uuid
from .base import db, User


def test_atomic_commit():
    name = uuid.uuid4().hex

    with db.atomic(commit=True):
        User.new(name=name)

    assert User.get_by_name(name) is not None


def test_atomic_no_commit():
    name = uuid.uuid4().hex

    with db.atomic(commit=False):
        User.new(name=name)

    assert User.get_by_name(name) is None
