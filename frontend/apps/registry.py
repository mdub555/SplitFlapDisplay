import importlib
import pkgutil

from apps.base import App

# Top-level settings.json keys that aren't app or global settings fields, so
# no field may use them.
RESERVED_SETTINGS = {'modules', 'firmware', 'saved_playlists', 'schedule', 'volume'}


class AppRegistry:
    def __init__(self):
        self._apps = {}
        self._caches = {}

    def register(self, app_instance):
        """Adds an app, after checking it won't clash with the ones already
        here: settings live in one flat dict, so two fields with the same key
        would silently share a value."""
        from settings.schema import GLOBAL_FIELDS   # deferred: it imports apps.base
        app = app_instance
        name = type(app).__name__
        if not app.key:
            raise ValueError(f'{name} has no key')
        if app.key in self._apps:
            raise ValueError(f'{name}: app key {app.key!r} is already used by '
                             f'{type(self._apps[app.key]).__name__}')
        owners = {f.key: 'Global Settings' for f in GLOBAL_FIELDS}
        owners.update((key, 'settings.json') for key in RESERVED_SETTINGS)
        for other in self._apps.values():
            owners.update((f.key, type(other).__name__) for f in other.settings_fields)
        for f in app.settings_fields:
            if f.key in owners:
                raise ValueError(f'{name}: setting {f.key!r} is already used by {owners[f.key]}')
        if app.oauth is not None:
            own = {f.key for f in app.settings_fields}
            for key in (app.oauth.client_id_key, app.oauth.client_secret_key):
                if key is not None and key not in own:
                    raise ValueError(f"{name}: oauth needs a settings field {key!r}")
        unknown = set(app.global_settings) - {f.key for f in GLOBAL_FIELDS}
        if unknown:
            raise ValueError(f'{name}: global_settings names unknown fields {sorted(unknown)}')
        self._apps[app.key] = app

    def get(self, key):
        return self._apps.get(key)

    def list_all(self):
        """Every app, in the order the Apps grid shows them."""
        return sorted(self._apps.values(), key=lambda a: (a.order, a.name.lower()))

    def cache_for(self, key):
        """The app's own cache dict (see App.get_pages)."""
        return self._caches.setdefault(key, {})

    def clear_caches(self):
        """Empties every app's cache, so new settings (a zip code, an API key)
        show on the next pass instead of after the old data expires."""
        self._caches = {}


def discover(package='apps.builtin'):
    """Every enabled App subclass with a key in `package` and the packages
    under it, by importing each module there. Adding an app is only writing
    its file."""
    pkg = importlib.import_module(package)
    for info in pkgutil.walk_packages(pkg.__path__, f'{package}.'):
        importlib.import_module(info.name)
    found, todo = [], list(App.__subclasses__())
    while todo:
        cls = todo.pop()
        todo.extend(cls.__subclasses__())
        if cls.__module__.startswith(f'{package}.') and cls.key and cls.enabled and cls not in found:
            found.append(cls)
    return found


# A module that doesn't import or an app that clashes stops the server
# starting: it's a mistake in the code, and failing loudly gets it fixed.
registry = AppRegistry()
for _cls in discover():
    registry.register(_cls())
