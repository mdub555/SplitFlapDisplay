"""The schedule (see display/scheduler.py): read it, or save a new one."""
from flask import Blueprint, jsonify, request

from apps.registry import registry
from display.scheduler import get_scheduler, local_now, target_for, validate
from settings.store import settings, save_settings
from routes.common import error, json_body

bp = Blueprint('schedule_routes', __name__)

EMPTY = {'enabled': False, 'default': '', 'entries': []}


def _reply():
    schedule = settings.get('schedule') or EMPTY
    now = local_now(settings)
    return jsonify(
        schedule=schedule,
        # The display's own clock, so the page can show it in the display's timezone.
        now=now.strftime('%a %H:%M'),
        # What the schedule calls for right now ('' for nothing).
        current=target_for(schedule, now) if schedule.get('enabled') else '',
    )


@bp.route('/schedule', methods=['GET', 'POST'])
def schedule():
    if request.method == 'GET':
        return _reply()
    cleaned, problem = validate(json_body(), {app.key for app in registry.list_all()})
    if problem:
        return error(problem, 400)
    settings['schedule'] = cleaned
    save_settings(settings)
    get_scheduler().check_soon()
    return _reply()
