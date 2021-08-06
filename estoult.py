import sys
import io

from importlib import import_module
from itertools import product
from enum import Enum
from copy import deepcopy
from collections import namedtuple
from contextlib import contextmanager
from typing import Any, Optional

try:
    import sqlite3
except ImportError:
    sqlite3 = None

try:
    import psycopg2
except ImportError:
    psycopg2 = None

try:
    import MySQLdb as mysql
except ImportError:
    mysql = None


__version__ = "0.7.7"
__all__ = [
    "Association",
    "Field",
    "fn",
    "MySQLDatabase",
    "op",
    "PostgreSQLDatabase",
    "Schema",
    "SQLiteDatabase",
    "qf",
    "Query",
]


class EstoultError(Exception):
    pass


class ClauseError(EstoultError):
    pass


class FieldError(EstoultError):
    pass


class QueryError(EstoultError):
    pass


class DatabaseError(EstoultError):
    pass


class AssociationError(EstoultError):
    pass


_sql_ops = {
    "eq": "=",
    "lt": "<",
    "le": "<=",
    "gt": ">",
    "ge": ">=",
    "ne": "<>",
    "add": "+",
    "sub": "-",
    "mul": "*",
    "truediv": "/",
    "mod": "%",
}


def _parse_arg(arg):
    if isinstance(arg, Clause):
        return arg
    elif isinstance(arg, Field):
        return str(arg), ()
    elif isinstance(arg, Query):
        return arg._query, arg._params
    elif isinstance(arg, list) or isinstance(arg, tuple):
        placeholders = ", ".join(["%s"] * len(arg))
        return placeholders, tuple(arg)

    return "%s", (arg,)


def _parse_args(func):
    def wrapper(*args):
        return func(*[_parse_arg(a) for a in args])

    return wrapper


def _strip(string):
    string = string.rstrip(" ,")

    if string.endswith("and"):
        string = string[:-3]

    return string


def _make_op(operator):
    @_parse_args
    def wrapper(lhs, rhs):
        return Clause(f"({lhs[0]}) {operator} ({rhs[0]})", tuple(lhs[1] + rhs[1]))

    return wrapper


def _make_fn(name):
    def wrapper(*args):
        return Clause(f"{name}({str(', '.join([str(a) for a in args]))})", ())

    return wrapper


class ClauseMetaclass(type):
    def __new__(cls, clsname, bases, attrs):
        # Add op overloading
        for name, operator in _sql_ops.items():
            attrs[f"__{name}__"] = staticmethod(_make_op(operator))

        return super(ClauseMetaclass, cls).__new__(cls, clsname, bases, attrs)


class Clause(namedtuple("Clause", ["clause", "params"]), metaclass=ClauseMetaclass):
    def __str__(self):
        return self.clause

    def __hash__(self):
        return hash(str(self))

    def __eq__(self, comp):
        return str(self) == comp


class OperatorMetaclass(type):
    def __new__(cls, clsname, bases, attrs):
        for name, operator in _sql_ops.items():
            attrs[name] = staticmethod(_make_op(operator))

        c = super(OperatorMetaclass, cls).__new__(cls, clsname, bases, attrs)

        c.add_op("or_", "or")
        c.add_op("and_", "and")
        c.add_op("in_", "in")
        c.add_op("like", "like")

        return c


class op(metaclass=OperatorMetaclass):
    @classmethod
    def add_op(cls, name, op):
        """
        Adds an operator to the module.

        :param name: What the name of the function should be called.
        :type name: str
        :param op: The SQL operator it is turned into.
        :type op: str
        """

        def func(lhs, rhs):
            fn = _make_op(op)
            return fn(lhs, rhs)

        setattr(cls, name, staticmethod(func))

    @staticmethod
    @_parse_args
    def ilike(lhs, rhs):
        # Does a case insensitive `like`. Only postgres has this operator,
        # but we can hack it together for the others
        if psycopg2:
            return Clause(f"({lhs[0]}) ilike ({rhs[0]})", (lhs[1] + rhs[1]))

        return Clause(f"lower({lhs[0]}) like lower({rhs[0]})", (lhs[1] + rhs[1]))

    @staticmethod
    @_parse_args
    def not_(arg):
        return Clause(f"not ({arg[0]})", (arg[1]))

    @staticmethod
    @_parse_args
    def is_null(arg):
        return Clause(f"({arg[0]}) is null", (arg[1]))

    @staticmethod
    @_parse_args
    def not_null(arg):
        return Clause(f"({arg[0]}) is not null", (arg[1]))


