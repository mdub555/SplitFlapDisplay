from datetime import datetime

from config import NUM_MODULES
from settings.store import settings, save_settings
from display.serial_link import send_raw, is_connected
from display.module_protocol import TOGGLE_COMMANDS, toggle_command

# Must match the firmware defaults (HOME_OFFSET / TOTAL_STEPS in eeprom_store.cpp).
DEFAULT_HOME_OFFSET = 480
DEFAULT_TOTAL_STEPS = 4096


def build_backup():
    return {
        'version': 3,  # v3 uses the 'modules' dictionary
        'created': datetime.now().isoformat(),
        'modules': settings.get('modules', {}),
        'auto_home': settings.get('auto_home', True),
    }


def restore_backup(data: dict) -> bool:
    """Applies module settings to settings.json and, if hardware is
    connected, pushes them to every module. Returns whether hardware was
    updated."""
    version = data.get('version', 1)

    if version >= 3:
        # Merge field-by-field rather than settings['modules'].update(...), which
        # would replace a module's whole dict and silently drop any field the
        # backup doesn't carry (e.g. an older backup with no toggle values).
        for mod_id, fields in data.get('modules', {}).items():
            settings['modules'].setdefault(mod_id, {}).update(fields)

    if 'auto_home' in data:
        settings['auto_home'] = data['auto_home']

    save_settings(settings)

    if not is_connected():
        return False

    for i in range(NUM_MODULES):
        s = str(i)
        # If no config, fall back to the firmware defaults
        mod = settings['modules'].get(s) or {}
        send_raw(f"m{i:02d}o{int(mod.get('homeOffset', DEFAULT_HOME_OFFSET))}")
        send_raw(f"m{i:02d}t{int(mod.get('totalSteps', DEFAULT_TOTAL_STEPS))}")
        # Toggles only go out if the backup actually has them (older backups and
        # modules with no saved config don't); never invent a value.
        for key in TOGGLE_COMMANDS:
            if isinstance(mod.get(key), bool):
                send_raw(toggle_command(i, key, mod[key]))
    return True
