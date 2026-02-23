"""
Database Base Model

Provides the SQLAlchemy declarative base. This is the foundation for all
ORM models in the application. Any class inheriting from this Base will be
mapped to a table in the PostgreSQL database.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
