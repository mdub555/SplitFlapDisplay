from flask import Blueprint, request, jsonify
import time

from config import GRID_ROWS, GRID_COLS, NUM_MODULES
from settings.store import settings, save_settings
from settings.schema import GLOBAL_FIELDS
from display.serial_link import send_raw, is_connected, ser, serial_lock

bp = Blueprint('settings_routes', __name__)


@bp.route('/config')
def get_config():
    """Static config the frontend needs at load time — grid size drives all
    dynamic grid rendering client-side instead of hardcoding 45/15/3."""
    return jsonify(
        grid_rows=GRID_ROWS,
        grid_cols=GRID_COLS,
        num_modules=NUM_MODULES,
        hardware_connected=is_connected(),
    )


@bp.route('/global_fields')
def global_fields():
    return jsonify([
        {'key': f.key, 'label': f.label, 'type': f.type, 'opts': f.opts,
         'placeholder': f.placeholder, 'default': f.default}
        for f in GLOBAL_FIELDS
    ])


@bp.route('/settings', methods=['GET', 'POST'])
def handle_settings():
    if request.method == 'POST':
        data = request.json or {}
        global_keys = {f.key for f in GLOBAL_FIELDS}
        settings.update({k: v for k, v in data.items() if k in global_keys})
        save_settings(settings)
        return jsonify(status='Saved')
    return jsonify(settings)


@bp.route('/toggle_autohome', methods=['POST'])
def toggle_autohome():
    enabled = (request.json or {}).get('enabled', True)
    settings['auto_home'] = enabled
    save_settings(settings)
    send_raw(f"m**a{1 if enabled else 0}")
    return jsonify(status='Auto-home updated')


@bp.route('/provision_module', methods=['POST'])
def provision_module():
    if not is_connected():
        return jsonify(status='error', message='Hardware not connected'), 503

    existing = {int(k) for k in settings.get('offsets', {}).keys()}
    new_id = next((i for i in range(NUM_MODULES) if i not in existing), None)
    if new_id is None:
        return jsonify(status='error', message='All module slots are already filled'), 400

    # 1. Confirm exactly one unprovisioned module is present
    with serial_lock:
        ser.reset_input_buffer()
        ser.write(b"m255d\n")
        ser.flush()
        start, buffer, found = time.time(), "", False
        while time.time() - start < 2.0:
            if ser.in_waiting:
                buffer += ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                if "m255d:" in buffer and '\n' in buffer:
                    found = True
                    break
            time.sleep(0.05)

    if not found:
        return jsonify(status="error", message="No unprovisioned module found on bus"), 404

    # 2. Assign it the target ID
    send_raw(f"m255i{new_id}")
    time.sleep(0.2)

    # 3. Push default offset/calibration so it's immediately usable
    send_raw(f"m{new_id:02d}o32")
    send_raw(f"m{new_id:02d}t4096")

    settings['offsets'][str(new_id)] = 32
    settings['calibrations'][str(new_id)] = 4096
    save_settings(settings)

    return jsonify(status="success", assigned_id=new_id)
