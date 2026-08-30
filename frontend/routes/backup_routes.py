from flask import Blueprint, request, jsonify

from settings.backup import build_backup, restore_backup

bp = Blueprint('backup_routes', __name__)


@bp.route('/backup_settings')
def backup_settings():
    return jsonify(build_backup())


@bp.route('/restore_settings', methods=['POST'])
def restore_settings():
    data = request.json
    if not data:
        return jsonify(status='error', message='No data'), 400
    hw_updated = restore_backup(data)
    return jsonify(status='success', hardware_updated=hw_updated)
