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


class EstoultError(Exception):
    pass


def _strip(string):
    return string.rstrip(" ").rstrip(",")


class FunctionMetaclass(type):

    sql_fns = [
        "count",
        "sum",
        "avg",
        "ceil",
        "distinct",
    ]

    @staticmethod
    def _make_fn(name):
        def wrapper(*args):
            return f"{name}({str(', '.join([str(a) for a in args]))})"

        return wrapper

    def __new__(cls, clsname, bases, attrs):
        for f in cls.sql_fns:
            attrs[f] = FunctionMetaclass._make_fn(f)

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
        "in": "in",
    }

    @staticmethod
    def _make_fn(operator):
        def wrapper(value):
            return f"{operator} %s", str(value)

        return wrapper

    def __new__(cls, clsname, bases, attrs):
        for name, operator in cls.sql_ops.items():
            attrs[name] = OperatorMetaclass._make_fn(operator)

        return super(OperatorMetaclass, cls).__new__(cls, clsname, bases, attrs)


class op(metaclass=OperatorMetaclass):
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

    def __hash__(self):
        return hash(str(self))

    def __eq__(self, comp):
        return str(self) == comp


class Schema:

    _database_ = None
    table_name = None

    def __init__(self):
        for key in dir(self):
            f = getattr(self, key)

            if isinstance(f, Field):
                f.schema = self

    @classmethod
    def mogrify(cls, *args, **kwargs):
        return cls._database_.mogrify(*args, **kwargs)

    @classmethod
    def sql(cls, *args, **kwargs):
        return cls._database_.sql(*args, **kwargs)

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
    def validate(cls, row, updating=False):
        pk, fields = cls._get_fields()
        changeset = {}

        if updating is not True:
            updating = row.get(pk) is not None

        for name, field in fields.items():
            new_value = row.get(name) or row.get(str(field))

            if new_value is None and updating is True:
                continue

            if new_value is None:
                if field.default is not None:
                    new_value = field.default
            else:
                if isinstance(new_value, field.type) is False:
                    raise EstoultError(f"Incorrect type for {str(field)}.")

            if field.null is False and new_value is None:
                raise EstoultError(f"{str(field)} cannot be None")

            changeset[name] = new_value

        return pk, changeset

    @classmethod
    def insert(cls, obj):
        _, changeset = cls.validate(obj)
        sql = f"insert into {cls.table_name} set "
        params = []

        for key, value in changeset.items():
            params.append(value)
            sql += f"{str(key)} = %s, "

        return cls._database_.insert(_strip(sql), params)

    @classmethod
    def update(cls, old, new):
        pk, changeset = cls.validate({**old, **new})
        sql = f"update {cls.table_name} set "
        params = []

        for key, value in changeset.items():
            params.append(value)
            sql += f"{str(key)} = %s, "

        sql = f"{_strip(sql)} where {pk} = {changeset[pk]}"

        return cls._database_.sql(sql, params)


class Query:
    def __init__(self, *schemas):
        if len(schemas) == 0:
            raise EstoultError("Schema(s) is/are required")

        self.schemas = schemas
        [s() for s in schemas]

        self.method = None

        self._query = ""
        self._params = []

    def select(self, *args):
        self.method = "select"

        if len(args) < 1:
            args = "*"
        else:
            args = ", ".join([str(a) for a in args])

        self._query = f"select {args} from {self.schemas[0].table_name}\n"

        return self

    def update(self, changeset):
        self.method = "sql"
        schema = self.schemas[0]

        self._query = f"update {schema.table_name} set "

        _, changeset = schema.validate(changeset, updating=True)

        for key, value in changeset.items():
            self._query += f"{str(key)} = %s, "
            self._params.append(str(value))

        self._query = f"{_strip(self._query)}\n"

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

    def where(self, *args):
        self._query += "where "

        for arg in args:
            key, value = list(arg.items())[0]

            if isinstance(value, tuple):
                self._query += f"{str(key)} {value[0]}, "
                self._params.append(value[1])
            else:
                self._query += f"{str(key)} = %s, "
                self._params.append(value)

        self._query = f"{_strip(self._query)}\n"

        return self

    def limit(self, args):
        s = ', '.join(['%s' for a in args])
        self._query += f"limit {s}\n"
        self._params.append(*args)
        return self

    def order_by(self, args, sort='desc'):
        s = ', '.join(['%s' for a in args])
        self._query += f"limit {s} {sort}\n"
        self._params.append(*args)
        return self

    def execute(self):
        func = getattr(self.schemas[0], self.method)
        return func(self._query, self._params)

    def __str__(self):
        return f"""
            ({self.schemas[0]
            .mogrify(self._query, self._params)
            .decode("utf-8")})
        """.replace(
            "\n", " "
        ).strip()


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

    @contextmanager
    def transaction(self, commit=True):
        conn = self.connect()
        cursor = conn.cursor()

        try:
            yield cursor
        except mysql.DatabaseError as err:
            conn.rollback()
            raise err
        else:
            if commit:
                conn.commit()
            else:
                conn.rollback()
        finally:
            conn.close()

    def mogrify(self, query, params):
        with self.transaction(commit=False) as cursor:
            if psycopg2:
                return cursor.mogrify(query, params)

            cursor.execute(query, params)
            return cursor._executed

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
