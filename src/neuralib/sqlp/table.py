from __future__ import annotations

import abc
import typing
from typing import NamedTuple, Any, Optional, Generic, TYPE_CHECKING, Annotated, Callable

from .literal import FOREIGN_POLICY, CONFLICT_POLICY

if TYPE_CHECKING:
    import datetime
    from .expr import SqlExpr

__all__ = [
    'Field', 'CURRENT_DATE', 'CURRENT_TIME', 'CURRENT_DATETIME',
    'table_name', 'table_new', 'table_field_names', 'table_fields', 'table_field',
    'PRIMARY', 'table_primary_fields',
    'UNIQUE', 'unique', 'UniqueConstraint', 'table_unique_fields',
    'foreign', 'ForeignConstraint', 'table_foreign_fields', 'table_foreign_field',
    'check', 'CheckConstraint', 'table_check_fields', 'table_check_field'
]

T = typing.TypeVar('T')
missing = object()


@typing.final
class PRIMARY(object):
    """
    annotate a field as a primary key.

    >>> class Example:
    ...     a: Annotated[str, PRIMARY]  # style 1
    """

    def __init__(self, order: typing.Literal['ASC', 'DESC'] = None,
                 conflict: CONFLICT_POLICY = None,
                 auto_increment=False):
        self.order = order
        self.conflict = conflict
        self.auto_increment = auto_increment


@typing.final
class UNIQUE(object):
    """
    annotated a field as a unique key.

    >>> class Example:
    ...     a: Annotated[str, UNIQUE]  # style 1
    """

    def __init__(self, conflict: CONFLICT_POLICY = None):
        self.conflict = conflict


@typing.final
class CURRENT_DATE(object):
    """
    annotated a date field which use current date as its default.

    >>> class Example:
    ...     a: Annotated[datetime.date, CURRENT_DATE]

    """

    def __init__(self):
        raise RuntimeError()


@typing.final
class CURRENT_TIME(object):
    """
    annotated a time field which use current time as its default.

    >>> class Example:
    ...     a: Annotated[datetime.time, CURRENT_TIME]

    """

    def __init__(self):
        raise RuntimeError()


@typing.final
class CURRENT_DATETIME(object):
    """
    annotated a datetime field which use current datetime as its default.

    >>> class Example:
    ...     a: Annotated[datetime.datetime, CURRENT_DATETIME]

    """

    def __init__(self):
        raise RuntimeError()


class Field(NamedTuple):
    """
    A SQL column, a field in a table.
    """
    table: type
    """associated table"""

    name: str
    """column/field name"""

    raw_type: type
    """origin field type"""

    sql_type: type
    """column/field type. Should be supported by SQL"""

    f_value: Any = missing
    """default value."""

    not_null: bool = True
    """Is it not NULL."""

    annotated: list[Any] = ()

    @property
    def table_name(self) -> str:
        return table_name(self.table)

    @property
    def has_default(self) -> bool:
        return self.f_value is not missing

    @property
    def is_primary(self) -> bool:
        return self.get_primary() is not None

    def get_primary(self) -> PRIMARY | None:
        for a in self.annotated:
            if a == PRIMARY:
                return PRIMARY()
            elif isinstance(a, PRIMARY):
                return a
        return None

    @property
    def is_unique(self) -> bool:
        return self.get_unique() is not None

    def get_unique(self) -> UNIQUE | None:
        for a in self.annotated:
            if a == UNIQUE:
                return UNIQUE()
            elif isinstance(a, UNIQUE):
                return a
        return None

    def get_annotation(self, annotation_type: type[T]) -> T | None:
        for a in self.annotated:
            if isinstance(a, annotation_type):
                return a
        return None


class Table(Generic[T], metaclass=abc.ABCMeta):
    """
    SQL table information.
    """

    table_type: type[T]
    """associated table"""

    table_name: str
    """name of the table."""

    @abc.abstractmethod
    def table_seq(self, instance: T) -> tuple[Any, ...]:
        """
        cast an instance as a tuple as SQL parameters.

        :param instance:
        :return:
        """
        pass

    @abc.abstractmethod
    def table_dict(self, instance: T, *, sql_type: bool = True) -> dict[str, Any]:
        """
        cast an instance cast as dict as SQL parameters.

        :param instance:
        :param sql_type: cast value as SQL type
        """
        pass

    @abc.abstractmethod
    def table_new(self, *args) -> T:
        """create an instance."""
        pass

    @property
    def table_field_names(self) -> list[str]:
        """list of the name for each field in the table."""
        return [it.name for it in self.table_fields]

    @property
    @abc.abstractmethod
    def table_fields(self) -> list[Field]:
        """list fields in the table."""
        pass

    @property
    def table_primary_fields(self) -> list[Field]:
        """list of primary field in the table."""
        return [field for field in self.table_fields if field.is_primary]

    def table_field(self, name: str) -> Field:
        """
        Get field by the name in the table.

        :param name:
        :return:
        :raise RuntimeError: no such field.
        """
        for field in self.table_fields:
            if field.name == name:
                return field
        raise RuntimeError(f'{self.table_name} no such field {name}')

    @property
    @abc.abstractmethod
    def table_unique_fields(self) -> list[UniqueConstraint]:
        """get a list of the unique constraint in the table."""
        pass

    @property
    @abc.abstractmethod
    def table_foreign_fields(self) -> list[ForeignConstraint]:
        """get a list of the foreign constraint in the table."""
        pass

    @property
    @abc.abstractmethod
    def table_check_fields(self) -> dict[Optional[str], CheckConstraint]:
        """get a dict of the field constraint in the table."""
        pass


