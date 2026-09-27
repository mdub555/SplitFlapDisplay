from datetime import datetime

from config import NUM_MODULES
from settings.store import settings, save_settings
from display.serial_link import send_raw, is_connected


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
        mod = settings['modules'].get(s)
        if mod:
            send_raw(f"m{i:02d}o{int(mod.get('homeOffset', 2832))}")
            send_raw(f"m{i:02d}t{int(mod.get('totalSteps', 4096))}")
        else:
            # If no config, use defaults
            send_raw(f"m{i:02d}o2832")
            send_raw(f"m{i:02d}t4096")
    return True