class FunctionMetaclass(type):

    sql_fns = [
        "count",
        "sum",
        "avg",
        "ceil",
        "distinct",
        "concat",
        "max",
        "min",
    ]

    def __new__(cls, clsname, bases, attrs):
        for f in cls.sql_fns:
            attrs[f] = staticmethod(_make_fn(f))

        return super(FunctionMetaclass, cls).__new__(cls, clsname, bases, attrs)


class fn(metaclass=FunctionMetaclass):
    @classmethod
    def add_fn(cls, name, sql_fn):
        """
        Adds an additional function to the module.

        :param name: What the name of the function should be called.
        :type name: str
        :param sql_fn: The SQL function it is turned into.
        :type sql_fn: str
        """

        def func(*args):
            fn = _make_fn(sql_fn)
            return fn(*args)

        setattr(cls, name, staticmethod(func))

    @staticmethod
    def alias(lhs, rhs):
        s, p = _parse_arg(lhs)
        return Clause(f"{s} as {rhs}", tuple(p))

    @staticmethod
    def cast(lhs, rhs):
        s, p = _parse_arg(lhs)
        return Clause(f"cast({s} as {rhs})", tuple(p))

    @staticmethod
    def wild(schema):
        """
        Select a schema with wildcard.

        :param schema: The schema.
        :type schema: Schema
        """
        if schema.allow_wildcard_select is False:
            raise QueryError(
                "Wildcard selects are disabled for schema: "
                f"`{schema.__tablename__}`"
                ", please specify fields."
            )

        return Clause(f"{schema.__tablename__}.*", ())


class FieldMetaclass(type):
    def __new__(cls, clsname, bases, attrs):
        # Add op overloading
        for name, operator in _sql_ops.items():
            attrs[f"__{name}__"] = _make_op(operator)

        return super(FieldMetaclass, cls).__new__(cls, clsname, bases, attrs)


class Field(metaclass=FieldMetaclass):
    """
    A schema field, analogous to columns on a table.

    :param type: Basic datatype of the field, used to cast values into the database.
    :type type: type
    :param name: The column name of the field, will default to the variable name of the
                 field.
    :type name: str, optional
    :param caster: A specified caster type/function for more extensive casting.
    :type caster: callable, optional
    :param null: Field allows nulls.
    :type null: bool, optional
    :param default: Default value.
    :type default: optional
    :param primary_key: Field is the primary key.
    :type primary_key: bool, optional
    """

    def __init__(
        self, type, name=None, caster=None, null=True, default=None, primary_key=False
    ):
        self.schema: Optional[Schema] = None
        self.type: str = type
        self.name: Optional[str] = name

        self.caster = caster
        self.null = null
        self.default = default
        self.primary_key = primary_key

    @property
    def full_name(self):
        return f"{self.schema.__tablename__}.{self.name}"

    def __str__(self):
        return self.full_name

    def __hash__(self):
        return hash(str(self))

    def __repr__(self):
        return (
            f"<Field {self.type} name={self.name} caster={self.caster} "
            f"null={self.null} default={self.default} "
            f"primary_key={self.primary_key}>"
        )


class qf(Field):
    """
    Query field - an extra user defined field used for queries.
    This is mainly needed for referencing aliases.

    :param name: The name of the field.
    :type name: str
    """

    def __init__(self, name):
        self.name = name

    @property
    def full_name(self):
        return f"{self.name}"

    def __repr__(self):
        return f"<qf name={self.name}>"


class _Cardinals(Enum):
    ONE_TO_ONE = 1
    ONE_TO_MANY = 2


class _Association:
    def __init__(self, cardinality, name, schema, owner, field):
        self.cardinality = cardinality
        self.name = name
        self.owner = owner
        self.field = field

        self._lazy_schema = schema

    @property
    def schema(self):
        if isinstance(self._lazy_schema, str):
            [module, cls] = self._lazy_schema.rsplit('.', 1)
            try:
                self._lazy_schema = getattr(import_module(module), cls)
            except (AttributeError, ModuleNotFoundError):
                raise AssociationError(f"Could not import schema: {self._lazy_schema}")

        return self._lazy_schema


class Association:
    """
    One to One/Many associations to help translate between relational data and object
    data.

    Many to Many is currently not supported because it does not translate well into
    an object structure.
    """

    @staticmethod
    def has_one(schema, on=[]):
        return _Association(_Cardinals.ONE_TO_ONE, None, schema, on[0], on[1])

    @staticmethod
    def has_many(schema, on=[]):
        return _Association(_Cardinals.ONE_TO_MANY, None, schema, on[0], on[1])


