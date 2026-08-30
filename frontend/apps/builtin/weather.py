from datetime import datetime

import requests

from apps.base import App, Frame, SettingField
from apps.builtin._shared import get_tz, center_page, cache_get_or_fetch


def fetch_weather(settings):
    """Exposed at module level (not just as a method) so DashboardApp can
    reuse it without duplicating the OpenWeatherMap call."""
    api_key = settings.get('weather_api_key', '').strip()
    zip_code = settings.get('zip_code', '02118').strip()
    if not api_key:
        return None
    try:
        url = (f"http://api.openweathermap.org/data/2.5/weather"
               f"?zip={zip_code},us&appid={api_key}&units=imperial")
        res = requests.get(url, timeout=5).json()
        return {
            'city': res['name'].upper(),
            'temp': round(res['main']['temp']),
            'feels': round(res['main']['feels_like']),
            'desc': res['weather'][0]['main'].upper(),
            'high': round(res['main']['temp_max']),
            'low': round(res['main']['temp_min']),
        }
    except Exception:
        return None


def weather_page(settings, cache):
    w = cache_get_or_fetch(cache, 'weather', 300, lambda: fetch_weather(settings))
    now_t = datetime.now(get_tz(settings)).strftime('%I:%M%p').lstrip('0')
    if not w:
        return center_page('NO WEATHER DATA', now_t, 'CHECK API KEY')
    mcl = max(1, 14 - len(now_t))
    l1 = f"{w['city'][:mcl]} {now_t}"
    pfx = f"{w['temp']}F ({w['feels']}F) "
    l2 = pfx + w['desc'][:max(0, 15 - len(pfx))]
    l3 = f"H:{w['high']}F L:{w['low']}F"
    return center_page(l1, l2, l3)


class WeatherApp(App):
    key = 'weather'
    name = 'Weather'
    icon = '🌤️'
    desc = 'Current conditions'
    settings_fields = [
        SettingField('zip_code', 'Zip Code', default='02118', placeholder='02118'),
        SettingField('weather_api_key', 'OpenWeatherMap API Key', type='password'),
    ]

    def get_pages(self, settings, cache):
        return [Frame(text=weather_page(settings, cache), delay=5)]
