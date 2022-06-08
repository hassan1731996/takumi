import datetime as dt
import pickle

from sqlalchemy.ext.hybrid import hybrid_method, hybrid_property

from takumi.extensions import db, redis


def add_columns_as_attributes(table):
    for column in table.columns:
        setattr(table, str(column).replace(".", "_"), column)
    return table


def hybrid_property_expression(func):
    @hybrid_property
    def wrapper(self):
        cls = self.__class__
        expression = getattr(self.__class__, func.__name__)
        return db.session.query(expression).filter(cls.id == self.id).one_or_none()[0]

    @wrapper.expression
    def wrapper(cls):
        return func(cls).label(func.__name__)

    return wrapper


def hybrid_method_expression(func):
    @hybrid_method
    def wrapper(self, *args, **kwargs):
        cls = self.__class__
        expression = getattr(self.__class__, func.__name__)(*args, **kwargs)
        return db.session.query(expression).filter(cls.id == self.id).one_or_none()[0]

    @wrapper.expression
    def wrapper(cls, *args, **kwargs):
        return func(cls, *args, **kwargs).label(func.__name__)

    return wrapper


def hybrid_property_subquery(func):
    @hybrid_property
    def wrapper(self):
        cls = self.__class__
        expression = getattr(self.__class__, func.__name__)
        return db.session.query(expression).filter(cls.id == self.id).one_or_none()[0]

    @wrapper.expression
    def wrapper(cls):
        return func(cls).subquery().as_scalar().label(func.__name__)

    return wrapper


def hybrid_method_subquery(func):
    @hybrid_method
    def wrapper(self, *args, **kwargs):
        cls = self.__class__
        expression = getattr(self.__class__, func.__name__)(*args, **kwargs)
        return db.session.query(expression).filter(cls.id == self.id).one_or_none()[0]

    @wrapper.expression
    def wrapper(cls, *args, **kwargs):
        return func(cls, *args, **kwargs).subquery().as_scalar().label(func.__name__)

    return wrapper


def cached_property(func, ttl=dt.timedelta(hours=1)):
    @property
    def wrapper(self, *args, **kwargs):
        cls = self.__class__
        key = "CACHED_PROPERTY:" + cls.__name__ + "." + func.__name__ + ":" + self.id
        conn = redis.get_connection()
        cached_result = conn.get(key)
        if cached_result is not None:
            try:
                return pickle.loads(cached_result.encode("latin1"))
            except pickle.UnpicklingError:
                pass
        result = func(self, *args, **kwargs)
        pickled = pickle.dumps(result)
        conn.setex(key, int(ttl.total_seconds()), pickled.decode("latin1"))
        return result

    return wrapper
