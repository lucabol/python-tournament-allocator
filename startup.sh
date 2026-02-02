#!/bin/bash

# Azure App Service startup script for Flask application
# This script is executed when the container starts

# Ensure data directory exists with proper permissions
mkdir -p /home/site/wwwroot/data
chmod 755 /home/site/wwwroot/data

# Initialize data files if they don't exist
cd /home/site/wwwroot

if [ ! -f "data/teams.yaml" ]; then
    echo "Initializing teams.yaml"
    touch data/teams.yaml
fi

if [ ! -f "data/courts.csv" ]; then
    echo "Initializing courts.csv"
    touch data/courts.csv
fi

if [ ! -f "data/constraints.yaml" ]; then
    echo "Initializing constraints.yaml"
    cat > data/constraints.yaml << EOF
match_duration: 30
break_duration: 10
max_matches_per_team_per_day: 5
min_rest_time: 15
scoring_format: best_of_3
EOF
fi

if [ ! -f "data/results.yaml" ]; then
    echo "Initializing results.yaml"
    cat > data/results.yaml << EOF
pool_play: {}
bracket: {}
EOF
fi

if [ ! -f "data/schedule.yaml" ]; then
    echo "Initializing schedule.yaml"
    touch data/schedule.yaml
fi

# Start the application with gunicorn
# Using 4 workers and binding to port 8000 (Azure App Service default)
cd src
gunicorn --bind=0.0.0.0:8000 --workers=4 --timeout=600 app:app
