import logging

import requests

from apps.base import App, Frame, SettingField
from apps.builtin._shared import cache_get_or_fetch, center_page


def _fetch(settings):
    coins = [c.strip().lower() for c in
             settings.get('crypto_list', 'bitcoin,ethereum,solana').split(',') if c.strip()][:6]
    url = (f"https://api.coingecko.com/api/v3/simple/price"
           f"?ids={','.join(coins)}&vs_currencies=usd&include_24hr_change=true")
    try:
        data = requests.get(url, timeout=8).json()
        pages = []
        for chunk in [coins[i:i + 3] for i in range(0, len(coins), 3)]:
            prices, changes = [''] * 3, [''] * 3
            for idx, coin in enumerate(chunk):
                if coin not in data:
                    prices[idx] = changes[idx] = f"{coin[:4].upper():4} N/A"
                    continue
                usd = data[coin].get('usd', 0)
                chg = data[coin].get('usd_24h_change', 0) or 0
                short = coin[:4].upper()
                sign = '+' if chg >= 0 else ''
                if usd >= 10000:
                    pstr = f"{short} ${usd:,.0f}"
                elif usd >= 1:
                    pstr = f"{short} ${usd:,.2f}"
                else:
                    pstr = f"{short} ${usd:.4f}"
                prices[idx] = pstr
                changes[idx] = f"{short} {sign}{chg:.1f}%"
            pages += [prices, changes]
        return pages or [('CRYPTO', 'NO DATA', '')]
    except Exception as e:
        logging.error(f"Crypto fetch error: {e}")
        return [('CRYPTO ERR', 'CHECK CONN', '')]


class CryptoApp(App):
    key = 'crypto'
    name = 'Crypto'
    icon = '₿'
    desc = 'Coin prices'
    settings_fields = [
        SettingField('crypto_list', 'CoinGecko IDs (comma-separated)',
                      default='bitcoin,ethereum,solana', placeholder='bitcoin,ethereum,solana'),
    ]

    def get_pages(self, settings, cache):
        rows_pages = cache_get_or_fetch(cache, 'crypto', 60, lambda: _fetch(settings))
        return [Frame(text=center_page(*rows), delay=8) for rows in rows_pages]
