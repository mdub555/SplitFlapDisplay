class AppRegistry:
    def __init__(self):
        self._apps = {}

    def register(self, app_instance):
        self._apps[app_instance.key] = app_instance

    def get(self, key):
        return self._apps.get(key)

    def list_all(self):
        return list(self._apps.values())


registry = AppRegistry()

# Import + register every built-in app. This is the ONLY file that needs a
# manual edit when adding a new app — routes, the settings schema, and the
# frontend all read from `registry` generically. To add an app: write a new
# apps/builtin/your_app.py implementing App.get_pages(), import its class
# here, and add it to the list below.
from apps.builtin.time_app import TimeApp
from apps.builtin.date_app import DateApp
from apps.builtin.dashboard import DashboardApp
from apps.builtin.weather import WeatherApp
from apps.builtin.metro import MetroApp
#from apps.builtin.stocks import StocksApp
from apps.builtin.sports import SportsApp
from apps.builtin.youtube import YoutubeApp
from apps.builtin.yt_comments import YoutubeCommentsApp
from apps.builtin.countdown import CountdownApp
from apps.builtin.world_clock import WorldClockApp
from apps.builtin.crypto import CryptoApp
from apps.builtin.iss import IssApp
from apps.builtin.livestream import LivestreamApp
from apps.builtin.demo import DemoApp
from apps.builtin.animations.rainbow import RainbowApp
from apps.builtin.animations.sweep import SweepApp
from apps.builtin.animations.twinkle import TwinkleApp
from apps.builtin.animations.checker import CheckerApp
from apps.builtin.animations.matrix import MatrixApp

for _cls in [
    DemoApp, LivestreamApp, DashboardApp, TimeApp, DateApp, WeatherApp,
    MetroApp, SportsApp, YoutubeApp, YoutubeCommentsApp,
    CountdownApp, WorldClockApp, CryptoApp, IssApp,
    RainbowApp, SweepApp, TwinkleApp, CheckerApp, MatrixApp,
]:
    registry.register(_cls())