class SchemaMetaclass(type):
    def __new__(cls, clsname, bases, attrs):
        # Deepcopy inherited fields
        for base in bases:
            at = dir(base)

            for a in at:
                f = getattr(base, a)

                if isinstance(f, Field):
                    attrs[a] = deepcopy(f)

        c = super(SchemaMetaclass, cls).__new__(cls, clsname, bases, attrs)

        for key in dir(c):
            f = getattr(c, key)

            if isinstance(f, Field):
                # Reference schema in fields
                f.schema = c

                # Set name to var reference
                if f.name is None:
                    f.name = key

            if isinstance(f, _Association):
                f.name = key

        return c

    @property
    def fields(cls):
        return [
            getattr(cls, key)
            for key in dir(cls)
            if isinstance(getattr(cls, key), Field)
        ]

    @property
    def associations(cls):
        return [
            getattr(cls, key)
            for key in dir(cls)
            if isinstance(getattr(cls, key), _Association)
        ]

    @property
    def pk(cls):
        pk = None

        for field in cls.fields:
            if field.primary_key is True:
                return field

            if field.name == "id":
                pk = field

        return pk

    def __getitem__(cls, item):
        return getattr(cls, item)


class Schema(metaclass=SchemaMetaclass):
    """
    A schema representation of a database table.

    :ivar allow_wildcard_select: Determines if wildcards can be used when 'selecting'.
    """

    _database_: Any = None
    __tablename__ = None

    allow_wildcard_select = True

    @classmethod
    def _cast(cls, updating, row):
        # Allow you to use a Field as key
        for key, value in list(row.items()):
            if isinstance(key, Field):
                row[key.name] = value
            else:
                row[key] = value

        changeset = {}

        for field in cls.fields:
            value = None

            try:
                # Try to get the value from the row
                # In a try/catch so we can tell the difference between
                # >>> row["field"] == None  # Field is set to `None`
                # >>> row.get("field") == None  # Field is not set
                value = row[field.name]
            except KeyError:
                if updating is True:
                    continue

                if field.default is None:
                    continue

            # Apply a default if we are inserting
            if value is None and updating is False and field.default is not None:
                if callable(field.default) is True:
                    value = field.default()
                else:
                    value = field.default

            # Cast the value
            if value is not None:
                value = (
                    field.type(value) if field.caster is None else field.caster(value)
                )

            changeset[field.name] = value

        return changeset

    @classmethod
    def _validate(cls, updating, row):
        changeset = {}

        for field in cls.fields:
            try:
                value = row[field.name]
            except KeyError:
                continue

            if field.null is False and value is None and updating is True:
                raise FieldError(f"{str(field)} cannot be None")

            changeset[field.name] = value

        return changeset

    @classmethod
    def _casval(cls, row, updating):
        changeset = cls._cast(updating, row)
        changeset = cls._validate(updating, changeset)

        # A user specified validation function
        validate_func = getattr(cls, "validate", lambda _, x: x)
        changeset = validate_func(updating, changeset)

        return changeset

    @classmethod
    def _get_field_by_name(cls, name: Any):
        # BIG HACK OH NO
        if isinstance(name, Field):
            name = name.name
        return getattr(cls, name, None)

    @classmethod
    def _is_association(cls, name):
        return isinstance(cls._get_field_by_name(name), _Association)

    @classmethod
    def _pop_associations(cls, obj):
        return {
            cls._get_field_by_name(k): obj.pop(k)
            for k in [
                key for key in obj.keys() if cls._is_association(key) and obj[key]
            ]
        }

    @classmethod
    def insert(cls, obj):
        associations = cls._pop_associations(obj)
        changeset = cls._casval(obj, updating=False)

        params = list(changeset.values())
        fields = ", ".join(changeset.keys())
        placeholders = ", ".join(["%s"] * len(changeset))

        sql = f"insert into {cls.__tablename__} (%s) values (%s)" % (
            fields,
            placeholders,
        )

        if psycopg2 is not None and cls.pk:
            sql += f" returning {cls.pk.name}"

        pk = cls._database_.insert(_strip(sql), params)

        if cls.pk:
            changeset[cls.pk.name] = pk

        if associations:
            changeset_asos = {}

            for aso, value in associations.items():
                changeset, changeset_asos[aso.name] = _do_association(
                    changeset, cls, aso, value
                )

            changeset = {**changeset, **changeset_asos}

        return changeset

    @classmethod
    def update(cls, old, new):
        obj = {**old, **new}
        associations = cls._pop_associations(obj)

        # Pop from old
        old_ks = [k for k in old.keys()]
        for k in old_ks:
            if cls._is_association(k):
                old.pop(k, None)

        changeset = cls._casval(obj, updating=True)

        sql = f"update {cls.__tablename__} set "
        params = []

        for key, value in changeset.items():
            sql += f"{key} = %s, "
            params.append(value)

        sql = f"{_strip(sql)} where "

        for key, value in old.items():
            sql += f"{key} = %s and "
            params.append(value)

        cls._database_.sql(_strip(sql), params)

        if associations:
            changeset_asos = {}

            for aso, value in associations.items():
                changeset, changeset_asos[aso.name] = _do_association(
                    changeset, cls, aso, value
                )

            changeset = {**changeset, **changeset_asos}

        return changeset

    @classmethod
    def update_by_pk(cls, id, new):
        return cls.update({cls.pk.name: id}, new)

    @classmethod
    def delete(cls, row):
        # Deletes single row - look at `Query` for batch
        sql = f"delete from {cls.__tablename__} where "
        params = []

        for key, value in row.items():
            sql += f"{key} = %s and "
            params.append(value)

        return cls._database_.sql(_strip(sql), params)

    @classmethod
    def delete_by_pk(cls, id, new):
        return cls.delete({cls.pk.name: id})


