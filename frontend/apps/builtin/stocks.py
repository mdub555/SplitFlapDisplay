from apps.base import App, SettingField
from apps.builtin._shared import cache_get_or_fetch, paired_items, row_frames, split_list


def _fetch(tickers):
    """(price line, change line) for each ticker."""
    import yfinance as yf   # here, so the app's module imports without it

    lines = []
    for sym in tickers:
        try:
            si = yf.Ticker(sym).fast_info
            prc = si.last_price
            prev = si.previous_close
            pct = ((prc - prev) / prev) * 100
            sign = '+' if pct >= 0 else ''
            lines.append((f"{sym[:5]:<5} ${prc:<7.2f}", f"{sym[:5]:<5} {sign}{pct:.2f}%"))
        except Exception:
            lines.append((f"{sym[:5]:<5} ERR",) * 2)
    return lines


class StocksApp(App):
    key = 'stocks'
    name = 'Stocks'
    icon = '📈'
    desc = 'Live prices'
    # Needs yfinance, which isn't in requirements.txt.
    enabled = False
    settings_fields = [
        SettingField('stocks_list', 'Tickers (comma-separated)', default='MSFT,GOOG,NVDA',
                      placeholder='MSFT,GOOG,NVDA'),
    ]

    def get_items(self, settings, cache, grid):
        tickers = split_list(self.setting(settings, 'stocks_list'))
        lines = cache_get_or_fetch(cache, 'stocks', 60, lambda: _fetch(tickers))
        if not lines:
            return [row_frames(grid, [('NO STOCKS', 'CONFIGURED')], delay=10)]
        return paired_items(grid, lines, delay=10)
