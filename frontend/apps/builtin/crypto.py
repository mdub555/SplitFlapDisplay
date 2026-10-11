import logging

import requests

from apps.base import App, SettingField
from apps.builtin._shared import cache_get_or_fetch, paired_frames, row_frames, split_list


def _fetch(coins):
    """(price line, change line) for each coin, or None if the request
    failed."""
    url = (f"https://api.coingecko.com/api/v3/simple/price"
           f"?ids={','.join(coins)}&vs_currencies=usd&include_24hr_change=true")
    try:
        data = requests.get(url, timeout=8).json()
    except Exception as e:
        logging.error(f"Crypto fetch error: {e}")
        return None
    lines = []
    for coin in coins:
        short = coin[:4].upper()
        if coin not in data:
            lines.append((f"{short:4} N/A",) * 2)
            continue
        usd = data[coin].get('usd', 0)
        chg = data[coin].get('usd_24h_change', 0) or 0
        sign = '+' if chg >= 0 else ''
        if usd >= 10000:
            pstr = f"{short} ${usd:,.0f}"
        elif usd >= 1:
            pstr = f"{short} ${usd:,.2f}"
        else:
            pstr = f"{short} ${usd:.4f}"
        lines.append((pstr, f"{short} {sign}{chg:.1f}%"))
    return lines


class CryptoApp(App):
    key = 'crypto'
    name = 'Crypto'
    icon = '₿'
    desc = 'Coin prices'
    order = 130
    settings_fields = [
        SettingField('crypto_list', 'CoinGecko IDs (comma-separated)',
                      default='bitcoin,ethereum,solana', placeholder='bitcoin,ethereum,solana'),
    ]

    def get_pages(self, settings, cache, grid):
        coins = split_list(self.setting(settings, 'crypto_list').lower(), limit=6)
        lines = cache_get_or_fetch(cache, 'crypto', 60, lambda: _fetch(coins))
        if lines is None:
            return row_frames(grid, [('CRYPTO ERR', 'CHECK CONN')], delay=8)
        if not lines:
            return row_frames(grid, [('CRYPTO', 'NO DATA')], delay=8)
        return paired_frames(grid, lines, delay=8)
