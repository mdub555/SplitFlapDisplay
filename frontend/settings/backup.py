from datetime import datetime

from config import NUM_MODULES
from settings.store import settings, save_settings
from display.serial_link import send_raw, is_connected


def build_backup():
    return {
        'version': 2,  # v1 also included tuned_chars (per-character EEPROM
                        # overrides); dropped since v8-module fine-tuning is
                        # no longer needed. A v1 backup can still be restored
                        # — restore_backup() just ignores any tuned_chars key.
        'created': datetime.now().isoformat(),
        'offsets': settings['offsets'],
        'calibrations': settings['calibrations'],
    }


def restore_backup(data: dict) -> bool:
    """Applies offsets/calibrations to settings.json and, if hardware is
    connected, pushes them to every module. Returns whether hardware was
    updated."""
    if 'offsets' in data:
        settings['offsets'].update(data['offsets'])
    if 'calibrations' in data:
        settings['calibrations'].update(data['calibrations'])
    save_settings(settings)

    if not is_connected():
        return False

    for i in range(NUM_MODULES):
        s = str(i)
        send_raw(f"m{i:02d}o{int(settings['offsets'].get(s, 2832))}")
        send_raw(f"m{i:02d}t{int(settings['calibrations'].get(s, 4096))}")
    return True
