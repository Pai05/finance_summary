#!/usr/bin/env bash
# Exit on error
set -o errexit

# Install Python dependencies from requirements.txt
pip install -r requirements.txt

# Create the database tables on the server
python db_manager.py