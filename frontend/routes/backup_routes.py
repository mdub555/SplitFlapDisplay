from flask import Blueprint, request, jsonify

from settings.backup import build_backup, restore_backup
from routes.common import error

bp = Blueprint('backup_routes', __name__)


@bp.route('/backup_settings')
def backup_settings():
    return jsonify(build_backup())


@bp.route('/restore_settings', methods=['POST'])
def restore_settings():
    data = request.json
    if not data:
        return error('No data', 400)
    if not isinstance(data, dict):
        return error('Not a backup file', 400)
    return jsonify(status='success', **restore_backup(data))
