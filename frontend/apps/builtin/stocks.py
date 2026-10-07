import yfinance as yf

from apps.base import App, SettingField
from apps.builtin._shared import cache_get_or_fetch, row_frames, split_list


def _fetch(tickers):
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
        tickers = split_list(self.setting(settings, 'stocks_list'))
        return row_frames(cache_get_or_fetch(cache, 'stocks', 60, lambda: _fetch(tickers)), delay=10)
