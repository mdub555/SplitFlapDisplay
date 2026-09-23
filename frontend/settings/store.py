import json
import logging
import os

from config import CONFIG_PATH, NUM_MODULES
from settings.schema import GLOBAL_FIELDS


def _global_defaults():
    return {f.key: f.default for f in GLOBAL_FIELDS}


def _app_defaults():
    # Deferred import: apps.registry imports every builtin app module, none
    # of which import settings.store, so this is safe — but importing it at
    # module load time here would create a needless load-order dependency.
    from apps.registry import registry
    defaults = {}
    for app in registry.list_all():
        for f in app.settings_fields:
            defaults[f.key] = f.default
    return defaults


def build_defaults():
    defaults = {
        'offsets': {},
        'calibrations': {},
        'auto_home': True,
        'saved_playlists': {},
    }
    defaults.update(_global_defaults())
    defaults.update(_app_defaults())
    return defaults


def load_settings():
    defaults = build_defaults()
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r') as f:
                data = json.load(f)
                defaults.update(data)
        except Exception as e:
            logging.error(f"Failed to load {CONFIG_PATH}, using defaults: {e}")
    return defaults


def save_settings(data):
    with open(CONFIG_PATH, 'w') as f:
        json.dump(data, f, indent=4)


settings = load_settings()
