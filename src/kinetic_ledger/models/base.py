"""Shared ORM base.

Models must use the same metadata object as the database session and Alembic.
Keeping a second declarative base here meant user and wallet tables were omitted
from both ``init_db`` and migration autogeneration.
"""

from ..database.database import Base

__all__ = ["Base"]
