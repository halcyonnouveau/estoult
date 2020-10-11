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


__version__ = "0.3.3"
__all__ = [
    "ClauseError",
    "Database",
    "DatabaseError",
    "EstoultError",
    "Field",
    "FieldError",
    "fn",
    "op",
    "Query",
    "QueryError",
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


Clause = namedtuple("Clause", ["clause", "params"])


def _strip(string):
    return string.rstrip(" ").rstrip(",").rstrip("and")


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
        def op_fn(field, value):
            return Clause(f"{field} {operator} %s", (value,))

        return op_fn

    def __new__(cls, clsname, bases, attrs):
        for name, operator in cls.sql_ops.items():
            attrs[name] = OperatorMetaclass.make_fn(operator)

        return super(OperatorMetaclass, cls).__new__(cls, clsname, bases, attrs)


class op(metaclass=OperatorMetaclass):
    @staticmethod
    def or_(cond_1, cond_2):
        return Clause(
            f"({_strip(cond_1[0])} or {_strip(cond_2[0])})", (*cond_1[1], *cond_2[1]),
        )

    @staticmethod
    def and_(cond_1, cond_2):
        return Clause(
            f"({_strip(cond_1[0])} and {_strip(cond_2[0])})", (*cond_1[1], *cond_2[1]),
        )

    @staticmethod
    def in_(field, value):
        if isinstance(value, Query):
            return Clause(f"{field} in ({str(value)})", ())

        if isinstance(value, list) or isinstance(value, tuple):
            placeholders = ", ".join(["%s"] * len(value))
            return Clause(f"{field} in ({placeholders})", (value,))

        raise ClauseError("`in` value can only be `subquery`, `list`, or `tuple`")

    @staticmethod
    def like(field, value):
        arg = f"%{value}%"
        return Clause(f"{field} like %s", (arg,))

    @staticmethod
    def ilike(field, value):
        arg = f"%{value}%"
        return Clause(f"{field} ilike %s", (arg,))

    @staticmethod
    def not_(field):
        return Clause(f"not {field}", ())

    @staticmethod
    def is_null(field):
        return Clause(f"{field} is null", ())

    @staticmethod
    def not_null(field):
        return Clause(f"{field} is not null", ())


class FunctionClauseMetaclass(type):
    def __new__(cls, clsname, bases, attrs):
        # Add op overloading
        for name, operator in OperatorMetaclass.sql_ops.items():
            attrs[f"__{name}__"] = OperatorMetaclass.make_fn(operator)

        return super(FunctionClauseMetaclass, cls).__new__(cls, clsname, bases, attrs)


class FunctionClause(Clause, metaclass=FunctionClauseMetaclass):
    def __str__(self):
        return self.clause


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
            return FunctionClause(
                f"{name}({str(', '.join([str(a) for a in args]))})", ()
            )

        return sql_fn

    def __new__(cls, clsname, bases, attrs):
        for f in cls.sql_fns:
            attrs[f] = FunctionMetaclass.make_sql_fn(f)

        # Add op overloading
        for name, operator in OperatorMetaclass.sql_ops.items():
            attrs[f"__{name}__"] = OperatorMetaclass.make_fn(operator)

        return super(FunctionMetaclass, cls).__new__(cls, clsname, bases, attrs)


class fn(metaclass=FunctionMetaclass):
    @staticmethod
    def alias(field, value):
        return FunctionClause(f"{field} as {value}", ())

    @staticmethod
    def cast(field, value):
        return FunctionClause(f"cast({field} as {value})", ())

    @staticmethod
    def wild(schema):
        return FunctionClause(f"{schema.__tablename__}.*", ())


class FieldMetaclass(type):
    def __new__(cls, clsname, bases, attrs):
        # Add op overloading
        for name, operator in OperatorMetaclass.sql_ops.items():
            attrs[f"__{name}__"] = OperatorMetaclass.make_fn(operator)

        return super(FieldMetaclass, cls).__new__(cls, clsname, bases, attrs)


class Field(metaclass=FieldMetaclass):
    def __init__(self, type, name, **kwargs):
        self.type = type
        self.name = name

        self.caster = kwargs.get("caster")

        self.null = kwargs.get("null", True)
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

    def __getitem__(cls, item):
        return getattr(cls, item)


class Schema(metaclass=SchemaMetaclass):

    _database_ = None
    __tablename__ = None

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

            if field.default is not None:
                value = field.default

            try:
                value = row[field.name]
            except KeyError:
                if updating is True or field.name == cls.pk.name:
                    continue

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
    def casval(cls, row):
        updating = row.get(cls.pk.name) is not None

        changeset = cls._cast(updating, row)
        changeset = cls._validate(updating, changeset)

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
            sql += f"{key} = %s, "
            params.append(value)

        sql = f"{_strip(sql)} where "

        for key, value in old.items():
            sql += f"{key} = %s and "
            params.append(value)

        return cls._database_.sql(_strip(sql), params)

    @classmethod
    def update_by_pk(cls, id, new):
        return cls.update({cls.pk: id}, new)

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
        return cls.delete({cls.pk: id}, new)


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
            self._query += f"{key} = %s, "
            self._params.append(value)

        self._query = f"{_strip(self._query)}\n"

        return self

    def delete(self):
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
            string, params = clause

            # We can always add an `and` to the end cus it get stripped off ;)
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
            raise QueryError("`limit` has too many arguments")

        self._params.extend(args)

        return self

    def order_by(self, *args):
        # Example: .order_by(Frog.id, {Frog.name: "desc"})
        params = []

        for a in args:
            if isinstance(a, dict):
                for k, v in a.items():
                    if v != "asc" and v != "desc":
                        raise QueryError("Value must be 'asc' or 'desc'")

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
            self.connect()

        if self.is_trans is False:
            self._new_cursor()

        f = func(self, *args, **kwargs)

        if self.autoconnect is True:
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

    def _connect(self):
        return mysql.connect(*self.cargs, **self.ckwargs)


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
