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


class Field:

    def __init__(self, type, name, **kwargs):
        self.type = type
        self.name = name

        self.primary_key = kwargs.get('primary_key') is True
        self.null = kwargs.get('null')
        self.default = kwargs.get('default')

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

                if (f.primary_key is True or (key == 'id' and pk is None)):
                    pk = key

        return pk, fields

    @classmethod
    def validate(cls, *args, **kwargs):
        pk, fields = cls._get_fields()
        changeset = {}

        updating = kwargs.get(pk) is not None

        for name, field in fields.items():
            if kwargs.get(name) is None and updating is True:
                continue

            new_value = kwargs.get(name)

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

        sql = sql[:-2]

        return Schema._database_.insert(sql, params)

    @classmethod
    def update(cls, old, new):
        pk, changeset = cls.validate(**{**old, **new})
        sql = f"update {cls.table_name} set "
        params = []

        for key, value in changeset.items():
            params.append(value)
            sql += f"{key} = %s, "

        sql = f"{sql[:-2]} where {pk} = {changeset[pk]}"

        return cls._database_.sql(sql, params)


class Query:
    def __init__(self, *schemas):
        self.schemas = schemas

        for s in schemas:
            s()

        self.method = None

        self._query = ""
        self._params = []

    def select(self, *args, method="select"):
        self.method = method

        if len(args) < 1:
            args = "*"
        else:
            args = ", ".join([
                a.full_name if isinstance(a, Field) else a for a in args
            ])

        self._query = f"select {args} from {self.schemas[0].table_name}\n"

        return self

    def get(self, *args):
        self.select(*args, method="get")
        return self

    def left_join(self, j_schema, on):
        if j_schema not in self.schemas:
            raise EstoultError("Schema not added to Query")

        q = f"{on[0].full_name} = {on[1].full_name}"
        self._query += f"left join {j_schema.table_name} on {q}\n"

        return self

    def union(self):
        self._query += "union\n"
        return self

    def where(self, *args, **kwargs):
        self._query += "where "

        for key, value in kwargs.items():
            self._query += f"{key} = '%s', "
            self._params.append(value)

        self._query = f"{self._query[:-2]}\n"

        return self

    def execute(self):
        func = getattr(self.schemas[0], self.method)
        return func(self._query, self._params)


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
            cur = conn.cursor()
            cur.execute(query, params)

            cols = [col[0] for col in cur.description]
            rows = [dict(zip(cols, row)) for row in cur.fetchall()]

            return rows
        except (Exception, mysql.Error) as err:
            raise err
        finally:
            cur.close()
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
