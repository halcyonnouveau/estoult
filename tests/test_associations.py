import copy

from estoult import Query
from .base import Organisation, Admin, User, recurse_replace


def test_has_one_get():
    org = (
        Query(Organisation)
        .get()
        .preload({Organisation.admin: [{Admin.user: [User.name]}]})
        .execute()
    )

    assert org.get("admin") is not None
    assert org["admin"].get("user") is not None


def test_has_many_get():
    org = Query(Organisation).get().preload(Organisation.users).execute()
    assert len(org.get("users")) > 0


def test_has_one_select():
    Query(Organisation).select().preload(Organisation.admin).execute()
    assert True


def test_has_many_select():
    Query(Organisation).select().preload(Organisation.users).execute()
    assert True


def test_insert_and_update():
    # TODO: Test without making Nones
    org_name = "Les Fans D'Astolfo"
    new_org = {
        "name": org_name,
        "admin": {"user": {"name": "Test Account"}},
        "users": [{"name": "Justin Duch"}, {"name": "Emilie Rousseau"}],
    }

    org = Organisation.insert(new_org)
    org_replaced = recurse_replace(copy.deepcopy(org))

    test = {
        "id": None,
        "name": "Les Fans D'Astolfo",
        "admin": {
            "id": None,
            "organisation_id": None,
            "user_id": None,
            "user": {"id": None, "name": "Test Account"},
        },
        "users": [
            {"name": "Justin Duch", "organisation_id": None, "id": None},
            {"name": "Emilie Rousseau", "organisation_id": None, "id": None},
        ],
    }

    assert org_replaced == test

    update_org = org
    update_org["admin"]["user"]["name"] = "Astolfo sui-même"
    update_org["users"].append({"name": "Kim Kitsuragi"})

    test["admin"]["user"]["name"] = "Astolfo sui-même"
    test["users"].append({"name": "Kim Kitsuragi", "organisation_id": None, "id": None})

    new_org = Organisation.update(org, update_org)

    assert recurse_replace(new_org) == test
