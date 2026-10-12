"""Signing in to a service with OAuth (authorization code with PKCE), for
any app that needs it.

An app sets `oauth = OAuthProvider(...)`. Its settings modal then shows a
Connect button (routes/oauth_routes.py), and in get_pages() the app calls
self.access_token(settings) for a token that's refreshed when it runs out,
or None while it isn't connected.

Tokens are kept in their own file next to settings.json, not in settings:
the page reads the settings (GET /settings), and backups include them.
"""
import base64
import hashlib
import json
import logging
import os
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import parse_qs, urlencode, urlparse

import requests

from config import CONFIG_PATH

TOKENS_PATH = os.path.join(os.path.dirname(CONFIG_PATH) or '.', 'oauth_tokens.json')

# How long a sign-in can take, from Connect to the code coming back.
PENDING_SECONDS = 15 * 60


@dataclass
class OAuthProvider:
    """A service an app signs in to.

    `client_id_key` (and `client_secret_key`, for a service that needs a
    secret as well as PKCE) name the app's own settings fields that hold
    them, as each person registers their own app with the service.

    `redirect_uri`: the address the service sends the browser back to. Left
    as None, it's this server's own /apps/<key>/oauth/callback, and signing
    in finishes on its own. A service that only allows https or loopback
    addresses (Spotify) gets a fixed loopback one instead: the browser lands
    on a page that doesn't load, and the person pastes its address into the
    app's settings to finish."""
    name: str
    authorize_url: str
    token_url: str
    client_id_key: str
    scopes: list = field(default_factory=list)
    client_secret_key: Optional[str] = None
    redirect_uri: Optional[str] = None
    extra_params: dict = field(default_factory=dict)   # added to the authorize URL
    help: str = ''                                     # setup steps, shown in the settings modal


class OAuthError(Exception):
    """Signing in didn't work; the message says why, for the page."""


_lock = threading.Lock()
_pending = {}   # state -> {app, verifier, redirect_uri, started}


def _load():
    try:
        with open(TOKENS_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        logging.error(f'Could not read {TOKENS_PATH}: {e}')
        return {}


def _save(tokens):
    os.makedirs(os.path.dirname(TOKENS_PATH) or '.', exist_ok=True)
    temp = f'{TOKENS_PATH}.tmp'
    # Only the owner may read it: it holds what lets the app act as you.
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(tokens, f, indent=2)
    os.replace(temp, TOKENS_PATH)


def is_connected(app_key):
    with _lock:
        return app_key in _load()


def disconnect(app_key):
    with _lock:
        tokens = _load()
        if tokens.pop(app_key, None) is not None:
            _save(tokens)


def _client(provider, settings):
    client_id = str(settings.get(provider.client_id_key, '')).strip()
    secret = str(settings.get(provider.client_secret_key, '')).strip() if provider.client_secret_key else None
    return client_id, secret


def start(app, settings, callback_uri):
    """Begins signing in: the address to send the browser to, and the
    redirect address it will come back to. `callback_uri` is this server's
    callback, used unless the provider has a fixed one."""
    provider = app.oauth
    client_id, secret = _client(provider, settings)
    if not client_id:
        raise OAuthError(f'Enter the {provider.name} Client ID first')
    if provider.client_secret_key and not secret:
        raise OAuthError(f'Enter the {provider.name} Client Secret first')
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    state = secrets.token_urlsafe(24)
    redirect_uri = provider.redirect_uri or callback_uri
    now = time.time()
    with _lock:
        for old in [s for s, p in _pending.items() if now - p['started'] > PENDING_SECONDS]:
            del _pending[old]
        _pending[state] = {'app': app.key, 'verifier': verifier, 'redirect_uri': redirect_uri, 'started': now}
    params = {
        'response_type': 'code', 'client_id': client_id, 'redirect_uri': redirect_uri, 'state': state,
        'code_challenge_method': 'S256', 'code_challenge': challenge, **provider.extra_params,
    }
    if provider.scopes:
        params['scope'] = ' '.join(provider.scopes)
    return f'{provider.authorize_url}?{urlencode(params)}', redirect_uri


def code_from_url(url):
    """(code, state) from the address the service sent the browser back to;
    raises OAuthError if it says signing in was refused, or has no code."""
    query = parse_qs(urlparse(url.strip()).query)
    if 'error' in query:
        raise OAuthError(f"Sign-in was refused: {query['error'][0]}")
    if 'code' not in query or 'state' not in query:
        raise OAuthError("That address has no sign-in code in it: paste the whole address from the browser's address bar")
    return query['code'][0], query['state'][0]


def finish(app, settings, code, state):
    """Trades the code from the redirect for tokens, and keeps them."""
    with _lock:
        pending = _pending.pop(state, None)
    if not pending or pending['app'] != app.key or time.time() - pending['started'] > PENDING_SECONDS:
        raise OAuthError('That sign-in has expired or was for something else: press Connect and try again')
    provider = app.oauth
    client_id, secret = _client(provider, settings)
    data = {'grant_type': 'authorization_code', 'code': code, 'redirect_uri': pending['redirect_uri'],
            'client_id': client_id, 'code_verifier': pending['verifier']}
    _store(app.key, _token_request(provider, data, secret))


def _token_request(provider, data, secret):
    if secret:
        data = {**data, 'client_secret': secret}
    try:
        res = requests.post(provider.token_url, data=data, timeout=10)
    except requests.RequestException as e:
        raise OAuthError(f'Could not reach {provider.name}: {e}') from None
    try:
        body = res.json()
    except ValueError:
        body = {}
    if not res.ok or 'access_token' not in body:
        reason = body.get('error_description') or body.get('error') or f'HTTP {res.status_code}'
        raise OAuthError(f'{provider.name} refused: {reason}')
    return body


def _store(app_key, body, old=None):
    entry = {
        'access_token': body['access_token'],
        # A refresh may or may not hand out a new refresh token.
        'refresh_token': body.get('refresh_token') or (old or {}).get('refresh_token'),
        'expires_at': time.time() + float(body.get('expires_in', 3600)),
    }
    with _lock:
        tokens = _load()
        tokens[app_key] = entry
        _save(tokens)
    return entry


def access_token(app, settings):
    """A current access token for the app, refreshed if it has run out (or
    is about to), or None if it isn't connected or the refresh fails."""
    with _lock:
        entry = _load().get(app.key)
    if not entry:
        return None
    if entry.get('expires_at', 0) - 60 > time.time():
        return entry['access_token']
    if not entry.get('refresh_token'):
        return None
    client_id, secret = _client(app.oauth, settings)
    data = {'grant_type': 'refresh_token', 'refresh_token': entry['refresh_token'], 'client_id': client_id}
    try:
        return _store(app.key, _token_request(app.oauth, data, secret), entry)['access_token']
    except OAuthError as e:
        logging.error(f'{app.oauth.name} token refresh failed: {e}')
        return None
