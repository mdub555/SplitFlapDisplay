import yfinance as yf

from apps.base import App, Frame, SettingField
from apps.builtin._shared import cache_get_or_fetch, center_page


def _fetch(settings):
    tickers = [t.strip() for t in settings.get('stocks_list', 'MSFT,GOOG,NVDA').split(',') if t.strip()]
    pages = []
    for chunk in [tickers[i:i + 3] for i in range(0, len(tickers), 3)]:
        prices = [''] * 3
        changes = [''] * 3
        for idx, sym in enumerate(chunk):
            try:
                si = yf.Ticker(sym).fast_info
                prc = si.last_price
                prev = si.previous_close
                pct = ((prc - prev) / prev) * 100
                sign = '+' if pct >= 0 else ''
                prices[idx] = f"{sym[:5]:<5} ${prc:<7.2f}"
                changes[idx] = f"{sym[:5]:<5} {sign}{pct:.2f}%"
            except Exception:
                prices[idx] = changes[idx] = f"{sym[:5]:<5} ERR"
        pages += [prices, changes]
    return pages or [['NO STOCKS', 'CONFIGURED', '']]


class StocksApp(App):
    key = 'stocks'
    name = 'Stocks'
    icon = '📈'
    desc = 'Live prices'
    settings_fields = [
        SettingField('stocks_list', 'Tickers (comma-separated)', default='MSFT,GOOG,NVDA',
                      placeholder='MSFT,GOOG,NVDA'),
    ]

    def get_pages(self, settings, cache):
        rows_pages = cache_get_or_fetch(cache, 'stocks', 60, lambda: _fetch(settings))
        return [Frame(text=center_page(*rows), delay=10) for rows in rows_pages]
