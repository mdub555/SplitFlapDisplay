from datetime import datetime

from config import NUM_MODULES
from settings.store import settings, save_settings
from settings.shared import current_firmware_values, migrate
from display.serial_link import send_raw, is_connected
from display.module_protocol import (
    TOGGLE_COMMANDS, Cmd, global_command, global_setting_problem, message, toggle_command)

# Must match the firmware defaults (HOME_OFFSET / TOTAL_STEPS in eeprom_store.cpp).
DEFAULT_HOME_OFFSET = 480
DEFAULT_TOTAL_STEPS = 4096


def build_backup():
    return {
        'version': 3,  # v3 uses the 'modules' dictionary
        'created': datetime.now().isoformat(),
        'modules': settings.get('modules', {}),
        # The settings shared by every module (timing, auto-home, ...).
        'firmware': current_firmware_values(settings),
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

    # The shared settings: from 'firmware', or (from an older backup) the old
    # auto-home switch and per-module release-motor values, the same way an
    # old settings.json is migrated. Anything malformed is left out.
    incoming = migrate({key: data[key] for key in ('auto_home', 'modules', 'firmware') if key in data})
    shared = {key: value for key, value in (incoming.get('firmware') or {}).items()
              if global_setting_problem(key, value) is None}
    if shared:
        settings['firmware'] = {**current_firmware_values(settings), **shared}

    save_settings(settings)

    if not is_connected():
        return False

    for i in range(NUM_MODULES):
        s = str(i)
        # If no config, fall back to the firmware defaults
        mod = settings['modules'].get(s) or {}
        send_raw(message(i, Cmd.SET_OFFSET, int(mod.get('homeOffset', DEFAULT_HOME_OFFSET))))
        send_raw(message(i, Cmd.SET_TOTAL_STEPS, int(mod.get('totalSteps', DEFAULT_TOTAL_STEPS))))
        # Toggles only go out if the backup actually has them (older backups and
        # modules with no saved config don't); never invent a value.
        for key in TOGGLE_COMMANDS:
            if isinstance(mod.get(key), bool):
                send_raw(toggle_command(i, key, mod[key]))
    for key, value in shared.items():
        send_raw(global_command(key, value))
    return True
