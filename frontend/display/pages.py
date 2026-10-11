"""Checking the playlist pages the page sends (POST /update_playlist and
POST /playlists) before they're played or saved, so a bad value is refused
with a reason instead of tripping up the playlist loop later.

A page is {text, delay, style, speed}, or (from older saved playlists) a
plain string. Numbers may arrive as strings; they're stored as numbers.

A step can also be an app, {app, delay}: each time round the playlist it
shows the app's next item (see App.get_items), for at least `delay`
seconds."""
from display.layout import STYLES

MAX_DELAY_S = 3600      # an hour per page is plenty
MAX_SPEED_MS = 500      # the page's own limit for ms between modules


def _number(value, what, low, high, positive=False):
    if isinstance(value, bool):
        raise ValueError(f'{what} must be a number')
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f'{what} must be a number') from None
    if not (low <= number <= high) or (positive and number <= 0):
        raise ValueError(f'{what} must be {"more than" if positive else "at least"} {low} '
                         f'and at most {high}')
    return int(number) if number.is_integer() else number


def clean_delay(value, what='Delay'):
    """Seconds a page is held: a number above 0, up to MAX_DELAY_S."""
    return _number(value, what, 0, MAX_DELAY_S, positive=True)


def clean_page(page, n, app_keys=None):
    """Page number `n` as a dict, checked; an app step's app must be one of
    `app_keys`, if given. Raises ValueError with a reason."""
    if isinstance(page, str):
        page = {'text': page}
    if not isinstance(page, dict):
        raise ValueError(f'Page {n} must be an object')
    if 'app' in page:
        if not isinstance(page['app'], str) or (app_keys is not None and page['app'] not in app_keys):
            raise ValueError(f'Page {n} is an app that doesn\'t exist: {page["app"]}')
        cleaned = {'app': page['app']}
        if page.get('delay') is not None:
            cleaned['delay'] = clean_delay(page['delay'], f'Page {n} delay')
        return cleaned
    if not isinstance(page.get('text'), str):
        raise ValueError(f'Page {n} needs its text')
    cleaned = {'text': page['text']}
    if page.get('delay') is not None:
        cleaned['delay'] = clean_delay(page['delay'], f'Page {n} delay')
    if page.get('style') is not None:
        if page['style'] not in STYLES:
            raise ValueError(f'Page {n} has an unknown transition: {page["style"]}')
        cleaned['style'] = page['style']
    if page.get('speed') is not None:
        speed = _number(page['speed'], f'Page {n} speed', 0, MAX_SPEED_MS)
        if not isinstance(speed, int):
            raise ValueError(f'Page {n} speed must be a whole number of ms')
        cleaned['speed'] = speed
    return cleaned


def clean_playlist(data, app_keys=None):
    """(pages, delay) from a request body {pages, delay}, checked. A missing
    delay is 5 s. Raises ValueError with a reason."""
    pages = data.get('pages', [])
    if not isinstance(pages, list):
        raise ValueError('Pages must be a list')
    delay = data.get('delay')
    delay = 5 if delay is None or delay == '' else clean_delay(delay)
    return [clean_page(page, n, app_keys) for n, page in enumerate(pages, 1)], delay
