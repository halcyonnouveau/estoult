from copy import deepcopy
from collections import namedtuple
from contextlib import contextmanager

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


__version__ = "0.2.1"
__all__ = [
    "ClauseError",
    "Database",
    "EstoultError",
    "Field",
    "FieldError",
    "fn",
    "op",
    "Query",
]


class EstoultError(Exception):
    pass


class ClauseError(EstoultError):
    pass


class FieldError(EstoultError):
    pass


Subquery = namedtuple("Subquery", ["query", "params"])
Clause = namedtuple("Clause", ["clause", "params"])
ConditionalClause = namedtuple("ConditionalClause", ["conditional", "params"])
OperatorClause = namedtuple("OperatorClause", ["operator", "operand"])


class InOperatorClause(OperatorClause):
    pass


def _parse_clause(clause):
    if isinstance(clause, set):
        clause = clause.pop()

    if isinstance(clause, ConditionalClause):
        return Clause(clause.conditional + " ", clause.params)

    if isinstance(clause, dict):
        # An unparsed clause is a dict with one key/value. E.g:
        # {User.email: "email@mail.com"}
        # In a `where` function you would add multiple clauses like this:
        # > .where({User.name: "beanpuppy"}, {User.archive: 0})
        # This makes the following SQL:
        # `where User.name = "beanpuppy" and User.archive = 0`
        if len(clause.keys()) > 1:
            raise ClauseError("Clause can only have one key/value pair")

        key, value = list(clause.items())[0]

        if isinstance(value, OperatorClause):
            # This is normally a clause from the operator class:
            # > {Person.id: op.gt(1)}
            string = f"{str(key)} {value.operator}"

            if isinstance(value.operand, Subquery):
                string += " " + value.operand.query
                params = value.operand.params
            else:
                params = (
                    value.operand
                    if isinstance(value, InOperatorClause)
                    else (value.operand,)
                )
        else:
            # The default way clauses are:
            # > {Person.id: 1}
            string = f"{str(key)} = %s"
            params = (value,)

        return Clause(string + " ", params)

    raise ClauseError(f"Clause structure is incorrect: {str(clause)}")


def _strip(string):
    return string.rstrip(" ").rstrip(",").rstrip("and")


class FunctionMetaclass(type):

    sql_fns = [
        "count",
        "sum",
        "avg",
        "ceil",
        "distinct",
        "concat",
    ]

    @staticmethod
    def make_sql_fn(name):
        def sql_fn(*args):
            return f"{name}({str(', '.join([str(a) for a in args]))})"

        return sql_fn

    def __new__(cls, clsname, bases, attrs):
        for f in cls.sql_fns:
            attrs[f] = FunctionMetaclass.make_sql_fn(f)

        return super(FunctionMetaclass, cls).__new__(cls, clsname, bases, attrs)


class fn(metaclass=FunctionMetaclass):
    @classmethod
    def alias(cls, field, value):
        return f"{field} as {value}"

    @classmethod
    def wild(cls, schema):
        return f"{schema.__tablename__}.*"


class OperatorMetaclass(type):

    sql_ops = {
        "eq": "=",
        "lt": "<",
        "le": "<=",
        "gt": ">",
        "ge": ">=",
        "ne": "<>",
    }

    @staticmethod
    def make_fn(operator):
        def op_fn(value):
            return OperatorClause(f"{operator} %s", value)

        return op_fn

    def __new__(cls, clsname, bases, attrs):
        for name, operator in cls.sql_ops.items():
            attrs[name] = OperatorMetaclass.make_fn(operator)

        return super(OperatorMetaclass, cls).__new__(cls, clsname, bases, attrs)


class op(metaclass=OperatorMetaclass):
    @staticmethod
    def _clause_args(func):
        def wrapper(cls, *args):
            args = [_parse_clause(a) for a in args]
            return func(cls, *args)

        return wrapper

    @classmethod
    @_clause_args.__func__
    def or_(cls, cond_1, cond_2):
        return ConditionalClause(
            f"({_strip(cond_1[0])} or {_strip(cond_2[0])})", (*cond_1[1], *cond_2[1]),
        )

    @classmethod
    @_clause_args.__func__
    def and_(cls, cond_1, cond_2):
        return ConditionalClause(
            f"({_strip(cond_1[0])} and {_strip(cond_2[0])})", (*cond_1[1], *cond_2[1]),
        )

    @classmethod
    def in_(cls, value):
        # `in` gets it's own special clause handling
        if isinstance(value, Subquery):
            return InOperatorClause("in", value)

        if isinstance(value, list) or isinstance(value, tuple):
            placeholders = ", ".join(["%s"] * len(value))
            return InOperatorClause(f"in ({placeholders})", value)

        raise ClauseError("`in` value can only be `subquery`, `list`, or `tuple`")

    @classmethod
    def like(cls, value):
        arg = f"%{value}%"
        return OperatorClause("like %s", (arg))

    @classmethod
    def ilike(cls, value):
        arg = f"%{value}%"
        return OperatorClause("ilike %s", (arg))

    @classmethod
    def not_(cls, field):
        return ConditionalClause(f"not {str(field)}", ())

    @classmethod
    def is_null(cls, field):
        return ConditionalClause(f"{str(field)} is null", ())

    @classmethod
    def not_null(cls, field):
        return ConditionalClause(f"{str(field)} is not null", ())