def _table_class(cls: type[T]) -> Table[T]:
    return getattr(cls, '_sql_table')


def table_name(table: type[T]) -> str:
    """the name of the table."""
    return _table_class(table).table_name


def table_seq(instance: T) -> tuple[Any, ...]:
    """
    cast an instance as a tuple as SQL parameters.

    :param instance:
    :return:
    """
    return _table_class(type(instance)).table_seq(instance)


def table_dict(instance: T, *, sql_type: bool = True) -> dict[str, Any]:
    """
    cast an instance cast as dict as SQL parameters.

    :param instance:
    :param sql_type: cast value as SQL type
    """
    return _table_class(type(instance)).table_dict(instance, sql_type=sql_type)


def table_new(table: type[T], *args) -> T:
    """create an instance for the table."""
    return _table_class(table).table_new(*args)


class UniqueConstraint(NamedTuple):
    name: str
    """constraint name"""

    table: type
    """associated table"""

    fields: list[str]
    """associated fields"""

    conflict: CONFLICT_POLICY | None


def unique(conflict: CONFLICT_POLICY = None):
    """
    A decorator to create an unique constraint.
    """

    def _decorator(f):
        setattr(f, '_sql_unique', (conflict,))
        return f

    return _decorator


class ForeignConstraint(NamedTuple):
    """SQL foreign constraint."""

    name: str
    """constraint name"""

    table: type
    """associated table"""
    fields: list[str]
    """associated fields"""

    foreign_table: type
    """referred foreign table"""
    foreign_fields: list[str]
    """referred foreign fields"""

    on_update: FOREIGN_POLICY
    on_delete: FOREIGN_POLICY


def foreign(*field,
            update: FOREIGN_POLICY = 'NO ACTION',
            delete: FOREIGN_POLICY = 'NO ACTION'):
    """
    A decorator to create a foreign constraint.

    Common use:

    With a foreign table

    >>> class ForeignTable:
    ...     a: Annotated[str, str]
    ...     b: Annotated[str, str]

    1. mapping one-by-one

    >>> class Example:
    ...     a: Annotated[str, str]
    ...     b: Annotated[str, str]
    ...     @foreign(ForeignTable.a, ForeignTable.b)
    ...     def _foreign(self):
    ...         return self.a, self.b

    2. by default, with the primary keys for the referred foreign table.

    >>> class Example:
    ...     a: Annotated[str, str]
    ...     b: Annotated[str, str]
    ...     @foreign(ForeignTable)
    ...     def _foreign(self):
    ...         return self.a, self.b

    3. Self refered.

    >>> class Example:
    ...     a: Annotated[str, str]
    ...     b: Annotated[str, str]
    ...     @foreign('a')
    ...     def _foreign(self):
    ...         return self.b

    :param field: a foreign table or foreign fields.
    :param update: update policy
    :param delete: delete policy
    """
    if len(field) == 0:
        raise RuntimeError('empty fields')

    def _decorator(f):
        setattr(f, '_sql_foreign', (field, update, delete))
        return f

    return _decorator


class CheckConstraint(NamedTuple):
    """SQL check constraint"""
    name: str
    """constraint name"""

    table: type
    """associated table"""
    field: Optional[str]
    """associated field's name."""
    expression: SqlExpr
    """checking expression"""


def check(field: str = None):
    """
    A decorator to make a check constraint.

    1. by a field

    >>> class Example:
    ...     a: str
    ...     @check('a')
    ...     def check_a(self):
    ...         return self.a != ''

    2. by over all

    >>> class Example:
    ...     a: str
    ...     @check()
    ...     def check_a(self):
    ...         return self.a != ''

    :param field: field name.
    """

    def _decorator(f):
        setattr(f, '_sql_check', (field,))
        return f

    return _decorator


def table_field_names(table: type[T]) -> list[str]:
    """list of the name for each field in the table."""
    return _table_class(table).table_field_names


def table_fields(table: type[T]) -> list[Field]:
    """list fields in the table."""
    return _table_class(table).table_fields


def table_field(table: type[T], field: str) -> Field:
    """
    Get field by the name in the table.

    :param field:
    :return:
    :raise RuntimeError: no such field.
    """
    return _table_class(table).table_field(field)


def table_primary_fields(table: type[T]) -> list[Field]:
    """list of the name for each primary field in the table."""
    return _table_class(table).table_primary_fields


def table_unique_fields(table: type[T]) -> list[UniqueConstraint]:
    """list of the name for each unique field in the table."""
    return _table_class(table).table_unique_fields


def table_foreign_fields(table: type[T]) -> list[ForeignConstraint]:
    """get a list of the foreign constraint in the table."""
    return _table_class(table).table_foreign_fields


def table_foreign_field(table: type[T], target: type | Callable) -> ForeignConstraint | None:
    """
    get the foreign constraint in the table that refer to the target table.

    :param table:
    :param target: refer table or foreign constraint function (the function decorated by @foreign)
    :return: foreign constraint.
    """
    if isinstance(target, type):
        for field in table_foreign_fields(table):
            if field.foreign_table == target:
                return field
    elif hasattr(target, '_sql_foreign'):
        for field in table_foreign_fields(table):
            if field.name == target.__name__:
                return field
    return None


def table_check_fields(table: type[T]) -> dict[Optional[str], CheckConstraint]:
    """get a dict of the field constraint in the table."""
    return _table_class(table).table_check_fields


def table_check_field(table: type[T], field: Optional[str]) -> Optional[CheckConstraint]:
    """get the check constrain of a field in the table."""
    return _table_class(table).table_check_fields.get(field, None)
