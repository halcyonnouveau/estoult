from contextlib import contextmanager
from collections import namedtuple

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


__version__ = "0.1.0"
__all__ = [
    "EstoultError",
    "ClauseError",
    "FieldError",
    "fn",
    "op",
    "Field",
    "Query",
    "Database",
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


def parse_clause(clause):
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


def strip(string):
    return string.rstrip(" ").rstrip(",").rstrip("and")


def replace_placeholders(func):
    def wrapper(self, query, *args, **kwargs):
        query = query.replace("%s", self.placeholder)
        return func(self, query, *args, **kwargs)

    return wrapper


class FunctionMetaclass(type):

    sql_fns = [
        "count",
        "sum",
        "avg",
        "ceil",
        "distinct",
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


class OperatorMetaclass(type):

    sql_ops = {
        "eq": "=",
        "lt": "<",
        "lt_eq": "<=",
        "gt": ">",
        "gt_eq": ">=",
        "n_eq": "<>",
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
            args = [parse_clause(a) for a in args]
            return func(cls, *args)

        return wrapper

    @classmethod
    @_clause_args.__func__
    def or_(cls, cond_1, cond_2):
        return ConditionalClause(
            f"({strip(cond_1[0])} or {strip(cond_2[0])})", (*cond_1[1], *cond_2[1]),
        )

    @classmethod
    @_clause_args.__func__
    def and_(cls, cond_1, cond_2):
        return ConditionalClause(
            f"({strip(cond_1[0])} and {strip(cond_2[0])})", (*cond_1[1], *cond_2[1]),
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
    def not_(cls, field):
        return ConditionalClause("not {str(field)}", ())

    @classmethod
    def is_null(cls, field):
        return ConditionalClause("{str(field)} is null", ())

    @classmethod
    def not_null(cls, field):
        return ConditionalClause("{str(field)} is not null", ())


class Field:
    def __init__(self, type, name, **kwargs):
        self.type = type
        self.name = name

        self.null = kwargs.get("null")
        self.default = kwargs.get("default")
        self.primary_key = kwargs.get("primary_key") is True

    @property
    def full_name(self):
        return f"{self.schema.table_name}.{self.name}"

    def __str__(self):
        return self.full_name

    def __hash__(self):
        return hash(str(self))

    def __eq__(self, comp):
        return str(self) == comp


class SchemaMetaclass(type):
    def __new__(cls, clsname, bases, attrs):
        c = super(SchemaMetaclass, cls).__new__(cls, clsname, bases, attrs)

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
    table_name = None

    @classmethod
    def validate(cls, row):
        changeset = {}

        updating = row.get(cls.pk.name) is not None

        for field in cls.fields:
            new_value = row.get(field.name)

            if new_value is None and updating is True:
                continue

            if new_value is None:
                if field.default is not None:
                    new_value = field.default
            else:
                if isinstance(new_value, field.type) is False:
                    raise FieldError(f"Incorrect type for {str(field)}.")

            if field.null is False and new_value is None:
                raise FieldError(f"{str(field)} cannot be None")

            changeset[field.name] = new_value

        return changeset

    @classmethod
    def insert(cls, obj):
        changeset = cls.validate(obj)
        sql = f"insert into {cls.table_name} set "
        params = []

        for key, value in changeset.items():
            params.append(value)
            sql += f"{str(key)} = %s, "

        return cls._database_.insert(strip(sql), params)

    @classmethod
    def update(cls, old, new):
        # This updates a single row only, if you want to update several
        # use `update` in `Query`
        changeset = cls.validate({**old, **new})
        sql = f"update {cls.table_name} set "
        params = []

        for key, value in changeset.items():
            params.append(value)
            sql += f"{str(key)} = %s, "

        sql = f"{strip(sql)} where {str(cls.pk)} = {changeset[cls.pk.name]}"

        return cls._database_.sql(sql, params)

    @classmethod
    def delete(cls, row):
        # Deletes single row - look at `Query` for batch
        sql = f"delete from {cls.table_name} where {str(cls.pk)} = {row[cls.pk.name]}"
        return cls._database_.sql(sql, [])


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
            if schema not in self.schemas:
                raise EstoultError("Schema not added to Query")

            q = f"{str(on[0])} = {str(on[1])}"
            self._query += f"{join_type} {schema.table_name} on {q}\n"

            return self

        return join_fn

    def __new__(cls, clsname, bases, attrs):
        for join_type in cls.sql_joins:
            attrs[join_type.replace(" ", "_")] = QueryMetaclass.make_join_fn(join_type)

        return super(QueryMetaclass, cls).__new__(cls, clsname, bases, attrs)


class Query(metaclass=QueryMetaclass):
    def __init__(self, *schemas):
        if len(schemas) == 0:
            raise EstoultError("Schema(s) is/are required")

        self.schemas = schemas
        self.schema = schemas[0]

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

        self._query = f"select {args} from {self.schema.table_name}\n"

        return self

    def update(self, changeset):
        self._method = "sql"
        self._query = f"update {self.schema.table_name} set "

        _, changeset = self.schema.validate(changeset, updating=True)

        for key, value in changeset.items():
            self._query += f"{str(key)} = %s, "
            self._params.append(str(value))

        self._query = f"{strip(self._query)}\n"

        return self

    def delete(self, row):
        self._method = "sql"
        self._query = f"delete from {self.schema.table_name}\n"
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
            string, params = parse_clause(clause)

            self._query += f"{string} and "
            self._params.extend(params)

        self._query = f"{strip(self._query)}\n"

        return self

    def limit(self, *args):
        s = ", ".join(["%s" for a in args])
        self._query += f"limit {s}\n"
        self._params.extend(args)
        return self

    def order_by(self, *args, sort="desc"):
        s = ", ".join(["%s" for a in args])
        self._query += f"limit {s} {sort}\n"
        self._params.extend(args)
        return self

    def execute(self):
        func = getattr(self.schema._database_, self._method)
        return func(self._query, self._params)

    def __str__(self):
        return f"""
            {(self.schema._database_
                .mogrify(self._query, self._params)
                .decode("utf-8"))}
        """.replace(
            "\n", " "
        ).strip()


class Database:
    def __init__(self, autoconnect=True, *args, **kwargs):
        self.autoconnect = autoconnect

        self.Schema = Schema
        self.Schema._database_ = self

        self.conn = None
        self._connect = self._make__connect_func(args, kwargs)

    def connect(self):
        self.conn = self._connect()

    def _close(self):
        self.conn.close()

    def close(self):
        return self._close

    def get_connection(self):
        if self.autoconnect is False:
            return self.conn
        else:
            return self._connect()

    @contextmanager
    def transaction(self, commit=True):
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            yield cursor
        except Exception as err:
            conn.rollback()
            raise err
        else:
            if commit:
                conn.commit()
            else:
                conn.rollback()
        finally:
            if self.autoconnect is True:
                conn.close()

    @replace_placeholders
    def mogrify(self, query, params):
        with self.transaction(commit=False) as cursor:
            if psycopg2:
                return cursor.mogrify(query, params)

            cursor.execute(query, params)
            return cursor._executed

    @replace_placeholders
    def select(self, query, params):
        with self.transaction() as cursor:
            cursor.execute(query, params)
            cols = [col[0] for col in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]

    @replace_placeholders
    def get(self, query, params):
        row = self.select(query, params)
        return row[0]

    @replace_placeholders
    def get_or_none(self, query, params):
        try:
            return self.get(query, params)
        except IndexError:
            return None

    @replace_placeholders
    def insert(self, query, params):
        with self.transaction() as cursor:
            cursor.execute(query, params)
            row_id = cursor.lastrowid
            return row_id

    @replace_placeholders
    def sql(self, query, params):
        with self.transaction() as cursor:
            cursor.execute(query, params)
            return True


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


class SQLiteDatabase(Database):
    def __init__(self, *args, **kwargs):
        self.placeholder = "?"

        super().__init__(*args, **kwargs)

    @classmethod
    def _make__connect_func(cls, args, kwargs):
        def _connect():
            return sqlite3.connect(*args, **kwargs)

        return _connect