class QueryMetaclass(type):

    sql_joins = [
        "inner join",
        "left join",
        "left outer join",
        "right join",
        "right outer join",
        "full join",
        "full outer join",
    ]

    @staticmethod
    def make_join_fn(join_type):
        def join_fn(self, schema, on):
            q = f"{str(on[0])} = {str(on[1])}"
            self._add_node(f"{join_type} {schema.__tablename__} on {q}", ())
            return self

        return join_fn

    def __new__(cls, clsname, bases, attrs):
        for join_type in cls.sql_joins:
            attrs[join_type.replace(" ", "_")] = QueryMetaclass.make_join_fn(join_type)

        return super(QueryMetaclass, cls).__new__(cls, clsname, bases, attrs)


Node = namedtuple("Node", ["node", "params"])


class Query(metaclass=QueryMetaclass):
    def __init__(self, schema):
        self.schema = schema

        self._method: Optional[str] = None
        self._nodes = []
        self._preloads = []

    def _add_node(self, node, params):
        self._nodes.append(Node(_strip(node), params))

    @property
    def _query(self):
        return " ".join([x.node for x in self._nodes])

    @property
    def _params(self):
        return tuple([p for x in self._nodes for p in x.params])

    def select(self, *args):
        self._method = "select"

        query = ""
        params = []

        if len(args) < 1:
            if self.schema.allow_wildcard_select is False:
                raise QueryError(
                    "Wildcard selects are disabled for schema: "
                    f"`{self.schema.__tablename__}`"
                    ", please specify fields."
                )

            query += "*"
        else:
            for arg in args:
                if isinstance(arg, Clause):
                    string, p = arg
                    query += f"{string}, "
                    params.extend(p)
                else:
                    query += f"{arg}, "

        self._add_node(
            f"select {_strip(query)} from {self.schema.__tablename__}", params
        )

        return self

    def update(self, changeset):
        self._method = "sql"

        changeset = self.schema._casval(changeset, updating=True)

        query = ""
        params = []

        for key, value in changeset.items():
            query += f"{key} = %s, "
            params.append(value)

        self._add_node(f"update {self.schema.__tablename__} set {query}", params)

        return self

    def delete(self):
        self._method = "sql"
        self._add_node(f"delete from {self.schema.__tablename__}", ())
        return self

    def get(self, *args):
        self.select(*args)
        self._method = "get"
        return self

    def get_or_none(self, *args):
        self.select(*args)
        self._method = "get_or_none"
        return self

    def union(self, schema):
        self._add_node("union", ())
        self.schema = schema
        return self

    def where(self, *clauses):
        query = ""
        params = []

        for clause in clauses:
            string, p = clause

            # We can always add an `and` to the end cus it get stripped off ;)
            query += f"{string} and "
            params.extend(p)

        self._add_node(f"where {query}", params)

        return self

    def limit(self, *args):
        # Example: .limit(1) or limit(1, 2)
        if len(args) == 1:
            self._add_node("limit %s", args)
        elif len(args) == 2:
            # `offset` works in mysql and postgres
            self._add_node("limit %s offset %s", args)
        else:
            raise QueryError("`limit` has too many arguments")

        return self

    def order_by(self, *args):
        # Example: .order_by(Frog.id, {Frog.name: "desc"})
        query = "order by "
        params = []

        for a in args:
            v = None

            if isinstance(a, dict):
                k, v = next(iter(a.items()))

                if v != "asc" and v != "desc":
                    raise QueryError("Value must be 'asc' or 'desc'")
            else:
                k = a

            if isinstance(k, Clause):
                c, p = _parse_arg(k)
                query += "%s " % c
                params.extend(p)
            elif isinstance(k, Field):
                query += f"{k} "
            else:
                query += "%s "
                params.append(str(k))

            if v:
                query += f"{v}, "

        self._add_node(f"{query}", params)

        return self

    def preload(self, association):
        self._preloads.append(association)
        return self

    def execute(self) -> Any:
        if self._method is None:
            raise QueryError("No method")

        func = getattr(self.schema._database_, self._method)
        data = func(self._query, self._params)

        if data is None:
            return data

        for association, row in product(
            self._preloads, data if isinstance(data, list) else [data]
        ):
            key, new_row = _do_preload(self.schema._database_, association, row)
            row[key] = new_row

        return data

    def copy(self):
        return deepcopy(self)

    def __str__(self):
        return (
            self.schema._database_.mogrify(self._query, self._params)
            .decode("utf-8")
            .strip()
        )

    def __repr__(self):
        return f'<Query query="{self._query}" params={self._params}>'


