'''Japanese dictionary utilities for tokenization and suggestion generation.'''

import os
import csv

import re
import jaconv
from sudachipy import dictionary
from kivy.properties import ListProperty
from kivy.utils import get_color_from_hex
from kivy.uix.label import Label
from kivy.graphics import Color, Rectangle
from kivy.uix.widget import Widget
from app.libs.widgets.hover_behavior import HoverBehavior


def load_real_mecab_dictionary(ipadic_csv_dir):
    '''Load MeCab dictionary from IPAdic CSV files.

    Args:
        ipadic_csv_dir: Directory path containing IPAdic CSV files.

    Returns:
        List of dictionaries containing surface, base_form, and reading for each word.
    '''
    words = []
    seen = set()
    for filename in os.listdir(ipadic_csv_dir):
        if filename.endswith(".csv"):
            filepath = os.path.join(ipadic_csv_dir, filename)
            with open(filepath, 'r', encoding='euc_jp') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) >= 12:
                        surface = row[0]
                        base_form = row[10] if row[10] != '*' else surface
                        reading = row[11] if row[11] != '*' else ''
                        key = (surface, base_form, reading)
                        if key not in seen:
                            seen.add(key)
                            words.append({
                                'surface': surface,
                                'base_form': base_form,
                                'reading': reading
                            })
    return words





tokenizer = dictionary.Dictionary().create()

def contains_japanese(text):
    '''Check if text contains Japanese characters (Hiragana, Katakana, or Kanji).

    Args:
        text: String to check for Japanese characters.

    Returns:
        True if text contains Japanese characters, False otherwise.
    '''
    # Hiragana: \u3040-\u309F, Katakana: \u30A0-\u30FF, Kanji: \u4E00-\u9FFF
    return re.search(r'[\u3040-\u30FF\u4E00-\u9FFF]', text) is not None



def get_suggestions(query, vocabulary_data):
    '''Generate Japanese word suggestions based on query input.

    Args:
        query: Search query string.
        vocabulary_data: List of vocabulary dictionaries to search through.

    Returns:
        Tuple of up to 15 suggested words based on the query.
    '''
    suggestions = []
    seen = set()
    query = query.strip()
    if not query:
        return []

    if contains_japanese(query):
        query_kata = jaconv.hira2kata(query)
        query_hira = jaconv.kata2hira(query)
        first_chars = {query[0], query_kata[0], query_hira[0]}

        for qv in (query, query_kata, query_hira):
            if qv not in seen:
                suggestions.append(qv)
                seen.add(qv)
                if len(suggestions) >= 15:
                    return tuple(suggestions)

        for q in [query, query_kata]:
            for m in tokenizer.tokenize(q):
                for v in (m.surface(), m.reading_form(), m.normalized_form()):
                    if (
                        v not in seen
                        and len(suggestions) < 7
                        and contains_japanese(v)
                        and (
                            not re.match(r'^[\u3040-\u309F\u30A0-\u30FF]+$', v)
                            or (
                                any(v.startswith(fc) for fc in first_chars)
                                and len(v) > len(query) - 2
                            )
                        )
                    ):
                        suggestions.append(v)
                        seen.add(v)
                if len(suggestions) >= 15:
                    break
            if len(suggestions) >= 15:
                break
        if len(suggestions) < 15:
            surfaces = sorted({
                w['surface'] for w in vocabulary_data
                if w['surface'].startswith(query) and contains_japanese(w['surface'])
            })
            for s in surfaces:
                if len(suggestions) >= 15:
                    break
                if s not in seen and (
                    not re.match(r'^[\u3040-\u309F\u30A0-\u30FF]+$', s)
                    or (
                        any(s.startswith(fc) for fc in first_chars)
                        and len(s) > len(query) - 2
                    )
                ):
                    suggestions.append(s)
                    seen.add(s)
        return tuple(suggestions)




class HoverLabel(Label, HoverBehavior):
    '''Label widget with hover effect for suggestion dropdowns.'''

    normal_bg = ListProperty(get_color_from_hex('#FFFF00'))
    hover_bg = ListProperty(get_color_from_hex('#FFE680'))

    def __init__(self, **kwargs):
        '''Initialize HoverLabel with hover rectangle tracking.'''
        super().__init__(**kwargs)
        self.hover_rect = None
        self.bind(pos=self.update_hover_rect, size=self.update_hover_rect)

    def on_enter(self, *args):
        '''Draw hover background when mouse enters the label.'''
        with self.canvas.before:
            Color(rgba=self.hover_bg)
            self.hover_rect = Rectangle(
                pos=(self.x + 1, self.y),
                size=(self.width - 2, self.height)
            )


    def on_leave(self, *args):
        '''Remove hover background when mouse leaves the label.'''
        if self.hover_rect:
            self.canvas.before.remove(self.hover_rect)
            self.hover_rect = None

    def update_hover_rect(self, *args):
        '''Update hover rectangle position and size when widget changes.'''
        if self.hover_rect:
            self.hover_rect.pos = (self.x + 1, self.y)
            self.hover_rect.size = (self.width - 2, self.height)

class SeparatorLine(Widget):
    '''Horizontal separator line widget for visual separation.'''

    def __init__(self, **kwargs):
        '''Initialize separator line with fixed height and gray color.'''
        super().__init__(size_hint_y=None, height=1, **kwargs)
        with self.canvas:
            Color(get_color_from_hex('#D9D9D9'))
            self.line = Rectangle(pos=self.pos, size=(self.width, 1.3))
        self.bind(pos=self._update_line, size=self._update_line)

    def _update_line(self, *args):
        '''Update line position and size when widget changes.'''
        self.line.pos = self.pos
        self.line.size = (self.width, 1)
