import re

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


class EstoultError(Exception):
    pass


def _strip(string):
    return string.rstrip(" ").rstrip(",")


class FunctionMetaclass(type):

    sql_single_arg_fns = [
        "count",
        "sum",
        "avg",
        "ceil",
    ]

    @staticmethod
    def _make_single_arg_fn(name):
        def wrapper(field):
            return f"{name}({str(field)})"

        return wrapper

    def __new__(cls, clsname, bases, attrs):
        attrs = {}

        for f in cls.sql_single_arg_fns:
            attrs[f] = FunctionMetaclass._make_single_arg_fn(f)

        return super(FunctionMetaclass, cls).__new__(cls, clsname, bases, attrs)


class fn(metaclass=FunctionMetaclass):
    pass


class Field:
    def __init__(self, type, name, **kwargs):
        self.type = type
        self.name = name

        self.primary_key = kwargs.get("primary_key") is True
        self.null = kwargs.get("null")
        self.default = kwargs.get("default")

    @property
    def full_name(self):
        return f"{self.schema.table_name}.{self.name}"

    def __str__(self):
        return self.full_name


class Schema:

    _database_ = None
    table_name = None

    def __init__(self):
        for key in dir(self):
            f = getattr(self, key)

            if isinstance(f, Field):
                f.schema = self

    @classmethod
    def select(cls, *args, **kwargs):
        return cls._database_.select(*args, **kwargs)

    @classmethod
    def get(cls, *args, **kwargs):
        return cls._database_.get(*args, **kwargs)

    @classmethod
    def _get_fields(cls):
        pk = None
        fields = {}

        for key in dir(cls):
            f = getattr(cls, key)

            if isinstance(f, Field):
                fields[key] = f

                if f.primary_key is True or (key == "id" and pk is None):
                    pk = key

        return pk, fields

    @classmethod
    def validate(cls, row):
        pk, fields = cls._get_fields()
        changeset = {}

        updating = row.get(pk) is not None

        for name, field in fields.items():
            if row.get(name) is None and updating is True:
                continue

            new_value = row.get(name)

            if new_value is None:
                if field.default is not None:
                    new_value = field.default
            else:
                if isinstance(new_value, field.type) is False:
                    raise EstoultError(f"Incorrect type for {name}.")

            if field.null is False and new_value is None:
                raise EstoultError(f"{name} cannot be None")

            changeset[name] = new_value

        return pk, changeset

    @classmethod
    def insert(cls, obj):
        _, changeset = cls.validate(obj)
        sql = f"insert into {cls.table_name} set "
        params = []

        for key, value in changeset.items():
            params.append(value)
            sql += f"{key} = %s, "

        return cls._database_.insert(_strip(sql), params)

    @classmethod
    def update(cls, old, new):
        pk, changeset = cls.validate({**old, **new})
        sql = f"update {cls.table_name} set "
        params = []

        for key, value in changeset.items():
            params.append(value)
            sql += f"{key} = %s, "

        sql = f"{_strip(sql)} where {pk} = {changeset[pk]}"

        return cls._database_.sql(sql, params)


class Query:
    def __init__(self, *schemas):
        self.schemas = schemas
        [s() for s in schemas]

        self.method = None

        self._query = ""
        self._params = []

    @staticmethod
    def sanitise_query(query):
        return re.sub(r"^[a-zA-Z_][a-zA-Z0-9_\$]*$", "", query)

    def select(self, *args):
        self.method = "select"

        if len(args) < 1:
            args = "*"
        else:
            args = ", ".join([str(a) for a in args])

        self._query = f"select {args} from {self.schemas[0].table_name}\n"

        return self

    def get(self, *args):
        self.select(*args)
        self.method = "get"
        return self

    def left_join(self, schema, on):
        if schema not in self.schemas:
            raise EstoultError("Schema not added to Query")

        q = f"{str(on[0])} = {str(on[1])}"
        self._query += f"left join {schema.table_name} on {q}\n"

        return self

    def union(self):
        self._query += "union\n"
        return self

    def where(self, *args, **kwargs):
        self._query += "where "

        for key, value in kwargs.items():
            self._query += f"{key} = '%s', "
            self._params.append(value)

        self._query = f"{_strip(self._query)}\n"

        return self

    def execute(self):
        func = getattr(self.schemas[0], self.method)
        return func(self._query, self._params)

    def __str__(self):
        query = self._query % self._params
        return f"({Query.sanitise_query(query)})"


class Database:
    def __init__(self, *args, **kwargs):
        self.connect = Database.make_connect_func(**kwargs)

        self.Schema = Schema
        self.Schema._database_ = self

    @staticmethod
    def make_connect_func(**kwargs):
        def connect():
            return mysql.connect(**kwargs)

        return connect

    def select(self, query, params):
        conn = self.connect()

        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            cols = [col[0] for col in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]
        except (Exception, mysql.Error) as err:
            raise err
        finally:
            cursor.close()
            conn.close()

    def get(self, query, params):
        row = self.select(query, params)
        return row[0]

    def insert(self, query, params):
        conn = self.connect()

        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            row_id = cursor.lastrowid
            conn.commit()
            return row_id
        except (Exception, mysql.Error) as err:
            conn.rollback()
            raise err
        finally:
            cursor.close()

    def sql(self, query, params):
        conn = self.connect()

        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return True
        except (Exception, mysql.Error) as err:
            conn.rollback()
            raise err
        finally:
            cursor.close()
