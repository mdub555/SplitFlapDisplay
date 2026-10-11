"""Connecting an app to its service with OAuth (see apps/oauth.py): the
same four routes serve every app that has an `oauth` provider."""
from flask import Blueprint, jsonify, request, url_for
from markupsafe import escape

from apps import oauth
from apps.registry import registry
from routes.common import error, json_body
from settings.store import settings

bp = Blueprint('oauth_routes', __name__)


def _oauth_app(app_key):
    app = registry.get(app_key)
    return app if app and app.oauth else None


def _connected(app):
    # Whatever the app had cached from before (or from no one) is stale now.
    registry.clear_caches()
    return jsonify(status='connected', connected=True)


@bp.route('/apps/<app_key>/oauth/start', methods=['POST'])
def start(app_key):
    """Where to send the browser to sign in, and the address it will come
    back to; `paste` says that address won't load, so the person pastes it
    into /finish instead."""
    app = _oauth_app(app_key)
    if not app:
        return error('That app has no sign-in', 404)
    callback = url_for('oauth_routes.callback', app_key=app_key, _external=True)
    try:
        url, redirect_uri = oauth.start(app, settings, callback)
    except oauth.OAuthError as e:
        return error(str(e), 400)
    return jsonify(authorize_url=url, redirect_uri=redirect_uri, paste=redirect_uri != callback)


@bp.route('/apps/<app_key>/oauth/finish', methods=['POST'])
def finish(app_key):
    """Finishes signing in from the address the browser was sent back to,
    pasted in by the person."""
    app = _oauth_app(app_key)
    if not app:
        return error('That app has no sign-in', 404)
    try:
        code, state = oauth.code_from_url(str(json_body().get('url', '')))
        oauth.finish(app, settings, code, state)
    except oauth.OAuthError as e:
        return error(str(e), 400)
    return _connected(app)


@bp.route('/apps/<app_key>/oauth/callback')
def callback(app_key):
    """Where the service sends the browser back to, for a provider that can
    redirect to this server. A page to close, either way."""
    app = _oauth_app(app_key)
    if not app:
        return 'That app has no sign-in.', 404
    try:
        code, state = oauth.code_from_url(request.url)
        oauth.finish(app, settings, code, state)
    except oauth.OAuthError as e:
        return _page(f'{app.name} was not connected', str(e)), 400
    registry.clear_caches()
    return _page(f'{app.name} is connected', 'You can close this tab.')


@bp.route('/apps/<app_key>/oauth/disconnect', methods=['POST'])
def disconnect(app_key):
    app = _oauth_app(app_key)
    if not app:
        return error('That app has no sign-in', 404)
    oauth.disconnect(app_key)
    registry.clear_caches()
    return jsonify(status='disconnected', connected=False)


def _page(title, message):
    return (f'<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            f'<title>{escape(title)}</title><body style="font-family:sans-serif;padding:2em">'
            f'<h1>{escape(title)}</h1><p>{escape(message)}</p>')
