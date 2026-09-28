"""Alembic: схема = таблицы всех модулей на общем metadata (kognis.db)."""

import importlib
import pkgutil

from alembic import context

import kognis
from kognis.db import make_engine, metadata

# регистрируем таблицы всех модулей (каждый объявляет свои в _infra.py)
for info in pkgutil.iter_modules(kognis.__path__):
    importlib.import_module(f"kognis.{info.name}")

target_metadata = metadata

with make_engine().connect() as connection:
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()
