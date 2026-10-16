import json
import os
from django.conf import settings

SEEDS_DIR = os.path.join(settings.BASE_DIR, 'seed')


def load_json(filename):
    """Loads a JSON file from the seed folder."""
    filepath = os.path.join(SEEDS_DIR, filename)
    if not os.path.exists(filepath):
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def save_json(filename, data):
    """Saves data to a JSON file in the seed folder."""
    filepath = os.path.join(SEEDS_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def get_blacklist():
    """Returns the list of ignored email domains."""
    return load_json('blacklist.json')