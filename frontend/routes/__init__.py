from routes import control, settings_routes, apps_routes, module_routes, backup_routes, playlist_routes, firmware_routes

BLUEPRINTS = [
    control.bp,
    settings_routes.bp,
    apps_routes.bp,
    module_routes.bp,
    backup_routes.bp,
    playlist_routes.bp,
    firmware_routes.bp,
]