class FieldMetaclass(type):
    @staticmethod
    def make_fn(operator):
        def op_fn(cls, value):
            return ConditionalClause(f"{cls.full_name} {operator} %s", (value,))

        return op_fn

    def __new__(cls, clsname, bases, attrs):
        for name, operator in OperatorMetaclass.sql_ops.items():
            attrs[f"__{name}__"] = FieldMetaclass.make_fn(operator)

        return super(FieldMetaclass, cls).__new__(cls, clsname, bases, attrs)


class Field(metaclass=FieldMetaclass):
    def __init__(self, type, name, **kwargs):
        self.type = type
        self.name = name

        self.caster = kwargs.get("caster")

        self.null = kwargs.get("null")
        self.default = kwargs.get("default")
        self.primary_key = kwargs.get("primary_key") is True

    @property
    def full_name(self):
        return f"{self.schema.__tablename__}.{self.name}"

    def __str__(self):
        return self.full_name

    def __hash__(self):
        return hash(str(self))

    def __eq__(self, comp):
        return str(self) == comp


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

        # Add schema to fields
        for key in dir(c):
            f = getattr(c, key)

            if isinstance(f, Field):
                f.schema = c

        return c

    @property
    def fields(cls):
        return [
            getattr(cls, key)
            for key in dir(cls)
            if isinstance(getattr(cls, key), Field)
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


class Schema(metaclass=SchemaMetaclass):

    _database_ = None
    __tablename__ = None

    @classmethod
    def _cast(cls, row):
        # Allow you to use a Field as key
        for key, value in list(row.items()):
            if isinstance(key, Field):
                row[key.name] = value
            else:
                row[key] = value

        changeset = {}
        updating = row.get(cls.pk.name) is not None

        for field in cls.fields:
            value = row.get(field.name)

            if value is None and field.name == cls.pk.name:
                continue

            if value is not None:
                value = (
                    field.type(value) if field.caster is None else field.caster(value)
                )

            if field.default is not None and updating is False:
                value = field.default

            changeset[field.name] = value

        return changeset

    @classmethod
    def _validate(cls, row):
        changeset = {}
        updating = row.get(cls.pk.name) is not None

        for field in cls.fields:
            value = row.get(field.name)

            if value is None:
                continue

            if field.null is False and value is None and updating is True:
                raise FieldError(f"{str(field)} cannot be None")

            changeset[field.name] = value

        return changeset

    @classmethod
    def casval(cls, row):
        changeset = cls._cast(row)
        changeset = cls._validate(changeset)

        # A user specified validation function
        validate_func = getattr(cls, "validate", lambda x: x)
        changeset = validate_func(changeset)

        return changeset

    @classmethod
    def insert(cls, obj):
        changeset = cls.casval(obj)

        params = list(changeset.values())
        fields = ", ".join(changeset.keys())
        placeholders = ", ".join(["%s"] * len(changeset))

        sql = f"insert into {cls.__tablename__} (%s) values (%s)\n" % (
            fields,
            placeholders,
        )

        if psycopg2 is not None:
            sql += f"returning {cls.pk.name}\n"

        return cls._database_.insert(_strip(sql), params)

    @classmethod
    def update(cls, old, new):
        # This updates a single row only, if you want to update several
        # use `update` in `Query`
        changeset = cls.casval({**old, **new})
        sql = f"update {cls.__tablename__} set "
        params = []

        for key, value in changeset.items():
            params.append(str(value))
            sql += f"{str(key)} = %s, "

        sql = f"{_strip(sql)} where {str(cls.pk)} = %s"

        params.append(changeset[cls.pk.name])

        return cls._database_.sql(sql, params)

    @classmethod
    def delete(cls, row):
        # Deletes single row - look at `Query` for batch
        sql = f"delete from {cls.__tablename__} where {str(cls.pk)} = %s"
        return cls._database_.sql(sql, [row[cls.pk.name]])


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
            self._query += f"{join_type} {schema.__tablename__} on {q}\n"

            return self

        return join_fn

    def __new__(cls, clsname, bases, attrs):
        for join_type in cls.sql_joins:
            attrs[join_type.replace(" ", "_")] = QueryMetaclass.make_join_fn(join_type)

        return super(QueryMetaclass, cls).__new__(cls, clsname, bases, attrs)


class Query(metaclass=QueryMetaclass):
    def __init__(self, schema):
        self.schema = schema

        self._method = None
        self._query = ""
        self._params = []

    @property
    def subquery(self):
        return Subquery(f"({self._query})", self._params)

    def select(self, *args):
        self._method = "select"

        if len(args) < 1:
            args = "*"
        else:
            args = ", ".join([str(a) for a in args])

        self._query = f"select {args} from {self.schema.__tablename__}\n"

        return self

    def update(self, changeset):
        self._method = "sql"
        self._query = f"update {self.schema.__tablename__} set "

        changeset = self.schema.casval(changeset)

        for key, value in changeset.items():
            self._query += f"{str(key)} = %s, "
            self._params.append(str(value))

        self._query = f"{_strip(self._query)}\n"

        return self

    def delete(self, row):
        self._method = "sql"
        self._query = f"delete from {self.schema.__tablename__}\n"
        return self

    def get(self, *args):
        self.select(*args)
        self._method = "get"
        return self

    def get_or_none(self, *args):
        self.select(*args)
        self._method = "get_or_none"
        return self

    def union(self):
        self._query += "union\n"
        return self

    def where(self, *clauses):
        self._query += "where "

        for clause in clauses:
            string, params = _parse_clause(clause)

            self._query += f"{string} and "
            self._params.extend(params)

        self._query = f"{_strip(self._query)}\n"

        return self

    def limit(self, *args):
        # Example: .limit(1) or limit(1, 2)
        if len(args) == 1:
            self._query += "limit %s\n"
        elif len(args) == 2:
            # `offset` works in mysql and postgres
            self._query += "limit %s offset %s\n"
        else:
            raise EstoultError("`limit` has too many arguments")

        self._params.extend(args)

        return self

    def order_by(self, *args):
        # Example: .order_by(Frog.id, {Frog.name: "desc"})
        params = []

        for a in args:
            if isinstance(a, dict):
                for k, v in a.items():
                    if v != "asc" and v != "desc":
                        raise EstoultError("Value must be 'asc' or 'desc'")

                    params.extend([str(k), v])
            else:
                params.extend([str(a, "asc")])

        s = ", ".join(["%s %s" for a in args]) % tuple(params)

        self._query += f"order by {s}\n"

        return self

    def execute(self):
        func = getattr(self.schema._database_, self._method)
        return func(self._query, self._params)

    def copy(self):
        return deepcopy(self)

    def __str__(self):
        return f"""
            {(self.schema._database_
                .mogrify(self._query, self._params)
                .decode("utf-8"))}
        """.replace(
            "\n", " "
        ).strip()


def _replace_placeholders(func):
    def wrapper(self, query, *args, **kwargs):
        query = query.replace("%s", self.placeholder)
        return func(self, query, *args, **kwargs)

    return wrapper


def _get_connection(func):
    def wrapper(self, *args, **kwargs):
        if self.autoconnect is True:
            self._connect()

        if self.cursor is None:
            self.cursor = self.conn.cursor()

        f = func(self, *args, **kwargs)

        if self.is_trans is False:
            self.cursor = None

        if self.autoconnect is True:
            self.conn.close()

        return f

    return wrapper


class Database:
    def __init__(self, autoconnect=True, *args, **kwargs):
        self.autoconnect = autoconnect

        self.Schema = Schema
        self.Schema._database_ = self

        self.cursor = None
        self.conn = None
        self.is_trans = False
        self._connect = self._make__connect_func(args, kwargs)

    def connect(self):
        self.conn = self._connect()

    def _close(self):
        self.conn.close()

    def close(self):
        return self._close

    @contextmanager
    def atomic(self, commit=True):
        self.cursor = self.conn.cursor()
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
            self.cursor = None

    @_replace_placeholders
    def _execute(self, query, params):
        self.cursor.execute(query, params)

        if self.is_trans is False:
            self.conn.commit()

    @_get_connection
    def sql(self, query, params):
        return self._execute(query, params)

    @_get_connection
    def mogrify(self, query, params):
        with self.atomic(commit=False):
            self._execute(query, params)
            return self.cursor._executed

    @_get_connection
    def select(self, query, params):
        self._execute(query, params)
        cols = [col[0] for col in self.cursor.description]
        return [dict(zip(cols, row)) for row in self.cursor.fetchall()]

    @_get_connection
    def insert(self, query, params):
        self._execute(query, params)

        if psycopg2 is not None:
            return self.cursor.fetchone()[0]

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

    @classmethod
    def _make__connect_func(cls, args, kwargs):
        def _connect():
            return mysql.connect(*args, **kwargs)

        return _connect


class PostgreSQLDatabase(Database):
    def __init__(self, *args, **kwargs):
        self.placeholder = "%s"

        super().__init__(*args, **kwargs)

    @classmethod
    def _make__connect_func(cls, args, kwargs):
        def _connect():
            return psycopg2.connect(*args, **kwargs)

        return _connect

    @_get_connection
    def mogrify(self, query, params):
        return self.cursor.mogrify(query, params)


class SQLiteDatabase(Database):
    def __init__(self, *args, **kwargs):
        self.placeholder = "?"

        super().__init__(*args, **kwargs)

    @classmethod
    def _make__connect_func(cls, args, kwargs):
        def _connect():
            return sqlite3.connect(*args, **kwargs)

        return _connect