def _do_association_update(row, schema, association, obj):
    aso_schema = association.schema
    pk_name = aso_schema.pk.name

    updating = pk_name in obj.keys()

    # Make sure association is always linked to our row
    obj[association.field] = row.get(association.owner)

    if updating is True:
        # Update the association
        obj = aso_schema.update({pk_name: obj[pk_name]}, obj)
        id = obj[pk_name]

        # If the schema is not associated with it, do it now
        aso_on = row.get(association.owner)
        row[association.owner] = id

        if id != aso_on:
            row = schema.update({schema.pk.name: row[schema.pk.name]}, row)
    else:
        # Insert the new association
        obj = aso_schema.insert(obj)
        # Update the previous schema to include the new association
        row = schema.update(row, {association.owner: obj[association.field]})

    return row, obj


def _do_association(row, schema, association, obj):
    if association.cardinality == _Cardinals.ONE_TO_ONE:
        return _do_association_update(row, schema, association, obj)
    else:
        # if association.cardinality == _Cardinals.ONE_TO_MANY:
        new_objs = []
        for o in obj:
            row, new = _do_association_update(row, schema, association, o)
            new_objs.append(new)

        return row, new_objs


def _do_preload_query(db, cardinality, query, value):
    if cardinality == _Cardinals.ONE_TO_ONE:
        return db.get_or_none(query, (value,))
    elif cardinality == _Cardinals.ONE_TO_MANY:
        return db.select(query, (value,))

    raise AssociationError("Association has unknown cardinality")


def _do_preload(db, association, row):
    # If the association is just an association, then we can preload it without any
    # issues
    if isinstance(association, _Association):
        if association.schema.allow_wildcard_select is False:
            raise QueryError(
                "Wildcard selects are disabled for schema: "
                f"`{association.schema.__tablename__}`"
                ", please specify fields."
            )

        query = f"""
            select * from {association.schema.__tablename__}
            where {association.field} = %s
        """

        return association.name, _do_preload_query(
            db, association.cardinality, query, row[association.owner]
        )

    # Otherwise, associations can be dicts or lists and we need to recurse through them
    aso, values = list(association.items())[0]

    if row.get(aso.owner) is None:
        return aso.name, None

    associations = [
        v for v in values if isinstance(v, _Association) or isinstance(v, dict)
    ]

    fields = [v.name for v in values if isinstance(v, Field) and v.name is not None]
    select = ", ".join(fields) if len(fields) > 0 else "*"

    if aso.schema.allow_wildcard_select is False and select == "*":
        raise QueryError(
            "Wildcard selects are disabled for schema: "
            f"`{aso.schema.__tablename__}`"
            ", please specify fields."
        )

    query = f"""
        select {select} from {aso.schema.__tablename__}
        where {aso.field} = %s
    """

    new_row = _do_preload_query(db, aso.cardinality, query, row[aso.owner])

    # If there's nothing associated with it, then just move on
    if new_row is None or new_row == []:
        return aso.name, new_row

    for field_aso in associations:
        name, field = _do_preload(db, field_aso, new_row)
        new_row[name] = field

    return aso.name, new_row


