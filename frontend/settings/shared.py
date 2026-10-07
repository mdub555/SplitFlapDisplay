"""The settings every module shares (see GLOBAL_SETTINGS), stored under
settings['firmware']. No side effects on import, unlike settings.store."""

from display.module_protocol import GLOBAL_SETTINGS


def current_firmware_values(settings):
    """The stored settings shared by every module, with defaults for anything
    missing (a settings.json from before a setting existed, or a partial dict)."""
    stored = settings.get('firmware') or {}
    return {key: stored.get(key, spec['default']) for key, spec in GLOBAL_SETTINGS.items()}


def migrate(stored):
    """Brings a settings dict saved by an older version up to date, in place.

    Auto-home on boot and release motor when idle used to be set per module
    (with auto-home also kept as a top-level 'auto_home' switch); they're now
    shared by every module, under 'firmware' with the other shared settings.
    """
    firmware = dict(stored.get('firmware') or {})
    if 'auto_home' in stored:
        firmware.setdefault('autoHome', bool(stored.pop('auto_home')))
    # Keep the modules' release-motor setting if they all agreed on one.
    released = {mod.get('motorRelease') for mod in (stored.get('modules') or {}).values()
                if isinstance(mod, dict) and isinstance(mod.get('motorRelease'), bool)}
    if len(released) == 1:
        firmware.setdefault('motorRelease', released.pop())
    if firmware:
        stored['firmware'] = firmware
    return stored
