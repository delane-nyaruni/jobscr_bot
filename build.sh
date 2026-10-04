#!/usr/bin/env bash
# exit on error
set -o errexit

# 1. Install dependencies
pip install -r requirements.txt

# 2. Collect static files for WhiteNoise (Fixes your "Beautiful UI")
python manage.py collectstatic --no-input --settings=dfms_backend.settings