def _replace_placeholders(func):
    def wrapper(self, query, *args, **kwargs):
        query = query.replace("%s", self.placeholder)
        return func(self, query, *args, **kwargs)

    return wrapper


def _get_connection(func):
    def wrapper(self, *args, **kwargs):
        if self.autoconnect is True:
            self.connect()

        if self.is_trans is False:
            self._new_cursor()

        f = func(self, *args, **kwargs)

        if self.autoconnect is True and self.is_trans is False:
            self.close()

        return f

    return wrapper


class Database:
    def __init__(self, autoconnect=True, *args, **kwargs):
        self.autoconnect = autoconnect

        self.Schema = Schema
        self.Schema._database_ = self

        self._conn = None
        self._cursor = None
        self.is_trans = False

        self.cargs = args
        self.ckwargs = kwargs

    def connect(self):
        self._conn = self._connect()

    @property
    def conn(self):
        return self._conn

    def _close(self):
        self._conn.close()

    def close(self):
        return self._close()

    def _new_cursor(self):
        self._cursor = self.conn.cursor()

    @property
    def cursor(self):
        if self._cursor is None:
            self._cursor = self.conn.cursor()

        return self._cursor

    @contextmanager
    def atomic(self, commit=True):
        # estoult says trans rights
        self.is_trans = True

        try:
            yield
        except Exception as err:
            self.conn.rollback()
            raise err
        else:
            if commit:
                self.conn.commit()
            else:
                self.conn.rollback()
        finally:
            self.is_trans = False

            if self.autoconnect is True:
                self.close()

    def _execute(self, query, params):
        self.cursor.execute(query, params)

        if self.is_trans is False:
            self.conn.commit()

    @_get_connection
    def sql(self, query, params):
        return self._execute(query, params)

    @_get_connection
    def select(self, query, params):
        self._execute(query, params)
        cols = [col[0] for col in self.cursor.description]
        return [dict(zip(cols, row)) for row in self.cursor.fetchall()]

    @_get_connection
    def insert(self, query, params):
        self._execute(query, params)

        if psycopg2 is not None:
            # Right now 'returning' is not supported and only used for
            # getting the primary key back, this needs to be changed when we
            # fully support it
            words = query.split(" ")
            if words[-2] == "returning":
                return self.cursor.fetchone()[0]
            else:
                return None

        return self.cursor.lastrowid

    def get(self, query, params):
        row = self.select(query, params)
        return row[0]

    def get_or_none(self, query, params):
        try:
            return self.get(query, params)
        except IndexError:
            return None


class MySQLDatabase(Database):
    def __init__(self, *args, **kwargs):
        self.placeholder = "%s"

        super().__init__(*args, **kwargs)

    def _connect(self):
        return mysql.connect(*self.cargs, **self.ckwargs)

    @_get_connection
    def mogrify(self, query, params):
        with self.atomic(commit=False):
            self._execute(query, params)
            return self.cursor._executed


class PostgreSQLDatabase(Database):
    def __init__(self, *args, **kwargs):
        self.placeholder = "%s"

        super().__init__(*args, **kwargs)

    def _connect(self):
        return psycopg2.connect(*self.cargs, **self.ckwargs)

    @_get_connection
    def mogrify(self, query, params):
        return self.cursor.mogrify(query, params)


class SQLiteDatabase(Database):
    def __init__(self, *args, **kwargs):
        self.placeholder = "?"

        super().__init__(*args, **kwargs)

    def _connect(self):
        return sqlite3.connect(*self.cargs, **self.ckwargs)

    @_replace_placeholders
    def _execute(self, *args, **kwargs):
        return super()._execute(*args, **kwargs)

    @_get_connection
    def mogrify(self, query, params):
        with self.atomic(commit=False):
            # SQLite doesn't have a thing to return the executed statement.
            # But we **can** print it! So just capture that! :) FML

            # redirect sys.stdout to a buffer
            self.conn.set_trace_callback(print)
            stdout = sys.stdout
            sys.stdout = io.StringIO()

            self._execute(query, params)

            # get output and restore sys.stdout
            output = sys.stdout.getvalue()
            sys.stdout = stdout
            self.conn.set_trace_callback(None)

            return output.encode("utf-8")
