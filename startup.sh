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

cd "$APP_ROOT/src"
exec gunicorn --bind=0.0.0.0:8000 --timeout 600 app:app
