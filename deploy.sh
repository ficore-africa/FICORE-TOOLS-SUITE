#!/bin/bash
set -e

# Environment setup
export PYTHONPATH=/opt/render/project/src:$PYTHONPATH
export FLASK_APP=app.py

# Ensure data directory is writable
DATA_DIR=/opt/render/project/src/data
mkdir -p "$DATA_DIR"
chmod 775 "$DATA_DIR"
echo "Ensured data directory at $DATA_DIR"

# Debug: List migration scripts
echo "Listing migration scripts:"
ls -la /opt/render/project/src/migrations || echo "No migration scripts found"

# Debug: Check database file
DB_PATH=/opt/render/project/src/data/ficore.db
echo "Checking database file at $DB_PATH:"
ls -l "$DB_PATH" || echo "Database file not found"

# Install dependencies
pip install -r requirements.txt

# Run Alembic migrations
echo "Running Alembic migrations..."
python -m alembic upgrade head

# Debug: Verify database schema
echo "Verifying database schema:"
sqlite3 "$DB_PATH" ".tables" || echo "Failed to list tables"

# Note: Gunicorn startup is handled by Procfile, so no 'exec gunicorn' here
echo "Deployment setup completed. Awaiting Procfile execution."
