from logging.config import fileConfig
import os
from sqlalchemy import engine_from_config, pool
from alembic import context
from app import db  # Import your SQLAlchemy instance from app.py

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the SQLAlchemy URL from the environment variable
connectable = engine_from_config(
    config.get_section(config.config_ini_section),
    prefix="sqlalchemy.",
    poolclass=pool.NullPool)

# Use the Flask-SQLAlchemy engine
with connectable.connect() as connection:
    context.configure(
        connection=connection,
        target_metadata=db.metadata  # Use your Flask-SQLAlchemy metadata
    )

    with context.begin_transaction():
        context.run_migrations()
