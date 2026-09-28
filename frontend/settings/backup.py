from datetime import datetime

from config import NUM_MODULES
from settings.store import settings, save_settings
from display.serial_link import send_raw, is_connected

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
        if 'modules' in data:
            settings['modules'].update(data['modules'])

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
    return True
