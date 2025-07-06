#!/bin/bash

# Initialize database
echo "Initializing database..."
python -m src.backend.cli.setup_db

# Start the application
echo "Starting Streamlit application..."
exec "$@"
