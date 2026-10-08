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


# v3: the modules and the shared firmware settings. v4 adds everything else
# that took work to set up: saved playlists, the schedule, and every app and
# global setting. A v3 file still restores as it always did.
BACKUP_VERSION = 4


def _setting_fields():
    """Every app and global settings field."""
    from apps.registry import registry   # deferred: it imports every app
    from settings.schema import GLOBAL_FIELDS
    return list(GLOBAL_FIELDS) + [f for app in registry.list_all() for f in app.settings_fields]


def build_backup():
    return {
        'version': BACKUP_VERSION,
        'created': datetime.now().isoformat(),
        'modules': settings.get('modules', {}),
        # The settings shared by every module (timing, auto-home, ...).
        'firmware': current_firmware_values(settings),
        'saved_playlists': settings.get('saved_playlists', {}),
        'schedule': settings.get('schedule'),
        'settings': {f.key: settings[f.key] for f in _setting_fields() if f.key in settings},
    }


def _restore_extras(data, restored, skipped):
    """The v4 parts: each checked the way saving it from the page would be.
    Saved playlists are merged in by name, the schedule replaces the current
    one, and settings are taken one by one; anything that doesn't check out
    is left out and named in `skipped`."""
    from apps.registry import registry
    from display.pages import clean_playlist
    from display.scheduler import validate

    playlists = data.get('saved_playlists')
    if isinstance(playlists, dict):
        good = 0
        for name, playlist in playlists.items():
            try:
                if not isinstance(name, str) or not name.strip() or not isinstance(playlist, dict):
                    raise ValueError('not a playlist')
                pages, delay = clean_playlist(playlist)
            except ValueError as e:
                skipped.append(f'playlist "{name}" ({e})')
                continue
            settings.setdefault('saved_playlists', {})[name.strip()] = {'pages': pages, 'delay': delay}
            good += 1
        if good:
            restored.append(f'{good} saved playlist{"" if good == 1 else "s"}')

    if data.get('schedule') is not None:
        schedule, problem = validate(data['schedule'], {app.key for app in registry.list_all()})
        if problem:
            skipped.append(f'the schedule ({problem})')
        else:
            settings['schedule'] = schedule
            restored.append('the schedule')

    values = data.get('settings')
    if isinstance(values, dict):
        good = 0
        for field in _setting_fields():
            if field.key not in values:
                continue
            try:
                settings[field.key] = field.clean(values[field.key])
                good += 1
            except ValueError as e:
                skipped.append(str(e))
        if good:
            restored.append(f'{good} app and global setting{"" if good == 1 else "s"}')


def restore_backup(data: dict) -> dict:
    """Applies a backup to settings.json and, if hardware is connected,
    pushes the module settings to every module. Returns
    {hardware_updated, restored: [what was restored], skipped: [what wasn't,
    and why]}."""
    version = data.get('version', 1)
    restored, skipped = [], []

    if version >= 3:
        # Merge field-by-field rather than settings['modules'].update(...), which
        # would replace a module's whole dict and silently drop any field the
        # backup doesn't carry (e.g. an older backup with no toggle values).
        for mod_id, fields in data.get('modules', {}).items():
            settings['modules'].setdefault(mod_id, {}).update(fields)
        if data.get('modules'):
            restored.append(f'{len(data["modules"])} module{"" if len(data["modules"]) == 1 else "s"}')

    # The shared settings: from 'firmware', or (from an older backup) the old
    # auto-home switch and per-module release-motor values, the same way an
    # old settings.json is migrated. Anything malformed is left out.
    incoming = migrate({key: data[key] for key in ('auto_home', 'modules', 'firmware') if key in data})
    shared = {key: value for key, value in (incoming.get('firmware') or {}).items()
              if global_setting_problem(key, value) is None}
    if shared:
        settings['firmware'] = {**current_firmware_values(settings), **shared}
        restored.append('the settings for all modules')

    if version >= 4:
        _restore_extras(data, restored, skipped)

    save_settings(settings)

    result = {'hardware_updated': False, 'restored': restored, 'skipped': skipped}
    if not is_connected():
        return result

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
    result['hardware_updated'] = True
    return result
