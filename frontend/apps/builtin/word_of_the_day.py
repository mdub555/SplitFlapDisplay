import html
import logging
import re
import xml.etree.ElementTree as ET

import requests

from apps.base import App
from apps.builtin._shared import cache_get_or_fetch, plain_text, row_frames, text_frames

FEED_URL = 'https://www.merriam-webster.com/wotd/feed/rss2'

PARTS_OF_SPEECH = ('noun', 'verb', 'adjective', 'adverb', 'pronoun', 'preposition',
                   'conjunction', 'interjection', 'phrase', 'idiom', 'abbreviation')


def _paragraphs(markup):
    """The text of each <p> (or line) in a feed item's HTML description."""
    text = re.sub(r'(?i)</p>|<br\s*/?>', '\n', markup)
    text = html.unescape(re.sub(r'<[^>]+>', '', text))
    return [p.strip() for p in text.split('\n') if p.strip()]


def parse_feed(xml_text):
    """{'word', 'part', 'meaning'} for the newest item in the feed. The
    meaning is the feed's short definition if it has one, else the
    paragraph after a WHAT IT MEANS heading, else the first definition-like
    paragraph. The part of speech is '' if the description doesn't give it."""
    item = ET.fromstring(xml_text).find('./channel/item')
    word = (item.findtext('title') or '').strip()
    paragraphs = _paragraphs(item.findtext('description') or '')

    def is_heading(p):
        return p.upper() == p or p.lower().startswith("merriam-webster's word of the day")

    def is_word_line(p):
        # "ebullient \ih-BULL-yunt\ adjective": the word, how to say it, and
        # the part of speech, and nothing else.
        return word.lower() in p.lower() and len(p) < len(word) + 40 and part_of(p)

    def part_of(p):
        return next((pos for pos in PARTS_OF_SPEECH if re.search(rf'\b{pos}\b', p.lower())), '')

    # Any tag whose name ends in "shortdef", whatever its namespace.
    meaning = next((el.text.strip() for el in item if el.tag.lower().endswith('shortdef') and el.text), '')
    if not meaning:
        after_heading = [p for prev, p in zip(paragraphs, paragraphs[1:]) if prev.upper() == 'WHAT IT MEANS']
        body = [p for p in paragraphs if not is_heading(p) and not is_word_line(p)]
        meaning = (after_heading or body or [''])[0].lstrip(': ')
    part = next((part_of(p) for p in paragraphs if is_word_line(p)), '')
    return {'word': word, 'part': part, 'meaning': meaning}


def _fetch():
    try:
        res = requests.get(FEED_URL, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        res.raise_for_status()
        return parse_feed(res.content)
    except Exception as e:
        logging.error(f'Word of the day fetch error: {e}')
        return None


class WordOfTheDayApp(App):
    key = 'word_of_the_day'
    name = 'Word of the Day'
    icon = '📖'
    desc = 'Merriam-Webster'
    order = 135

    def get_pages(self, settings, cache, grid):
        wotd = cache_get_or_fetch(cache, 'wotd', 3600, _fetch)
        if not wotd or not wotd['word']:
            return row_frames(grid, [('WORD OF THE DAY', 'FETCH ERROR')], delay=5)
        word = plain_text(wotd['word'])
        meaning = plain_text(wotd['meaning'])
        # The word, its part of speech and its meaning on one page when they
        # fit there.
        lines = [*grid.wrap(word), plain_text(wotd['part']), *grid.wrap(meaning, max_lines=len(meaning) + 1)]
        lines = [line for line in lines if line]
        if len(lines) <= grid.rows:
            return row_frames(grid, [lines], delay=8)
        # When they don't: the word on its own, then its meaning under it, as
        # many pages as the meaning takes.
        intro = [line for line in ('WORD OF THE DAY', *grid.wrap(word), plain_text(wotd['part'])) if line]
        frames = row_frames(grid, [intro], delay=6)
        if wotd['meaning']:
            frames += text_frames(grid, plain_text(wotd['meaning']), delay=6, heading=word)
        return frames
