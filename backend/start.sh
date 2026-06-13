#!/bin/sh
echo "Running database migrations..."
PYTHONPATH=backend alembic upgrade head
echo "Starting server..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2 --timeout-keep-alive 120 --access-log --log-level info
