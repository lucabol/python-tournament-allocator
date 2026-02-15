#!/bin/bash
# Azure App Service startup script for Tournament Allocator
#
# When Oryx builds with compressed output, it puts output.tar.zst in
# /home/site/wwwroot. At container startup, Azure decompresses it to a
# temp directory and sets APP_PATH to that location. The gunicorn --chdir
# must point to the decompressed location, not /home/site/wwwroot.

APP_ROOT="${APP_PATH:-/home/site/wwwroot}"

# Activate the Oryx-created virtual environment
if [ -d "$APP_ROOT/antenv/bin" ]; then
    source "$APP_ROOT/antenv/bin/activate"
fi

mkdir -p "${TOURNAMENT_DATA_DIR:-/home/data}"

# One-time migration: move data from old location to new
DATA_PATH="${TOURNAMENT_DATA_DIR:-/home/data}"
OLD_DATA_PATH="/home/site/wwwroot/data"

# Check if new location is empty (or just has .lock) AND old location exists with user data
if [ -d "$OLD_DATA_PATH" ] && [ -d "$OLD_DATA_PATH/users" ]; then
    # Check if new location is empty or only has .lock file
    FILE_COUNT=$(find "$DATA_PATH" -mindepth 1 ! -name '.lock' | wc -l)
    if [ "$FILE_COUNT" -eq 0 ]; then
        echo "Migrating data from $OLD_DATA_PATH to $DATA_PATH"
        mv "$OLD_DATA_PATH"/* "$DATA_PATH/" 2>/dev/null || true
        echo "Migration complete: data moved to $DATA_PATH"
    fi
fi

cd "$APP_ROOT/src"
exec gunicorn --bind=0.0.0.0:8000 --timeout 600 --threads 4 app:app
