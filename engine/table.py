# -*- coding: utf-8 -*-
# vim:et sts=4 sw=4
#
# ibus-table - The Tables engine for IBus
#
# Copyright (c) 2008-2009 Yu Yuwei <acevery@gmail.com>
# Copyright (c) 2009-2014 Caius "kaio" CHANCE <me@kaio.net>
# Copyright (c) 2012-2021 Mike FABIAN <mfabian@redhat.com>
# Copyright (c) 2019      Peng Wu <alexepico@gmail.com>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

'''
This file implements the ibus engine for ibus-table
'''

__all__ = (
    "TabEngine",
)

from typing import Any
from typing import List
from typing import Tuple
from typing import Iterable
from typing import Dict
from typing import Union
from typing import Optional
import sys
import os
import re
import copy
import time
import logging
IMPORT_SIMPLEAUDIO_SUCCESSFUL = False
try:
    import simpleaudio # type: ignore
    IMPORT_SIMPLEAUDIO_SUCCESSFUL = True
except (ImportError,):
    IMPORT_SIMPLEAUDIO_SUCCESSFUL = False

from gettext import dgettext
_ = lambda a: dgettext('ibus-table', a)
N_ = lambda a: a
from gi import require_version # type: ignore
require_version('IBus', '1.0')
from gi.repository import IBus # type: ignore
require_version('Gio', '2.0')
from gi.repository import Gio
require_version('GLib', '2.0')
from gi.repository import GLib
#import tabsqlitedb
from gi.repository import GObject
import it_util

LOGGER = logging.getLogger('ibus-table')

DEBUG_LEVEL = int(0)

def ascii_ispunct(character):
    '''
    Use our own function instead of ascii.ispunct()
    from “from curses import ascii” because the behaviour
    of the latter is kind of weird. In Python 3.3.2 it does
    for example:

        # >>> from curses import ascii
        # >>> ascii.ispunct('.')
        # True
        # >>> ascii.ispunct(u'.')
        # True
        # >>> ascii.ispunct('a')
        # False
        # >>> ascii.ispunct(u'a')
        # False
        # >>>
        # >>> ascii.ispunct(u'あ')
        # True
        # >>> ascii.ispunct('あ')
        # True
        # >>>

    あ isn’t punctuation. ascii.ispunct() only really works
    in the ascii range, it returns weird results when used
    over the whole unicode range. Maybe we should better use
    unicodedata.category(), which works fine to figure out
    what is punctuation for all of unicode. But at the moment
    I am only porting from Python2 to Python3 and just want to
    preserve the original behaviour for the moment.

    By the way, Python 3.6.6 does not seem the  above bug
    anymore, in Python 3.6.6 we  get

        # >>> from curses import ascii
        # >>> ascii.ispunct('あ')
        # False
        # >>>

    Examples:

    >>> ascii_ispunct('.')
    True
    >>> ascii_ispunct('a')
    False
    >>> ascii_ispunct('あ')
    False
    '''
    return bool(character in '''!"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~''')

THEME: Dict[str, Union[bool, int]] = {
        "dark": False,
        "candidate_text": it_util.color_string_to_argb('#1973a2'),
        "system_phrase": it_util.color_string_to_argb('#000000'),
        "user_phrase": it_util.color_string_to_argb('#7700c3'),
        "system_phrase_unused": it_util.color_string_to_argb('#000000'),
        "debug_text": it_util.color_string_to_argb('#00ff00'),
        "preedit_left": it_util.color_string_to_argb('#f90f0f'), # bright red
        "preedit_right": it_util.color_string_to_argb('#1edc1a'), # light green
        "preedit_invalid": it_util.color_string_to_argb('#ff00ff'), # magenta
        "aux_text": it_util.color_string_to_argb('#9515b5'),
}

THEME_DARK: Dict[str, Union[bool, int]] = {
        "dark": True,
        "candidate_text": it_util.color_string_to_argb('#7bc8f0'),
        "system_phrase": it_util.color_string_to_argb('#ffffff'),
        "user_phrase": it_util.color_string_to_argb('#c078ee'),
        "system_phrase_unused": it_util.color_string_to_argb('#f0f0f0'),
        "debug_text": it_util.color_string_to_argb('#00ff00'),
        "preedit_left": it_util.color_string_to_argb('#f9f90f'),
        "preedit_right": it_util.color_string_to_argb('#1edc1a'),
        "preedit_invalid": it_util.color_string_to_argb('#ff00ff'),
        "aux_text": it_util.color_string_to_argb('#dd70f9'),
}

__HALF_FULL_TABLE: List[Tuple[int, int, int]] = [
    (0x0020, 0x3000, 1),
    (0x0021, 0xFF01, 0x5E),
    (0x00A2, 0xFFE0, 2),
    (0x00A5, 0xFFE5, 1),
    (0x00A6, 0xFFE4, 1),
    (0x00AC, 0xFFE2, 1),
    (0x00AF, 0xFFE3, 1),
    (0x20A9, 0xFFE6, 1),
    (0xFF61, 0x3002, 1),
    (0xFF62, 0x300C, 2),
    (0xFF64, 0x3001, 1),
    (0xFF65, 0x30FB, 1),
    (0xFF66, 0x30F2, 1),
    (0xFF67, 0x30A1, 1),
    (0xFF68, 0x30A3, 1),
    (0xFF69, 0x30A5, 1),
    (0xFF6A, 0x30A7, 1),
    (0xFF6B, 0x30A9, 1),
    (0xFF6C, 0x30E3, 1),
    (0xFF6D, 0x30E5, 1),
    (0xFF6E, 0x30E7, 1),
    (0xFF6F, 0x30C3, 1),
    (0xFF70, 0x30FC, 1),
    (0xFF71, 0x30A2, 1),
    (0xFF72, 0x30A4, 1),
    (0xFF73, 0x30A6, 1),
    (0xFF74, 0x30A8, 1),
    (0xFF75, 0x30AA, 2),
    (0xFF77, 0x30AD, 1),
    (0xFF78, 0x30AF, 1),
    (0xFF79, 0x30B1, 1),
    (0xFF7A, 0x30B3, 1),
    (0xFF7B, 0x30B5, 1),
    (0xFF7C, 0x30B7, 1),
    (0xFF7D, 0x30B9, 1),
    (0xFF7E, 0x30BB, 1),
    (0xFF7F, 0x30BD, 1),
    (0xFF80, 0x30BF, 1),
    (0xFF81, 0x30C1, 1),
    (0xFF82, 0x30C4, 1),
    (0xFF83, 0x30C6, 1),
    (0xFF84, 0x30C8, 1),
    (0xFF85, 0x30CA, 6),
    (0xFF8B, 0x30D2, 1),
    (0xFF8C, 0x30D5, 1),
    (0xFF8D, 0x30D8, 1),
    (0xFF8E, 0x30DB, 1),
    (0xFF8F, 0x30DE, 5),
    (0xFF94, 0x30E4, 1),
    (0xFF95, 0x30E6, 1),
    (0xFF96, 0x30E8, 6),
    (0xFF9C, 0x30EF, 1),
    (0xFF9D, 0x30F3, 1),
    (0xFFA0, 0x3164, 1),
    (0xFFA1, 0x3131, 30),
    (0xFFC2, 0x314F, 6),
    (0xFFCA, 0x3155, 6),
    (0xFFD2, 0x315B, 9),
    (0xFFE9, 0x2190, 4),
    (0xFFED, 0x25A0, 1),
    (0xFFEE, 0x25CB, 1)]

def unichar_half_to_full(char: str) -> str:
    '''
    Convert a character to full width if possible.

    :param char: A character to convert to full width

    Examples:

    >>> unichar_half_to_full('a')
    'ａ'
    >>> unichar_half_to_full('ａ')
    'ａ'
    >>> unichar_half_to_full('☺')
    '☺'
    '''
    code = ord(char)
    for half, full, size in __HALF_FULL_TABLE:
        if half <= code < half + size:
            return chr(full + code - half)
    return char

def unichar_full_to_half(char: str) -> str:
    '''
    Convert a character to half width if possible.

    :param char: A character to convert to half width
    :type char: String
    :rtype: String

    Examples:

    >>> unichar_full_to_half('ａ')
    'a'
    >>> unichar_full_to_half('a')
    'a'
    >>> unichar_full_to_half('☺')
    '☺'
    '''
    code = ord(char)
    for half, full, size in __HALF_FULL_TABLE:
        if full <= code < full + size:
            return chr(half + code - full)
    return char

SAVE_USER_COUNT_MAX = 16
SAVE_USER_TIMEOUT = 30 # in seconds

########################
### Engine Class #####
####################
class TabEngine(IBus.EngineSimple):
    '''The IM Engine for Tables'''

    def __init__(self, bus, obj_path, database, unit_test=False) -> None:
        super().__init__(connection=bus.get_connection(),
                         object_path=obj_path)
        global DEBUG_LEVEL
        try:
            DEBUG_LEVEL = int(str(os.getenv('IBUS_TABLE_DEBUG_LEVEL')))
        except (TypeError, ValueError):
            DEBUG_LEVEL = int(0)

        self._unit_test = unit_test
        self._input_purpose = 0
        self._has_input_purpose = False
        if hasattr(IBus, 'InputPurpose'):
            self._has_input_purpose = True
        self._bus = bus
        # this is the backend sql db we need for our IME
        # we receive this db from IMEngineFactory
        #self.db = tabsqlitedb.TabSqliteDb( name = dbname )
        self.database = database
        self._setup_pid = 0
        self._icon_dir = '%s%s%s%s' % (os.getenv('IBUS_TABLE_LOCATION'),
                                       os.path.sep, 'icons', os.path.sep)
        self._engine_name = os.path.basename(
            self.database.filename).replace('.db', '').replace(' ', '_')
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'self._engine_name = %s', self._engine_name)

        self._gsettings = Gio.Settings(
            schema='org.freedesktop.ibus.engine.table',
            path='/org/freedesktop/ibus/engine/table/%s/' %self._engine_name)
        self._gsettings.connect('changed', self.on_gsettings_value_changed)

        self._prop_dict: Dict[str, IBus.Property] = {}
        self._sub_props_dict: Dict[str, IBus.PropList] = {}
        self.main_prop_list: List[IBus.Property] = []
        self.chinese_mode_menu: Dict[str, Any] = {}
        self.chinese_mode_properties: Dict[str, Any] = {}
        self.input_mode_menu: Dict[str, Any] = {}
        self.input_mode_properties: Dict[str, Any] = {}
        self.letter_width_menu: Dict[str, Any] = {}
        self.letter_width_properties: Dict[str, Any] = {}
        self.punctuation_width_menu: Dict[str, Any] = {}
        self.punctuation_width_properties: Dict[str, Any] = {}
        self.pinyin_mode_menu: Dict[str, Any] = {}
        self.pinyin_mode_properties: Dict[str, Any] = {}
        self.suggestion_mode_menu: Dict[str, Any] = {}
        self.suggestion_mode_properties: Dict[str, Any] = {}
        self.onechar_mode_menu: Dict[str, Any] = {}
        self.onechar_mode_properties: Dict[str, Any] = {}
        self.autocommit_mode_menu: Dict[str, Any] = {}
        self.autocommit_mode_properties: Dict[str, Any] = {}
        self._setup_property: Optional[IBus.Property] = None
        self.theme = THEME

        self._keybindings: Dict[str, List[str]] = {}
        self._hotkeys: Optional[it_util.HotKeys] = None

        # self._ime_py: Indicates whether this table supports pinyin mode
        self._ime_py = self.database.ime_properties.get('pinyin_mode')
        if self._ime_py:
            self._ime_py = bool(self._ime_py.lower() == u'true')
        else:
            LOGGER.info('We could not find "pinyin_mode" entry in database, '
                        'is it an outdated database?')
            self._ime_py = False

        # self._ime_sg: Indicates whether this table supports suggestion mode
        self._ime_sg = self.database.ime_properties.get('suggestion_mode')
        if self._ime_sg:
            self._ime_sg = bool(self._ime_sg.lower() == u'true')
        else:
            LOGGER.info(
                'We could not find "suggestion_mode" entry in database, '
                'is it an outdated database?')
            self._ime_sg = False

        self._symbol = self.database.ime_properties.get('symbol')
        if self._symbol is None or self._symbol == u'':
            self._symbol = self.database.ime_properties.get('status_prompt')
        if self._symbol is None:
            self._symbol = u''
        # some Chinese tables have “STATUS_PROMPT = CN” replace it
        # with the shorter and nicer “中”:
        if self._symbol == u'CN':
            self._symbol = u'中'
        # workaround for the translit and translit-ua tables which
        # have 2 character symbols. '☑' + self._symbol then is
        # 3 characters and currently gnome-shell ignores symbols longer
        # than 3 characters:
        if self._symbol == u'Ya':
            self._symbol = u'Я'
        if self._symbol == u'Yi':
            self._symbol = u'Ї'
        # now we check and update the valid input characters
        self._valid_input_chars = self.database.ime_properties.get(
            'valid_input_chars')
        self._pinyin_valid_input_chars = u'abcdefghijklmnopqrstuvwxyz!@#$%'

        self._debug_level = it_util.variant_to_value(
            self._gsettings.get_value('debuglevel'))
        if self._debug_level < 0:
            self._debug_level = 0 # minimum
        if self._debug_level > 255:
            self._debug_level = 255 # maximum
        DEBUG_LEVEL = self._debug_level

        self._dynamic_adjust = it_util.variant_to_value(
            self._gsettings.get_user_value('dynamicadjust'))
        if self._dynamic_adjust is None:
            self._dynamic_adjust = self.database.ime_properties.get(
                'dynamic_adjust')
            if self._dynamic_adjust:
                self._dynamic_adjust = bool(
                    self._dynamic_adjust.lower() == u'true')
            else:
                LOGGER.info(
                    'Could not find "dynamic_adjust" entry from database, '
                    + 'is it an outdated database?')
        if self._dynamic_adjust is None:
            self._dynamic_adjust = it_util.variant_to_value(
                self._gsettings.get_value('dynamicadjust'))

        self._single_wildcard_char = it_util.variant_to_value(
            self._gsettings.get_user_value('singlewildcardchar'))
        if self._single_wildcard_char is None:
            self._single_wildcard_char = self.database.ime_properties.get(
                'single_wildcard_char')
        if self._single_wildcard_char is None:
            self._single_wildcard_char = it_util.variant_to_value(
                self._gsettings.get_value('singlewildcardchar'))
        if len(self._single_wildcard_char) > 1:
            self._single_wildcard_char = self._single_wildcard_char[0]

        self._multi_wildcard_char = it_util.variant_to_value(
            self._gsettings.get_user_value('multiwildcardchar'))
        if self._multi_wildcard_char is None:
            self._multi_wildcard_char = self.database.ime_properties.get(
                'multi_wildcard_char')
        if self._multi_wildcard_char is None:
            self._multi_wildcard_char = it_util.variant_to_value(
                self._gsettings.get_value('multiwildcardchar'))
        if len(self._multi_wildcard_char) > 1:
            self._multi_wildcard_char = self._multi_wildcard_char[0]

        self._auto_wildcard = it_util.variant_to_value(
            self._gsettings.get_user_value('autowildcard'))
        if self._auto_wildcard is None:
            if self.database.ime_properties.get('auto_wildcard') is not None:
                self._auto_wildcard = self.database.ime_properties.get(
                    'auto_wildcard').lower() == u'true'
        if self._auto_wildcard is None:
            self._auto_wildcard = it_util.variant_to_value(
                self._gsettings.get_value('autowildcard'))

        self._max_key_length = int(
            self.database.ime_properties.get('max_key_length'))
        self._max_key_length_pinyin = 7

        # 0 = Direct input, i.e. table input OFF (aka “English input mode”),
        #     most characters are just passed through to the application
        #     (but some fullwidth ↔ halfwidth conversion may be done even
        #     in this mode, depending on the settings)
        # 1 = Table input ON (aka “Table input mode”, “Chinese mode”)
        self._input_mode = it_util.variant_to_value(
            self._gsettings.get_value('inputmode'))

        self._error_sound_object: Optional[simpleaudio.WaveObject] = None
        self._error_sound_file = ''
        self._error_sound = it_util.variant_to_value(
            self._gsettings.get_value('errorsound'))
        self.set_error_sound_file(
            it_util.variant_to_value(
                self._gsettings.get_value('errorsoundfile')),
            update_gsettings=False)

        # self._prev_key: hold the key event last time.
        self._prev_key: Optional[it_util.KeyEvent] = None
        self._prev_char: Optional[str] = None
        self._double_quotation_state = False
        self._single_quotation_state = False
        # self._prefix: the previous commit character or phrase
        self._prefix = u''
        self._py_mode = False
        # suggestion mode
        self._sg_mode = False
        self._sg_mode_active = False

        self._full_width_letter: List[Optional[bool]] = [None, None]
        self._full_width_letter = [
            it_util.variant_to_value(
                self._gsettings.get_value('endeffullwidthletter')),
            it_util.variant_to_value(
                self._gsettings.get_user_value('tabdeffullwidthletter'))
            ]
        if self._full_width_letter[1] is None:
            if self.database.ime_properties.get('def_full_width_letter'):
                self._full_width_letter[1] = self.database.ime_properties.get(
                    'def_full_width_letter').lower() == u'true'
        if self._full_width_letter[1] is None:
            self._full_width_letter[1] = it_util.variant_to_value(
                self._gsettings.get_value('tabdeffullwidthletter'))

        self._full_width_punct: List[Optional[bool]] = [None, None]
        self._full_width_punct = [
            it_util.variant_to_value(
                self._gsettings.get_value('endeffullwidthpunct')),
            it_util.variant_to_value(
                self._gsettings.get_user_value('tabdeffullwidthpunct'))
            ]
        if self._full_width_punct[1] is None:
            if self.database.ime_properties.get('def_full_width_punct'):
                self._full_width_punct[1] = self.database.ime_properties.get(
                    'def_full_width_punct').lower() == u'true'
        if self._full_width_punct[1] is None:
            self._full_width_punct[1] = it_util.variant_to_value(
                self._gsettings.get_value('tabdeffullwidthpunct'))

        self._auto_commit = it_util.variant_to_value(
            self._gsettings.get_user_value('autocommit'))
        if self._auto_commit is None:
            if self.database.ime_properties.get('auto_commit'):
                self._auto_commit = self.database.ime_properties.get(
                    'auto_commit').lower() == u'true'
        if self._auto_commit is None:
            self._auto_commit = it_util.variant_to_value(
                self._gsettings.get_value('autocommit'))

        # If auto select is true, then the first candidate phrase will
        # be selected automatically during typing. Auto select is true
        # by default for the stroke5 table for example.
        self._auto_select = it_util.variant_to_value(
            self._gsettings.get_user_value('autoselect'))
        if self._auto_select is None:
            if self.database.ime_properties.get('auto_select') is not None:
                self._auto_select = self.database.ime_properties.get(
                    'auto_select').lower() == u'true'
        if self._auto_select is None:
            self._auto_select = it_util.variant_to_value(
                self._gsettings.get_value('autoselect'))

        self._always_show_lookup = it_util.variant_to_value(
            self._gsettings.get_user_value('alwaysshowlookup'))
        if self._always_show_lookup is None:
            if (self.database.ime_properties.get('always_show_lookup')
                is not None):
                self._always_show_lookup = self.database.ime_properties.get(
                    'always_show_lookup').lower() == u'true'
        if self._always_show_lookup is None:
            self._always_show_lookup = it_util.variant_to_value(
                self._gsettings.get_value('alwaysshowlookup'))

        # The values below will be reset in
        # self.clear_input_not_committed_to_preedit()
        self._chars_valid = u''    # valid user input in table mode
        self._chars_invalid = u''  # invalid user input in table mode
        self._chars_valid_update_candidates_last = u''
        self._chars_invalid_update_candidates_last = u''
        # self._candidates holds the “best” candidates matching the user input
        # [(tabkeys, phrase, freq, user_freq), ...]
        self._candidates: List[Tuple[str, str, int, int]] = []
        self._candidates_previous: List[Tuple[str, str, int, int]] = []

        # self._u_chars: holds the user input of the phrases which
        # have been automatically committed to preedit (but not yet
        # “really” committed).
        self._u_chars: List[str] = []
        # self._strings: holds the phrases which have been
        # automatically committed to preedit (but not yet “really”
        # committed).
        #
        # self._u_chars and self._strings should always have the same
        # length, if I understand it correctly.
        #
        # Example when using the wubi-jidian86 table:
        #
        # self._u_chars = ['gaaa', 'gggg', 'ihty']
        # self._strings = ['形式', '王', '小']
        #
        # I.e. after typing 'gaaa', '形式' is in the preedit and
        # both self._u_chars and self._strings are empty. When typing
        # another 'g', the maximum key length of the wubi table (which is 4)
        # is exceeded and '形式' is automatically committed to the preedit
        # (but not yet “really” committed, i.e. not yet committed into
        # the application). The key 'gaaa' and the matching phrase '形式'
        # are stored in self._u_chars and self._strings respectively
        # and 'gaaa' is removed from self._chars_valid. Now self._chars_valid
        # contains only the 'g' which starts a new search for candidates ...
        # When removing the 'g' with backspace, the 'gaaa' is moved
        # back from self._u_chars into self._chars_valid again and
        # the same candidate list is shown as before the last 'g' had
        # been entered.
        self._strings: List[str] = []
        # self._cursor_precommit: The cursor
        # position in the array of strings which have already been
        # committed to preëdit but not yet “really” committed.
        self._cursor_precommit = 0

        self._prompt_characters = eval(
            self.database.ime_properties.get('char_prompts'))

        # self._onechar: whether we only select single character
        self._onechar = it_util.variant_to_value(self._gsettings.get_value(
            'onechar'))
        # self._chinese_mode: the candidate filter mode,
        #   0 means to show simplified Chinese only
        #   1 means to show traditional Chinese only
        #   2 means to show all characters but show simplified Chinese first
        #   3 means to show all characters but show traditional Chinese first
        #   4 means to show all characters
        # we use LC_CTYPE or LANG to determine which one to use if
        # no default comes from the user GSettings.
        self._chinese_mode = it_util.variant_to_value(
            self._gsettings.get_user_value('chinesemode'))
        if self._chinese_mode is not None and DEBUG_LEVEL > 1:
            LOGGER.debug(
                'Chinese mode found in Gsettings, mode=%s',
                self._chinese_mode)
        if self._chinese_mode is None:
            self._chinese_mode = it_util.get_default_chinese_mode(
                self.database)

        # If auto select is true, then the first candidate phrase will
        # be selected automatically during typing. Auto select is true
        # by default for the stroke5 table for example.
        self._auto_select = it_util.variant_to_value(
            self._gsettings.get_user_value('autoselect'))
        if self._auto_select is None:
            if self.database.ime_properties.get('auto_select') is not None:
                self._auto_select = self.database.ime_properties.get(
                    'auto_select').lower() == u'true'
        if self._auto_select is None:
            self._auto_select = it_util.variant_to_value(
                self._gsettings.get_value('autoselect'))

        self._default_keybindings = it_util.get_default_keybindings(
            self._gsettings, self.database)

        self._page_size = it_util.variant_to_value(
            self._gsettings.get_default_value('lookuptablepagesize'))
        for index in range(1, 10):
            if not self._default_keybindings[
                    'commit_candidate_%s' % (index + 1)]:
                self._page_size = min(index, self._page_size)
                break
        user_page_size = it_util.variant_to_value(
            self._gsettings.get_user_value('lookuptablepagesize'))
        if not user_page_size is None:
            self._page_size = user_page_size

        self._orientation = it_util.variant_to_value(
            self._gsettings.get_user_value('lookuptableorientation'))
        if self._orientation is None:
            self._orientation = self.database.get_orientation()

        user_keybindings = it_util.variant_to_value(
            self._gsettings.get_user_value('keybindings'))
        if not user_keybindings:
            user_keybindings = {}
        self.set_keybindings(user_keybindings, update_gsettings=False)

        use_dark_theme = it_util.variant_to_value(
            self._gsettings.get_user_value('darktheme'))
        if use_dark_theme:
            self.set_dark_theme(True, update_gsettings=False)

        self._lookup_table = self.get_new_lookup_table()

        self.chinese_mode_properties = {
            'ChineseMode.Simplified': {
                'number': 0,
                'symbol': '簡',
                'icon': 'sc-mode.svg',
                # Translators: This is the menu entry to select
                # when one wants to input only Simplified Chinese.
                'label': _('Simplified Chinese'),
                'tooltip':
                _('Switch to “Simplified Chinese only”.')},
            'ChineseMode.Traditional': {
                'number': 1,
                'symbol': '繁',
                'icon': 'tc-mode.svg',
                # Translators: This is the menu entry to select
                # when one wants to input only Traditonal Chinese
                'label': _('Traditional Chinese'),
                'tooltip':
                _('Switch to “Traditional Chinese only”.')},
            'ChineseMode.SimplifiedFirst': {
                'number': 2,
                'symbol': '簡/大',
                'icon': 'scb-mode.svg',
                # Translators: This is the menu entry to select when
                # one wants to input both Simplified and Traditional
                # Chinese but wants the Simplified Chinese to be
                # preferred, i.e. shown higher up in the candidate
                # lists.
                'label': _('Simplified Chinese first'),
                'tooltip':
                _('Switch to “Simplified Chinese before traditional”.')},
            'ChineseMode.TraditionalFirst': {
                'number': 3,
                'symbol': '繁/大',
                'icon': 'tcb-mode.svg',
                # Translators: This is the menu entry to select when
                # one wants to input both Simplified and Traditional
                # Chinese but wants the Traditional Chinese to be
                # preferred, i.e. shown higher up in the candidate
                # lists.
                'label': _('Traditional Chinese first'),
                'tooltip':
                _('Switch to “Traditional Chinese before simplified”.')},
            'ChineseMode.All': {
                'number': 4,
                'symbol': '大',
                'icon': 'cb-mode.svg',
                # Translators: This is the menu entry to select when
                # one wants to input both Simplified and Traditional
                # Chinese and has no particular preference whether
                # simplified or traditional characters should be higher
                # up in the candidate lists.
                'label': _('All Chinese characters'),
                'tooltip': _('Switch to “All Chinese characters”.')}
        }
        self.chinese_mode_menu = {
            'key': 'ChineseMode',
            'label': _('Chinese mode'),
            'tooltip': _('Switch Chinese mode'),
            'shortcut_hint': repr(
                self._keybindings['switch_to_next_chinese_mode']),
            'sub_properties': self.chinese_mode_properties
        }
        if self.database._is_chinese:
            self.input_mode_properties = {
                'InputMode.Direct': {
                    'number': 0,
                    'symbol': '英',
                    'icon': 'english.svg',
                    'label': _('English'),
                    'tooltip': _('Switch to English input')},
                'InputMode.Table': {
                    'number': 1,
                    'symbol': '中',
                    'symbol_table': '中',
                    'symbol_pinyin': '拼音',
                    'icon': 'chinese.svg',
                    'label': _('Chinese'),
                    'tooltip': _('Switch to Chinese input')}
            }
        else:
            self.input_mode_properties = {
                'InputMode.Direct': {
                    'number': 0,
                    'symbol': '☐' + self._symbol,
                    'icon': 'english.svg',
                    'label': _('Direct'),
                    'tooltip': _('Switch to direct input')},
                'InputMode.Table': {
                    'number': 1,
                    'symbol': '☑' + self._symbol,
                    'icon': 'ibus-table.svg',
                    'label': _('Table'),
                    'tooltip': _('Switch to table input')}
            }
        # The symbol of the property “InputMode” is displayed
        # in the input method indicator of the Gnome3 panel.
        # This depends on the property name “InputMode” and
        # is case sensitive!
        self.input_mode_menu = {
            'key': 'InputMode',
            'label': _('Input mode'),
            'tooltip': _('Switch Input mode'),
            'shortcut_hint': repr(
                self._keybindings['toggle_input_mode_on_off']),
            'sub_properties': self.input_mode_properties
        }
        self.letter_width_properties = {
            'LetterWidth.Half': {
                'number': 0,
                'symbol': '◑',
                'icon': 'half-letter.svg',
                'label': _('Half'),
                'tooltip': _('Switch to halfwidth letters')},
            'LetterWidth.Full': {
                'number': 1,
                'symbol': '●',
                'icon': 'full-letter.svg',
                'label': _('Full'),
                'tooltip': _('Switch to fullwidth letters')}
        }
        self.letter_width_menu = {
            'key': 'LetterWidth',
            'label': _('Letter width'),
            'tooltip': _('Switch letter width'),
            'shortcut_hint': repr(
                self._keybindings['toggle_letter_width']),
            'sub_properties': self.letter_width_properties
        }
        self.punctuation_width_properties = {
            'PunctuationWidth.Half': {
                'number': 0,
                'symbol': ',.',
                'icon': 'half-punct.svg',
                'label': _('Half'),
                'tooltip': _('Switch to halfwidth punctuation')},
            'PunctuationWidth.Full': {
                'number': 1,
                'symbol': '、。',
                'icon': 'full-punct.svg',
                'label': _('Full'),
                'tooltip': _('Switch to fullwidth punctuation')}
        }
        self.punctuation_width_menu = {
            'key': 'PunctuationWidth',
            'label': _('Punctuation width'),
            'tooltip': _('Switch punctuation width'),
            'shortcut_hint': repr(
                self._keybindings['toggle_punctuation_width']),
            'sub_properties': self.punctuation_width_properties
        }
        self.pinyin_mode_properties = {
            'PinyinMode.Table': {
                'number': 0,
                'symbol': '☐ 拼音',
                'icon': 'tab-mode.svg',
                'label': _('Table'),
                'tooltip': _('Switch to table mode')},
            'PinyinMode.Pinyin': {
                'number': 1,
                'symbol': '☑ 拼音',
                'icon': 'py-mode.svg',
                'label': _('Pinyin'),
                'tooltip': _('Switch to pinyin mode')}
        }
        self.pinyin_mode_menu = {
            'key': 'PinyinMode',
            'label': _('Pinyin mode'),
            'tooltip': _('Switch pinyin mode'),
            'shortcut_hint': repr(
                self._keybindings['toggle_pinyin_mode']),
            'sub_properties': self.pinyin_mode_properties
        }
        self.suggestion_mode_properties = {
            'SuggestionMode.Disabled': {
                'number': 0,
                'symbol': '☐ 联想',
                'icon': 'tab-mode.svg',
                'label': _('Suggestion disabled'),
                'tooltip': _('Switch to suggestion mode')},
            'SuggestionMode.Enabled': {
                'number': 1,
                'symbol': '☑ 联想',
                'icon': 'tab-mode.svg',
                'label': _('Suggestion enabled'),
                'tooltip': _('Switch to suggestion mode')}
        }
        self.suggestion_mode_menu = {
            'key': 'SuggestionMode',
            'label': _('Suggestion mode'),
            'tooltip': _('Switch suggestion mode'),
            'shortcut_hint': repr(
                self._keybindings['toggle_suggestion_mode']),
            'sub_properties': self.suggestion_mode_properties
        }
        self.onechar_mode_properties = {
            'OneCharMode.Phrase': {
                'number': 0,
                'symbol': '☐ 1',
                'icon': 'phrase.svg',
                'label': _('Multiple character match'),
                'tooltip':
                _('Switch to matching multiple characters at once')},
            'OneCharMode.OneChar': {
                'number': 1,
                'symbol': '☑ 1',
                'icon': 'onechar.svg',
                'label': _('Single character match'),
                'tooltip':
                _('Switch to matching only single characters')}
        }
        self.onechar_mode_menu = {
            'key': 'OneCharMode',
            'label': _('Onechar mode'),
            'tooltip': _('Switch onechar mode'),
            'shortcut_hint': repr(
                self._keybindings['toggle_onechar_mode']),
            'sub_properties': self.onechar_mode_properties
        }
        self.autocommit_mode_properties = {
            'AutoCommitMode.Direct': {
                'number': 0,
                'symbol': '☐ ↑',
                'icon': 'ncommit.svg',
                'label': _('Normal'),
                'tooltip':
                _('Switch to normal commit mode '
                  + '(automatic commits go into the preedit '
                  + 'instead of into the application. '
                  + 'This enables automatic definitions of new shortcuts)')},
            'AutoCommitMode.Normal': {
                'number': 1,
                'symbol': '☑ ↑',
                'icon': 'acommit.svg',
                'label': _('Direct'),
                'tooltip':
                _('Switch to direct commit mode '
                  + '(automatic commits go directly into the application)')}
        }
        self.autocommit_mode_menu = {
            'key': 'AutoCommitMode',
            'label': _('Auto commit mode'),
            'tooltip': _('Switch autocommit mode'),
            'shortcut_hint': repr(
                self._keybindings['toggle_autocommit_mode']),
            'sub_properties': self.autocommit_mode_properties
        }
        self._init_properties()

        self._on = False
        self._save_user_count = 0
        self._save_user_start = time.time()

        self._save_user_count_max = SAVE_USER_COUNT_MAX
        self._save_user_timeout = SAVE_USER_TIMEOUT
        self.reset()

        self.sync_timeout_id = GObject.timeout_add_seconds(
            1, self._sync_user_db)

        self.connect('process-key-event', self.__do_process_key_event)

        LOGGER.info(
            '********** Initialized and ready for input: **********')

    def get_new_lookup_table(self) -> IBus.LookupTable:
        '''
        Get a new lookup table
        '''
        lookup_table = IBus.LookupTable()
        lookup_table.clear()
        lookup_table.set_page_size(self._page_size)
        lookup_table.set_orientation(self._orientation)
        lookup_table.set_cursor_visible(True)
        lookup_table.set_round(True)
        for index in range(0, 10):
            label = ''
            if self._keybindings['commit_candidate_%s' % (index + 1)]:
                keybinding = self._keybindings[
                    'commit_candidate_%s' % (index + 1)][0]
                key = it_util.keybinding_to_keyevent(keybinding)
                label = keybinding
                if key.unicode and not key.name.startswith('KP_'):
                    label = key.unicode
            lookup_table.append_label(IBus.Text.new_from_string(label))
        return lookup_table

    def clear_all_input_and_preedit(self) -> None:
        '''
        Clear all input, whether committed to preëdit or not.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('clear_all_input_and_preedit()')
        self.clear_input_not_committed_to_preedit()
        self._u_chars = []
        self._strings = []
        self._cursor_precommit = 0
        self._prefix = u''
        self._sg_mode_active = False
        self.update_candidates()

    def is_empty(self) -> bool:
        '''Checks whether the preëdit is empty

        Returns True if the preëdit is empty, False if not.
        '''
        return self._chars_valid + self._chars_invalid == u''

    def clear_input_not_committed_to_preedit(self) -> None:
        '''
        Clear the input which has not yet been committed to preëdit.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('clear_input_not_committed_to_preedit()')
        self._chars_valid = u''
        self._chars_invalid = u''
        self._chars_valid_update_candidates_last = u''
        self._chars_invalid_update_candidates_last = u''
        self._lookup_table.clear()
        self._lookup_table.set_cursor_visible(True)
        self._candidates = []
        self._candidates_previous = []

    def add_input(self, char: str) -> bool:
        '''
        Add input character and update candidates.

        Returns “True” if candidates were found, “False” if not.
        '''
        if (self._chars_invalid
                or (not self._py_mode
                    and (char not in
                         self._valid_input_chars
                         + self._single_wildcard_char
                         + self._multi_wildcard_char))
                or (self._py_mode
                    and (char not in
                         self._pinyin_valid_input_chars
                         + self._single_wildcard_char
                         + self._multi_wildcard_char))):
            self._chars_invalid += char
        else:
            self._chars_valid += char
        res = self.update_candidates()
        return res

    def pop_input(self) -> str:
        '''remove and display last input char held'''
        last_input_char = ''
        if self._chars_invalid:
            last_input_char = self._chars_invalid[-1]
            self._chars_invalid = self._chars_invalid[:-1]
        elif self._chars_valid:
            last_input_char = self._chars_valid[-1]
            self._chars_valid = self._chars_valid[:-1]
            if (not self._chars_valid) and self._u_chars:
                self._chars_valid = self._u_chars.pop(
                    self._cursor_precommit - 1)
                self._strings.pop(self._cursor_precommit - 1)
                self._cursor_precommit -= 1
        self.update_candidates()
        return last_input_char

    def get_input_chars(self) -> str:
        '''get characters held, valid and invalid'''
        return self._chars_valid + self._chars_invalid

    def split_strings_committed_to_preedit(
            self, index: int, index_in_phrase: int) -> None:
        head = self._strings[index][:index_in_phrase]
        tail = self._strings[index][index_in_phrase:]
        self._u_chars.pop(index)
        self._strings.pop(index)
        self._u_chars.insert(index, self.database.parse_phrase(head))
        self._strings.insert(index, head)
        self._u_chars.insert(index+1, self.database.parse_phrase(tail))
        self._strings.insert(index+1, tail)

    def remove_preedit_before_cursor(self) -> None:
        '''Remove preëdit left of cursor'''
        if self._chars_invalid:
            return
        if self.get_input_chars():
            self.commit_to_preedit()
        if not self._strings:
            return
        if self._cursor_precommit <= 0:
            return
        self._u_chars = self._u_chars[self._cursor_precommit:]
        self._strings = self._strings[self._cursor_precommit:]
        self._cursor_precommit = 0

    def remove_preedit_after_cursor(self) -> None:
        '''Remove preëdit right of cursor'''
        if self._chars_invalid:
            return
        if self.get_input_chars():
            self.commit_to_preedit()
        if not self._strings:
            return
        if self._cursor_precommit >= len(self._strings):
            return
        self._u_chars = self._u_chars[:self._cursor_precommit]
        self._strings = self._strings[:self._cursor_precommit]
        self._cursor_precommit = len(self._strings)

    def remove_preedit_character_before_cursor(self) -> None:
        '''Remove character before cursor in strings comitted to preëdit'''
        if self._chars_invalid:
            return
        if self.get_input_chars():
            self.commit_to_preedit()
        if not self._strings:
            return
        if self._cursor_precommit < 1:
            return
        self._cursor_precommit -= 1
        self._chars_valid = self._u_chars.pop(self._cursor_precommit)
        self._strings.pop(self._cursor_precommit)
        self.update_candidates()

    def remove_preedit_character_after_cursor(self) -> None:
        '''Remove character after cursor in strings committed to preëdit'''
        if self._chars_invalid:
            return
        if self.get_input_chars():
            self.commit_to_preedit()
        if not self._strings:
            return
        if self._cursor_precommit > len(self._strings) - 1:
            return
        self._u_chars.pop(self._cursor_precommit)
        self._strings.pop(self._cursor_precommit)

    def get_preedit_tabkeys_parts(
            self) -> Tuple[Tuple[str, ...], str, Tuple[str, ...]]:
        '''Returns the tabkeys which were used to type the parts
        of the preëdit string.

        Such as “(left_of_current_edit, current_edit, right_of_current_edit)”

        “left_of_current_edit” and “right_of_current_edit” are
        strings of tabkeys which have been typed to get the phrases
        which have already been committed to preëdit, but not
        “really” committed yet. “current_edit” is the string of
        tabkeys of the part of the preëdit string which is not
        committed at all.

        For example, the return value could look like:

        (('gggg', 'aahw'), 'adwu', ('ijgl', 'jbus'))

        See also get_preedit_string_parts() which might return something
        like

        (('王', '工具'), '其', ('漫画', '最新'))

        when the wubi-jidian86 table is used.
        '''
        left_of_current_edit: Tuple[str, ...] = ()
        current_edit = u''
        right_of_current_edit: Tuple[str, ...] = ()
        if self.get_input_chars():
            current_edit = self.get_input_chars()
        if self._u_chars:
            left_of_current_edit = tuple(
                self._u_chars[:self._cursor_precommit])
            right_of_current_edit = tuple(
                self._u_chars[self._cursor_precommit:])
        return (left_of_current_edit, current_edit, right_of_current_edit)

    def get_preedit_tabkeys_complete(self) -> str:
        '''Returns the tabkeys which belong to the parts of the preëdit
        string as a single string
        '''
        (left_tabkeys,
         current_tabkeys,
         right_tabkeys) = self.get_preedit_tabkeys_parts()
        return  (u''.join(left_tabkeys)
                 + current_tabkeys
                 + u''.join(right_tabkeys))

    def get_preedit_string_parts(
            self) -> Tuple[Tuple[str, ...], str, Tuple[str, ...]]:
        '''Returns the phrases which are parts of the preëdit string.

        Such as “(left_of_current_edit, current_edit, right_of_current_edit)”

        “left_of_current_edit” and “right_of_current_edit” are
        tuples of strings which have already been committed to preëdit, but not
        “really” committed yet. “current_edit” is the phrase in the part of the
        preëdit string which is not yet committed at all.

        For example, the return value could look like:

        (('王', '工具'), '其', ('漫画', '最新'))

        See also get_preedit_tabkeys_parts() which might return something
        like

        (('gggg', 'aahw'), 'adwu', ('ijgl', 'jbus'))

        when the wubi-jidian86 table is used.
        '''
        left_of_current_edit: Tuple[str, ...] = ()
        current_edit = u''
        right_of_current_edit: Tuple[str, ...] = ()
        if self._candidates:
            current_edit = self._candidates[
                int(self._lookup_table.get_cursor_pos())][1]
        elif self.get_input_chars():
            current_edit = self.get_input_chars()
        if self._strings:
            left_of_current_edit = tuple(
                self._strings[:self._cursor_precommit])
            right_of_current_edit = tuple(
                self._strings[self._cursor_precommit:])
        return (left_of_current_edit, current_edit, right_of_current_edit)

    def get_preedit_string_complete(self) -> str:
        '''Returns the phrases which are parts of the preëdit string as a
        single string

        '''
        if self._sg_mode_active:
            if self._candidates:
                return self._candidates[
                    int(self._lookup_table.get_cursor_pos())][0]
            return u''

        (left_strings,
         current_string,
         right_strings) = self.get_preedit_string_parts()

        return (u''.join(left_strings)
                + current_string
                + u''.join(right_strings))

    def get_caret(self) -> int:
        '''Get caret position in preëdit string'''
        caret = 0
        if self._cursor_precommit and self._strings:
            for part in self._strings[:self._cursor_precommit]:
                caret += len(part)
        if self._candidates:
            caret += len(
                self._candidates[int(self._lookup_table.get_cursor_pos())][1])
        else:
            caret += len(self.get_input_chars())
        return caret

    def arrow_left(self) -> None:
        '''Move cursor left in the preëdit string.'''
        if self._chars_invalid:
            return
        if self.get_input_chars():
            self.commit_to_preedit()
        if not self._strings:
            return
        if self._cursor_precommit <= 0:
            return
        if len(self._strings[self._cursor_precommit-1]) <= 1:
            self._cursor_precommit -= 1
        else:
            self.split_strings_committed_to_preedit(
                self._cursor_precommit-1, -1)
        self.update_candidates()

    def arrow_right(self) -> None:
        '''Move cursor right in the preëdit string.'''
        if self._chars_invalid:
            return
        if self.get_input_chars():
            self.commit_to_preedit()
        if not self._strings:
            return
        if self._cursor_precommit >= len(self._strings):
            return
        self._cursor_precommit += 1
        if len(self._strings[self._cursor_precommit-1]) > 1:
            self.split_strings_committed_to_preedit(
                self._cursor_precommit-1, 1)
        self.update_candidates()

    def control_arrow_left(self) -> None:
        '''Move cursor to the beginning of the preëdit string.'''
        if self._chars_invalid:
            return
        if self.get_input_chars():
            self.commit_to_preedit()
        if not self._strings:
            return
        self._cursor_precommit = 0
        self.update_candidates()

    def control_arrow_right(self) -> None:
        '''Move cursor to the end of the preëdit string'''
        if self._chars_invalid:
            return
        if self.get_input_chars():
            self.commit_to_preedit()
        if not self._strings:
            return
        self._cursor_precommit = len(self._strings)
        self.update_candidates()

    def append_table_candidate(
            self, tabkeys=u'', phrase=u'', freq=0, user_freq=0) -> None:
        '''append table candidate to lookup table'''
        assert self._input_mode == 1
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'tabkeys=%s phrase=%s freq=%s user_freq=%s',
                tabkeys, phrase, freq, user_freq)
        if not tabkeys or not phrase:
            return

        mwild = self._multi_wildcard_char
        swild = self._single_wildcard_char
        if ((mwild and mwild in self._chars_valid)
                or (swild and swild in self._chars_valid)):
            # show all tabkeys if wildcard in tabkeys
            remaining_tabkeys = tabkeys
        else:
            regexp = self._chars_valid
            regexp = re.escape(regexp)
            match = re.match(r'^' + regexp, tabkeys)
            if match:
                remaining_tabkeys = tabkeys[match.end():]
            else:
                # This should never happen! For the candidates
                # added to the lookup table here, a match has
                # been found for self._chars_valid in the database.
                # In that case, the above regular expression should
                # match as well.
                remaining_tabkeys = tabkeys
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'remaining_tabkeys=%s '
                'self._chars_valid=%s phrase=%s',
                remaining_tabkeys, self._chars_valid, phrase)
        table_code = u''

        if not self._py_mode:
            remaining_tabkeys_new = u''
            for char in remaining_tabkeys:
                if char in self._prompt_characters:
                    remaining_tabkeys_new += self._prompt_characters[char]
                else:
                    remaining_tabkeys_new += char
            remaining_tabkeys = remaining_tabkeys_new
        candidate_text = phrase + u' ' + remaining_tabkeys

        if table_code:
            candidate_text = candidate_text + u'   ' + table_code
        attrs = IBus.AttrList()
        attrs.append(IBus.attr_foreground_new(
            self.theme["candidate_text"], 0, len(candidate_text)))
        if freq < 0:
            # this is a user defined phrase:
            attrs.append(
                IBus.attr_foreground_new(
                    self.theme["user_phrase"], 0, len(phrase)))
        elif user_freq > 0:
            # this is a system phrase which has already been used by the user:
            attrs.append(IBus.attr_foreground_new(
                self.theme["system_phrase"], 0, len(phrase)))
        else:
            # this is a system phrase that has not been used yet:
            attrs.append(IBus.attr_foreground_new(
                self.theme["system_phrase_unused"], 0, len(phrase)))

        if DEBUG_LEVEL > 0:
            debug_text = u' ' + str(freq) + u' ' + str(user_freq)
            candidate_text += debug_text
            attrs.append(IBus.attr_foreground_new(
                self.theme["debug_text"],
                len(candidate_text) - len(debug_text),
                len(candidate_text)))
        text = IBus.Text.new_from_string(candidate_text)
        i = 0
        while attrs.get(i) is not None:
            attr = attrs.get(i)
            text.append_attribute(attr.get_attr_type(),
                                  attr.get_value(),
                                  attr.get_start_index(),
                                  attr.get_end_index())
            i += 1
        self._lookup_table.append_candidate(text)
        self._lookup_table.set_cursor_visible(True)

    @staticmethod
    def select_longest_prefix_idx(asc_table_codes: List[str]) -> int:
        prefix_tree: List[List[()]] = []
        idx = -1
        count = 1

        '''
        (branch from, node index of branch from), (code, asc table codes index, same prefix count), ...
        for input
        ["w","wx","wxa","wxb","wxbc","wccd", "wxbd", "ilonga"]
        build a tree like this
        (-1, 0),('w', 0, 1),('wx', 1, 2),('wxa', 2, 3),
        (0, 2),('wxb', 3, 3),('wxbc', 4, 4),
        (0, 1),('wccd', 5, 2),
        (1, 1),('wxbd', 6, 4),
        (-1, 0),('ilonga', 7, 1),

        '''
        for code_idx in range(len(asc_table_codes)):
            branch_count = len(prefix_tree)
            code = asc_table_codes[code_idx]

            branch_idx = branch_count - 1
            node_idx = 0
            # traverse branches
            while branch_idx >= 0:
                prefix_branch = prefix_tree[branch_idx]
                branch_count = len(prefix_branch)
                node_idx = branch_count - 1
                # traverse nodes
                while node_idx > 0:
                    node = prefix_branch[node_idx]
                    if code.startswith(node[0]):
                        # make a leaf
                        if node_idx == branch_count - 1:
                            # extends branch
                            prefix_branch.append((code, code_idx, node[2] + 1))
                        else:
                            # in a new branch
                            new_branch = [(branch_idx, node_idx), (code, code_idx, node[2] + 1)]
                            prefix_tree.append(new_branch)

                        break
                    else:
                        # next node
                        node_idx -= 1

                if node_idx > 0:
                    break
                else:
                    # next branch
                    branch_idx -= 1

            if node_idx == 0:
                # new root branch
                new_branch = [(branch_idx, node_idx), (code, code_idx, 1)]
                prefix_tree.append(new_branch)

        # tree leaf holds the max same-prefix count code
        for branch in prefix_tree:
            node = branch[-1]
            if node[2] >= count:
                count = node[2]
                if node[1] > idx:
                    idx = node[1]

        return idx

    def append_pinyin_candidate(
            self, tabkeys=u'', phrase=u'', freq=0, user_freq=0) -> None:
        '''append pinyin candidate to lookup table'''
        assert self._input_mode == 1
        assert self._py_mode
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'tabkeys=%s phrase=%s freq=%s user_freq=%s',
                tabkeys, phrase, freq, user_freq)
        if not tabkeys or not phrase:
            return

        regexp = self._chars_valid
        regexp = re.escape(regexp)
        match = re.match(r'^'+regexp, tabkeys)
        if match:
            remaining_tabkeys = tabkeys[match.end():]
        else:
             # This should never happen! For the candidates
             # added to the lookup table here, a match has
             # been found for self._chars_valid in the database.
             # In that case, the above regular expression should
             # match as well.
            remaining_tabkeys = tabkeys
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'remaining_tabkeys=%s '
                'self._chars_valid=%s phrase=%s',
                remaining_tabkeys, self._chars_valid, phrase)

        table_code = u''

        if self.database._is_chinese and self._py_mode:
            # restore tune symbol
            remaining_tabkeys = remaining_tabkeys.replace(
                '!', '↑1').replace(
                    '@', '↑2').replace(
                        '#', '↑3').replace(
                            '$', '↑4').replace(
                                '%', '↑5')
            # If in pinyin mode, phrase can only be one character.
            # When using pinyin mode for a table like Wubi or Cangjie,
            # the reason is probably because one does not know the
            # Wubi or Cangjie code. So get that code from the table
            # and display it as well to help the user learn that code.
            # The Wubi tables contain several codes for the same
            # character, therefore self.database.find_zi_code(phrase) may
            # return a list. The last code in that list is the full
            # table code for that characters, other entries in that
            # list are shorter substrings of the full table code which
            # are not interesting to display. Therefore, we use only
            # the last element of the list of table codes.
            possible_table_codes = self.database.find_zi_code(phrase)
            if possible_table_codes:
                idx = self.select_longest_prefix_idx(possible_table_codes)
                table_code = possible_table_codes[idx]
            table_code_new = u''
            for char in table_code:
                if char in self._prompt_characters:
                    table_code_new += self._prompt_characters[char]
                else:
                    table_code_new += char
            table_code = table_code_new

        candidate_text = phrase + u' ' + remaining_tabkeys
        if table_code:
            candidate_text = candidate_text + u'   ' + table_code
        attrs = IBus.AttrList()
        attrs.append(IBus.attr_foreground_new(
            self.theme["candidate_text"], 0, len(candidate_text)))

        # this is a pinyin character:
        attrs.append(IBus.attr_foreground_new(
            self.theme["system_phrase"], 0, len(phrase)))

        if DEBUG_LEVEL > 0:
            debug_text = u' ' + str(freq) + u' ' + str(user_freq)
            candidate_text += debug_text
            attrs.append(IBus.attr_foreground_new(
                self.theme["debug_text"],
                len(candidate_text) - len(debug_text),
                len(candidate_text)))
        text = IBus.Text.new_from_string(candidate_text)
        i = 0
        while attrs.get(i) is not None:
            attr = attrs.get(i)
            text.append_attribute(attr.get_attr_type(),
                                  attr.get_value(),
                                  attr.get_start_index(),
                                  attr.get_end_index())
            i += 1
        self._lookup_table.append_candidate(text)
        self._lookup_table.set_cursor_visible(True)

    def append_suggestion_candidate(
            self, prefix=u'', phrase=u'', freq=0, user_freq=0) -> None:
        '''append suggestion candidate to lookup table'''
        assert self._input_mode == 1
        assert self._sg_mode
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'tabkeys=%s phrase=%s freq=%s user_freq=%s',
                prefix, phrase, freq, user_freq)
        if not prefix or not phrase:
            return

        if not phrase.startswith(prefix):
            return

        candidate_text = phrase

        attrs = IBus.AttrList()
        attrs.append(IBus.attr_foreground_new(
            self.theme["candidate_text"], 0, len(candidate_text)))

        # this is a suggestion candidate:
        attrs.append(IBus.attr_foreground_new(
            self.theme["system_phrase"], 0, len(phrase)))

        if DEBUG_LEVEL > 0:
            debug_text = u' ' + str(freq) + u' ' + str(user_freq)
            candidate_text += debug_text
            attrs.append(IBus.attr_foreground_new(
                self.theme["debug_text"],
                len(candidate_text) - len(debug_text),
                len(candidate_text)))
        text = IBus.Text.new_from_string(candidate_text)
        i = 0
        while attrs.get(i) is not None:
            attr = attrs.get(i)
            text.append_attribute(attr.get_attr_type(),
                                  attr.get_value(),
                                  attr.get_start_index(),
                                  attr.get_end_index())
            i += 1
        self._lookup_table.append_candidate(text)
        self._lookup_table.set_cursor_visible(True)

    def update_candidates(self, force=False) -> bool:
        '''
        Searches for candidates and updates the lookuptable.

        :param force: Force update candidates even if no change to input

        Returns “True” if candidates were found and “False” if not.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'self._chars_valid=%s '
                'self._chars_invalid=%s '
                'self._chars_valid_update_candidates_last=%s '
                'self._chars_invalid_update_candidates_last=%s '
                'self._candidates=%s '
                'self.database.startchars=%s '
                'self._strings=%s',
                self._chars_valid,
                self._chars_invalid,
                self._chars_valid_update_candidates_last,
                self._chars_invalid_update_candidates_last,
                self._candidates,
                self.database.startchars,
                self._strings)
        if (not force and not self._sg_mode_active
            and
            self._chars_valid == self._chars_valid_update_candidates_last
            and
            self._chars_invalid == self._chars_invalid_update_candidates_last):
            # The input did not change since we came here last, do
            # nothing and leave candidates and lookup table unchanged:
            return bool(self._candidates)
        self._chars_valid_update_candidates_last = self._chars_valid
        self._chars_invalid_update_candidates_last = self._chars_invalid
        self._lookup_table.clear()
        self._lookup_table.set_cursor_visible(True)
        if not self._sg_mode_active:
            if self._chars_invalid or not self._chars_valid:
                self._candidates = []
                self._candidates_previous = self._candidates
                return False
        if (not self._sg_mode_active
            and self._py_mode
            and self.database._is_chinese):
            self._candidates = (
                self.database.select_chinese_characters_by_pinyin(
                    tabkeys=self._chars_valid,
                    chinese_mode=self._chinese_mode,
                    single_wildcard_char=self._single_wildcard_char,
                    multi_wildcard_char=self._multi_wildcard_char))
        elif not self._sg_mode_active:
            self._candidates = self.database.select_words(
                tabkeys=self._chars_valid,
                onechar=self._onechar,
                chinese_mode=self._chinese_mode,
                single_wildcard_char=self._single_wildcard_char,
                multi_wildcard_char=self._multi_wildcard_char,
                auto_wildcard=self._auto_wildcard,
                dynamic_adjust=self._dynamic_adjust)
        elif self._sg_mode_active and self._sg_mode:
            self._candidates = self.database.select_suggestion_candidate(
                self._prefix)
        else:
            assert False
        # If only a wildcard character has been typed, insert a
        # special candidate at the first position for the wildcard
        # character itself. For example, if “?” is used as a
        # wildcard character and this is the only character typed, add
        # a candidate ('?', '?', 0, 1000000000) in halfwidth mode or a
        # candidate ('?', '？', 0, 1000000000) in fullwidth mode.
        # This is needed to make it possible to input the wildcard
        # characters themselves, if “?” acted only as a wildcard
        # it would be impossible to input a fullwidth question mark.
        if not self._sg_mode_active:
            if (self._chars_valid
                in [self._single_wildcard_char, self._multi_wildcard_char]):
                wildcard_key = self._chars_valid
                wildcard_phrase = self._chars_valid
                if ascii_ispunct(wildcard_key):
                    if self._full_width_punct[1]:
                        wildcard_phrase = unichar_half_to_full(wildcard_phrase)
                    else:
                        wildcard_phrase = unichar_full_to_half(wildcard_phrase)
                else:
                    if self._full_width_letter[1]:
                        wildcard_phrase = unichar_half_to_full(wildcard_phrase)
                    else:
                        wildcard_phrase = unichar_full_to_half(wildcard_phrase)
                self._candidates.insert(
                    0, (wildcard_key, wildcard_phrase, 0, 1000000000))
        if self._candidates:
            self.fill_lookup_table()
            self._candidates_previous = self._candidates
            return True
        # There are only valid and no invalid input characters but no
        # matching candidates could be found from the databases. The
        # last of self._chars_valid must have caused this.  That
        # character is valid in the sense that it is listed in
        # self._valid_input_chars, it is only invalid in the sense
        # that after adding this character, no candidates could be
        # found anymore.  Add this character to self._chars_invalid
        # and remove it from self._chars_valid.
        if self._chars_valid:
            self._chars_invalid += self._chars_valid[-1]
            self._chars_valid = self._chars_valid[:-1]
            self._chars_valid_update_candidates_last = self._chars_valid
            self._chars_invalid_update_candidates_last = self._chars_invalid
        return False

    def commit_to_preedit(self) -> bool:
        '''Add selected phrase in lookup table to preëdit string'''
        if not self._sg_mode_active:
            if not self._chars_valid:
                return False
        if self._candidates:
            if not self._sg_mode_active:
                phrase = self._candidates[self.get_cursor_pos()][1]
                self._u_chars.insert(
                    self._cursor_precommit,
                    self._candidates[self.get_cursor_pos()][0])
                self._strings.insert(
                    self._cursor_precommit, phrase)
                self._prefix = phrase
            elif self._sg_mode_active:
                phrase = self._candidates[self.get_cursor_pos()][0]
                phrase = phrase[len(self._prefix):]
                self._u_chars.insert(self._cursor_precommit,
                                     u'')
                self._strings.insert(self._cursor_precommit,
                                     phrase)
                self._prefix = u''
                self._sg_mode_active = False
            else:
                assert False
            self._cursor_precommit += 1
        self.clear_input_not_committed_to_preedit()
        self.update_candidates()
        return True

    def commit_to_preedit_current_page(self, index) -> bool:
        '''
        Commits the candidate at position “index” in the current
        page of the lookup table to the preëdit. Does not yet “really”
        commit the candidate, only to the preëdit.
        '''
        cursor_pos = self._lookup_table.get_cursor_pos()
        cursor_in_page = self._lookup_table.get_cursor_in_page()
        current_page_start = cursor_pos - cursor_in_page
        real_index = current_page_start + index
        if real_index >= len(self._candidates):
            # the index given is out of range we do not commit anything
            return False
        self._lookup_table.set_cursor_pos(real_index)
        return self.commit_to_preedit()

    def get_aux_strings(self) -> str:
        '''Get aux strings'''
        input_chars = self.get_input_chars()
        if input_chars:
            aux_string = input_chars
            if DEBUG_LEVEL > 0 and self._u_chars:
                (tabkeys_left,
                 dummy_tabkeys_current,
                 tabkeys_right) = self.get_preedit_tabkeys_parts()
                (strings_left,
                 dummy_string_current,
                 strings_right) = self.get_preedit_string_parts()
                aux_string = u''
                for i in range(0, len(strings_left)):
                    aux_string += (
                        u'('
                        + tabkeys_left[i] + u' '+ strings_left[i]
                        + u') ')
                aux_string += input_chars
                for i in range(0, len(strings_right)):
                    aux_string += (
                        u' ('
                        + tabkeys_right[i]+u' '+strings_right[i]
                        + u')')
            if self._py_mode:
                aux_string = aux_string.replace(
                    '!', '1').replace(
                        '@', '2').replace(
                            '#', '3').replace(
                                '$', '4').replace(
                                    '%', '5')
            else:
                aux_string_new = u''
                for char in aux_string:
                    if char in self._prompt_characters:
                        aux_string_new += self._prompt_characters[char]
                    else:
                        aux_string_new += char
                aux_string = aux_string_new
            return aux_string

        # There are no input strings at the moment. But there could
        # be stuff committed to the preëdit. If there is something
        # committed to the preëdit, show some information in the
        # auxiliary text.
        #
        # For the character at the position of the cursor in the
        # preëdit, show a list of possible input key sequences which
        # could be used to type that character at the left side of the
        # auxiliary text.
        #
        # If the preëdit is longer than one character, show the input
        # key sequence which will be defined for the complete current
        # contents of the preëdit, if the preëdit is committed.
        aux_string = u''
        if self._strings:
            if self._cursor_precommit >= len(self._strings):
                char = self._strings[-1][0]
            else:
                char = self._strings[self._cursor_precommit][0]
            aux_string = u' '.join(self.database.find_zi_code(char))
        cstr = u''.join(self._strings)
        if self.database.user_can_define_phrase:
            if len(cstr) > 1:
                aux_string += (u'\t#: ' + self.database.parse_phrase(cstr))
        aux_string_new = u''
        for char in aux_string:
            if char in self._prompt_characters:
                aux_string_new += self._prompt_characters[char]
            else:
                aux_string_new += char
        return aux_string_new

    def fill_lookup_table(self) -> None:
        '''Fill more entries to self._lookup_table if needed.

        If the cursor in _lookup_table moved beyond current length,
        add more entries from _candidiate[0] to _lookup_table.'''

        looklen = self._lookup_table.get_number_of_candidates()
        psize = self._lookup_table.get_page_size()
        if (self._lookup_table.get_cursor_pos() + psize >= looklen and
                looklen < len(self._candidates)):
            endpos = looklen + psize
            batch = self._candidates[looklen:endpos]
            for candidate in batch:
                if (self._input_mode
                    and not self._py_mode and not self._sg_mode_active):
                    self.append_table_candidate(
                        tabkeys=candidate[0],
                        phrase=candidate[1],
                        freq=candidate[2],
                        user_freq=candidate[3])
                elif (self._input_mode
                      and self._py_mode and not self._sg_mode_active):
                    self.append_pinyin_candidate(
                        tabkeys=candidate[0],
                        phrase=candidate[1],
                        freq=candidate[2],
                        user_freq=candidate[3])
                elif self._input_mode and self._sg_mode_active:
                    self.append_suggestion_candidate(
                        prefix=self._prefix,
                        phrase=candidate[0],
                        freq=candidate[1])
                else:
                    assert False

    def cursor_down(self) -> bool:
        '''Process Arrow Down Key Event
        Move Lookup Table cursor down'''
        self.fill_lookup_table()

        res = self._lookup_table.cursor_down()
        if not res and self._candidates:
            return True
        return res

    def cursor_up(self) -> bool:
        '''Process Arrow Up Key Event
        Move Lookup Table cursor up'''
        res = self._lookup_table.cursor_up()
        if not res and self._candidates:
            return True
        return res

    def page_down(self) -> bool:
        '''Process Page Down Key Event
        Move Lookup Table page down'''
        self.fill_lookup_table()
        res = self._lookup_table.page_down()
        if not res and self._candidates:
            return True
        return res

    def page_up(self) -> bool:
        '''Process Page Up Key Event
        move Lookup Table page up'''
        res = self._lookup_table.page_up()
        if not res and self._candidates:
            return True
        return res

    def remove_candidate_from_user_database(self, index: int) -> bool:
        '''Remove the candidate shown at index in the lookup table
        from the user database.

        If that candidate is not in the user database at all, nothing
        happens.

        If this is a candidate which is also in the system database,
        removing it from the user database only means that its user
        frequency data is reset. It might still appear in subsequent
        matches but with much lower priority.

        If this is a candidate which is user defined and not in the system
        database, it will not match at all anymore after removing it.

        :param index: The index in the current page of the lookup table.
                      The topmost candidate has the index 0 (and usually the
                      label “1”)
        :return: True if successful, False if not
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('index=%s', index)
        cursor_pos = self._lookup_table.get_cursor_pos()
        cursor_in_page = self._lookup_table.get_cursor_in_page()
        current_page_start = cursor_pos - cursor_in_page
        real_index = current_page_start + index
        if len(self._candidates) > real_index: # this index is valid
            candidate = self._candidates[real_index]
            self.database.remove_phrase(
                tabkeys=candidate[0], phrase=candidate[1], commit=True)
            # call update_candidates() to get a new SQL query.  The
            # input has not really changed, therefore we must clear
            # the remembered list of characters to
            # force update_candidates() to really do something and not
            # return immediately:
            self._chars_valid_update_candidates_last = u''
            self._chars_invalid_update_candidates_last = u''
            self.update_candidates()
            return True
        return False

    def get_cursor_pos(self) -> int:
        '''get lookup table cursor position'''
        return self._lookup_table.get_cursor_pos()

    def get_lookup_table(self) -> IBus.LookupTable:
        '''Get lookup table'''
        return self._lookup_table

    def remove_char(self) -> None:
        '''Process remove_char Key Event'''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('remove_char()')
        if self.get_input_chars():
            self.pop_input()
            return
        self.remove_preedit_character_before_cursor()

    def delete(self) -> None:
        '''Process delete Key Event'''
        if self.get_input_chars():
            return
        self.remove_preedit_character_after_cursor()

    def select_next_candidate_in_current_page(self) -> bool:
        '''Cycle cursor to next candidate in the page.'''
        total = len(self._candidates)

        if total > 0:
            page_size = self._lookup_table.get_page_size()
            pos = self._lookup_table.get_cursor_pos()
            page = int(pos/page_size)
            pos += 1
            if pos >= (page+1)*page_size or pos >= total:
                pos = page*page_size
            self._lookup_table.set_cursor_pos(pos)
            return True
        return False

    def select_previous_candidate_in_current_page(self) -> bool:
        '''Cycle cursor to previous candidate in the page.'''
        total = len(self._candidates)

        if total > 0:
            page_size = self._lookup_table.get_page_size()
            pos = self._lookup_table.get_cursor_pos()
            page = int(pos/page_size)
            pos -= 1
            if pos < page*page_size or pos < 0:
                pos = min(((page + 1) * page_size) - 1, total)
            self._lookup_table.set_cursor_pos(pos)
            return True
        return False

    def one_candidate(self) -> bool:
        '''Return true if there is only one candidate'''
        return len(self._candidates) == 1

    def reset(self) -> None:
        '''Clear the preëdit and close the lookup table
        '''
        self.clear_all_input_and_preedit()
        self._double_quotation_state = False
        self._single_quotation_state = False
        self._prev_key = None
        self._update_ui()

    def do_destroy(self) -> None:
        '''Called when this input engine is destroyed
        '''
        if self.sync_timeout_id > 0:
            GObject.source_remove(self.sync_timeout_id)
            self.sync_timeout_id = 0
        self.reset()
        self.do_focus_out()
        if self._save_user_count > 0:
            self.database.sync_usrdb()
            self._save_user_count = 0
        super().destroy()

    def set_debug_level(
            self, debug_level: int, update_gsettings: bool = True) -> None:
        '''Sets the debug level

        :param debug_level: The debug level (>= 0 and <= 255)
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        global DEBUG_LEVEL
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', debug_level, update_gsettings)
        if debug_level == self._debug_level:
            return
        if 0 <= debug_level <= 255:
            self._debug_level = debug_level
            DEBUG_LEVEL = debug_level
            self.reset()
            if update_gsettings:
                self._gsettings.set_value(
                    'debuglevel',
                    GLib.Variant.new_int32(debug_level))

    def get_debug_level(self) -> int:
        '''Returns the current debug level'''
        return self._debug_level

    def set_dynamic_adjust(
            self, dynamic_adjust: bool, update_gsettings: bool = True) -> None:
        '''Sets whether dynamic adjustment of the candidates is used.

        :param dynamic_adjust: True if dynamic adjustment is used, False if not
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)',
                dynamic_adjust, update_gsettings)
        if dynamic_adjust == self._dynamic_adjust:
            return
        self._dynamic_adjust = dynamic_adjust
        self.database.reset_phrases_cache()
        if update_gsettings:
            self._gsettings.set_value(
                'dynamicadjust',
                GLib.Variant.new_boolean(dynamic_adjust))

    def get_dynamic_adjust(self) -> bool:
        '''Returns whether dynamic adjustment of the candidates is used.'''
        return self._dynamic_adjust

    def set_error_sound(
            self, error_sound: bool, update_gsettings: bool = True) -> None:
        '''Sets whether a sound is played on error or not

        :param error_sound: True if a sound is played on error, False if not
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', error_sound, update_gsettings)
        if error_sound == self._error_sound:
            return
        self._error_sound = error_sound
        if update_gsettings:
            self._gsettings.set_value(
                'errorsound',
                GLib.Variant.new_boolean(error_sound))

    def get_error_sound(self) -> bool:
        '''Returns whether a sound is played on error or not'''
        return self._error_sound

    def set_error_sound_file(
            self, path: str = u'', update_gsettings: bool = True) -> None:
        '''Sets the path of the .wav file containing the sound
        to play on error.

        :param path: The path of the .wav file containing the error sound
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the dconf key changed
                                 to avoid endless loops when the dconf
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', path, update_gsettings)
        if path == self._error_sound_file:
            return
        self._error_sound_file = path
        if update_gsettings:
            self._gsettings.set_value(
                "errorsoundfile",
                GLib.Variant.new_string(path))
        path = os.path.expanduser(path)
        if not IMPORT_SIMPLEAUDIO_SUCCESSFUL:
            LOGGER.info(
                'No sound because python3-simpleaudio is not available.')
        else:
            if not os.path.isfile(path):
                LOGGER.info('Sound file %s does not exist.', path)
            elif not os.access(path, os.R_OK):
                LOGGER.info('Sound file %s not readable.', path)
            else:
                try:
                    LOGGER.info(
                        'Trying to initialize error sound from %s', path)
                    self._error_sound_object = (
                        simpleaudio.WaveObject.from_wave_file(path))
                    LOGGER.info('Error sound initialized.')
                except (FileNotFoundError, PermissionError):
                    LOGGER.exception(
                        'Initializing error sound object failed. '
                        'File not found or no read permissions.')
                except:
                    LOGGER.exception(
                        'Initializing error sound object failed '
                        'for unknown reasons.')

    def get_error_sound_file(self) -> str:
        '''
        Return the path of the .wav file containing the error sound.
        '''
        return self._error_sound_file

    def set_keybindings(self,
                        keybindings: Union[Dict[str, List[str]], Any],
                        update_gsettings: bool = True) -> None:
        '''Set current key bindings

        :param keybindings: The key bindings to use
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', keybindings, update_gsettings)
        if not isinstance(keybindings, dict):
            return
        keybindings = copy.deepcopy(keybindings)
        self._keybindings = copy.deepcopy(self._default_keybindings)
        # Update the default settings with the possibly changed settings:
        it_util.dict_update_existing_keys(self._keybindings, keybindings)
        # Update hotkeys:
        self._hotkeys = it_util.HotKeys(self._keybindings)
        # New keybindings might have changed the keys to commit candidates
        # from the lookup table and then the labels of the lookup table
        # might need to be updated:
        self._lookup_table = self.get_new_lookup_table()
        # Some property menus have tooltips which show hints for the
        # key bindings. These may need to be updated if the key
        # bindings have changed.
        #
        # I don’t check whether the key bindings really have changed,
        # just update all the properties anyway.
        #
        # But update them only if the properties have already been
        # initialized. At program start they might still be empty at
        # the time when self.set_keybindings() is called.
        if self._prop_dict:
            if self.chinese_mode_menu:
                self.chinese_mode_menu['shortcut_hint'] = (
                    repr(self._keybindings['switch_to_next_chinese_mode']))
            if self.input_mode_menu:
                self.input_mode_menu['shortcut_hint'] = (
                    repr(self._keybindings['toggle_input_mode_on_off']))
            if self.letter_width_menu:
                self.letter_width_menu['shortcut_hint'] = (
                    repr(self._keybindings['toggle_letter_width']))
            if self.punctuation_width_menu:
                self.punctuation_width_menu['shortcut_hint'] = (
                    repr(self._keybindings['toggle_punctuation_width']))
            if self.pinyin_mode_menu:
                self.pinyin_mode_menu['shortcut_hint'] = (
                    repr(self._keybindings['toggle_pinyin_mode']))
            if self.suggestion_mode_menu:
                self.suggestion_mode_menu['shortcut_hint'] = (
                    repr(self._keybindings['toggle_suggestion_mode']))
            if self.onechar_mode_menu:
                self.onechar_mode_menu['shortcut_hint'] = (
                    repr(self._keybindings['toggle_onechar_mode']))
            if self.autocommit_mode_menu:
                self.autocommit_mode_menu['shortcut_hint'] = (
                    repr(self._keybindings['toggle_autocommit_mode']))
            self._init_properties()
        if update_gsettings:
            variant_dict = GLib.VariantDict(GLib.Variant('a{sv}', {}))
            for command in sorted(self._keybindings):
                variant_array = GLib.Variant.new_array(
                    GLib.VariantType('s'),
                    [GLib.Variant.new_string(x)
                     for x in self._keybindings[command]])
                variant_dict.insert_value(command, variant_array)
            self._gsettings.set_value(
                'keybindings',
                variant_dict.end())

    def get_keybindings(self) -> Dict[str, List[str]]:
        '''Get current key bindings'''
        # It is important to return a copy, we do not want to change
        # the private member variable directly.
        return self._keybindings.copy()

    def set_input_mode(self, mode: int = 1):
        '''Sets whether direct input or the current table is used.

        :param mode: Whether to use direct input.
                     0: Use direct input.
                     1: Use the current table.
        '''
        if mode == self._input_mode:
            return
        self._input_mode = mode
        # Not saved to Gsettings on purpose. In the setup tool one
        # can select whether “Table input” or “Direct input” should
        # be the default when the input method starts. But when
        # changing this input mode using the property menu,
        # the change is not remembered.
        self._init_or_update_property_menu(
            self.input_mode_menu,
            self._input_mode)
        # Letter width and punctuation width depend on the input mode.
        # Therefore, the properties for letter width and punctuation
        # width need to be updated here:
        self._init_or_update_property_menu(
            self.letter_width_menu,
            self._full_width_letter[self._input_mode])
        self._init_or_update_property_menu(
            self.punctuation_width_menu,
            self._full_width_punct[self._input_mode])
        self.reset()

    def set_dark_theme(
            self, use_dark_theme: bool = False, update_gsettings: bool = True):
        '''Set theme to dark theme on request'''
        if use_dark_theme:
            theme = THEME_DARK
        else:
            theme = THEME
        if theme is not self.theme:
            self.theme = theme
            self._update_ui()

        if update_gsettings:
            self._gsettings.set_value(
                "darktheme",
                GLib.Variant.new_boolean(use_dark_theme))

    def get_input_mode(self) -> int:
        '''
        Return the current input mode, direct input: 0, table input: 1.
        '''
        return self._input_mode

    def set_pinyin_mode(self, mode: bool = False) -> None:
        '''Sets whether Pinyin is used.

        :param mode: Whether to use Pinyin.
                     True: Use Pinyin.
                     False: Use the current table.
        :type mode: Boolean
        '''
        if not self._ime_py:
            return
        if mode == self._py_mode:
            return
        # The pinyin mode is never saved to GSettings on purpose
        self._py_mode = mode
        self._init_or_update_property_menu(
            self.pinyin_mode_menu, mode)
        if mode:
            self.input_mode_properties['InputMode.Table']['symbol'] = (
                self.input_mode_properties['InputMode.Table']['symbol_pinyin'])
        else:
            self.input_mode_properties['InputMode.Table']['symbol'] = (
                self.input_mode_properties['InputMode.Table']['symbol_table'])
        self._init_or_update_property_menu(
            self.input_mode_menu,
            self._input_mode)
        self._update_ui()

    def get_pinyin_mode(self) -> bool:
        '''Return the current pinyin mode'''
        return self._py_mode

    def set_suggestion_mode(self, mode: bool = False) -> None:
        '''Sets whether Suggestion is used.

        :param mode: Whether to use Suggestion.
                     True: Use Suggestion.
                     False: Not use Suggestion.
        '''
        if not self._ime_sg:
            return
        if mode == self._sg_mode:
            return
        self.commit_to_preedit()
        self._sg_mode = mode
        self._init_or_update_property_menu(
            self.suggestion_mode_menu, mode)
        self._update_ui()

    def get_suggestion_mode(self) -> bool:
        '''Return the current suggestion mode'''
        return self._sg_mode

    def set_onechar_mode(
            self, mode: bool = False, update_gsettings: bool = True) -> None:
        '''Sets whether only single characters should be matched in
        the database.

        :param mode: Whether only single characters should be matched.
                     True: Match only single characters.
                     False: Possibly match multiple characters at once.
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the dconf key changed
                                 to avoid endless loops when the dconf
                                 key is changed twice in a short time.
        '''
        if mode == self._onechar:
            return
        self._onechar = mode
        self._init_or_update_property_menu(
            self.onechar_mode_menu, mode)
        self.database.reset_phrases_cache()
        if update_gsettings:
            self._gsettings.set_value(
                "onechar",
                GLib.Variant.new_boolean(mode))

    def get_onechar_mode(self) -> bool:
        '''
        Returns whether only single characters are matched in the database.
        '''
        return self._onechar

    def set_autocommit_mode(
            self, mode: bool = False, update_gsettings: bool = True) -> None:
        '''Sets whether automatic commits go into the preëdit or into the
        application.

        :param mode: Whether automatic commits  go into the  preëdit
                     or into the application.
                     True: Into the application.
                     False: Into the preëdit.
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the dconf key changed
                                 to avoid endless loops when the dconf
                                 key is changed twice in a short time.
        '''
        if mode == self._auto_commit:
            return
        self._auto_commit = mode
        self._init_or_update_property_menu(
            self.autocommit_mode_menu, mode)
        if update_gsettings:
            self._gsettings.set_value(
                "autocommit",
                GLib.Variant.new_boolean(mode))

    def get_autocommit_mode(self) -> bool:
        '''Returns the current auto-commit mode'''
        return self._auto_commit

    def set_autoselect_mode(
            self, mode: bool = False, update_gsettings: bool = True) -> None:
        '''Sets whether the first candidate will be selected
        automatically during typing.

        :param mode: Whether to select the first candidate automatically.
        :type mode: Boolean
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the dconf key changed
                                 to avoid endless loops when the dconf
                                 key is changed twice in a short time.
        :type update_gsettings: Boolean
        '''
        if mode == self._auto_select:
            return
        self._auto_select = mode
        if update_gsettings:
            self._gsettings.set_value(
                "autoselect",
                GLib.Variant.new_boolean(mode))

    def get_autoselect_mode(self) -> bool:
        '''Returns the current auto-select mode'''
        return self._auto_select

    def set_autowildcard_mode(
            self, mode: bool = False, update_gsettings: bool = True) -> None:
        '''Sets whether a wildcard should be automatically appended
        to the input.

        :param mode: Whether to append a wildcard automatically.
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the dconf key changed
                                 to avoid endless loops when the dconf
                                 key is changed twice in a short time.
        '''
        if mode == self._auto_wildcard:
            return
        self._auto_wildcard = mode
        self.database.reset_phrases_cache()
        if update_gsettings:
            self._gsettings.set_value(
                "autowildcard",
                GLib.Variant.new_boolean(mode))

    def get_autowildcard_mode(self) -> bool:
        '''Returns the  current automatic wildcard mode'''
        return self._auto_wildcard

    def set_single_wildcard_char(
            self, char: str = u'', update_gsettings: bool = True) -> None:
        '''Sets the single wildchard character.

        :param char: The character to use as a single wildcard
                     (String  of length 1).
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the dconf key changed
                                 to avoid endless loops when the dconf
                                 key is changed twice in a short time.
        '''
        if char == self._single_wildcard_char:
            return
        self._single_wildcard_char = char
        self.database.reset_phrases_cache()
        if update_gsettings:
            self._gsettings.set_value(
                "singlewildcardchar",
                GLib.Variant.new_string(char))

    def get_single_wildcard_char(self) -> str:
        '''
        Return the character currently used as a single wildcard.

        (String of length 1.)
        '''
        return self._single_wildcard_char

    def set_multi_wildcard_char(
            self, char: str = u'', update_gsettings: bool = True) -> None:
        '''Sets the multi wildchard character.

        :param char: The character to use as a multi wildcard.
                     (String  of length 1.)
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the dconf key changed
                                 to avoid endless loops when the dconf
                                 key is changed twice in a short time.
        '''
        if len(char) > 1:
            char = char[0]
        if char == self._multi_wildcard_char:
            return
        self._multi_wildcard_char = char
        self.database.reset_phrases_cache()
        if update_gsettings:
            self._gsettings.set_value(
                "multiwildcardchar",
                GLib.Variant.new_string(char))

    def get_multi_wildcard_char(self) -> str:
        '''
        Return the character currently used as a multi wildcard.
        (String of length 1.)
        '''
        return self._multi_wildcard_char

    def set_always_show_lookup(
            self, mode: bool = False, update_gsettings: bool = True) -> None:
        '''Sets the whether the lookup table is shown.

        :param mode: Whether to show the lookup table.
                     True: Lookup table is shown
                     False: Lookup table is hidden
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the dconf key changed
                                 to avoid endless loops when the dconf
                                 key is changed twice in a short time.
        '''
        if mode == self._always_show_lookup:
            return
        self._always_show_lookup = mode
        if update_gsettings:
            self._gsettings.set_value(
                "alwaysshowlookup",
                GLib.Variant.new_boolean(mode))

    def get_always_show_lookup(self) -> bool:
        '''Returns whether the lookup table is shown or hidden'''
        return self._always_show_lookup

    def set_lookup_table_orientation(
            self, orientation: int, update_gsettings: bool = True) -> None:
        '''Sets the orientation of the lookup table

        :param orientation: The orientation of the lookup table
                            0 <= orientation <= 2
                            IBUS_ORIENTATION_HORIZONTAL = 0,
                            IBUS_ORIENTATION_VERTICAL   = 1,
                            IBUS_ORIENTATION_SYSTEM     = 2.
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the dconf key changed
                                 to avoid endless loops when the dconf
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('orientation(%s)', orientation)
        if orientation == self._orientation:
            return
        if 0 <= orientation <= 2:
            self._orientation = orientation
            self._lookup_table.set_orientation(orientation)
            if update_gsettings:
                self._gsettings.set_value(
                    'lookuptableorientation',
                    GLib.Variant.new_int32(orientation))

    def get_lookup_table_orientation(self) -> int:
        '''Returns the current orientation of the lookup table'''
        return self._orientation

    def set_page_size(
            self, page_size: int, update_gsettings: bool = True) -> None:
        '''Sets the page size of the lookup table

        :param page_size: The page size of the lookup table
                          1 <= page size <= number of select keys
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the dconf key changed
                                 to avoid endless loops when the dconf
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('page_size=%s', page_size)
        if page_size == self._page_size:
            return
        for index in range(1, 10):
            if not self._default_keybindings[
                    'commit_candidate_%s' % (index + 1)]:
                page_size = min(index, page_size)
                break
        if page_size < 1:
            page_size = 1
        self._page_size = page_size
        # get a new lookup table to adapt to the new page size:
        self._lookup_table = self.get_new_lookup_table()
        self.reset()
        if update_gsettings:
            self._gsettings.set_value(
                'lookuptablepagesize',
                GLib.Variant.new_int32(page_size))

    def get_page_size(self) -> int:
        '''Returns the current page size of the lookup table'''
        return self._page_size

    def set_letter_width(
            self,
            mode: bool = False,
            input_mode: int = 0,
            update_gsettings: bool = True) -> None:
        '''
        Sets whether full width letters should be used.

        :param mode: Whether to use full width letters
        :param input_mode: The input mode (direct input: 0, table: 1)
                           for which to set the full width letter mode.
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if mode == self._full_width_letter[input_mode]:
            return
        self._full_width_letter[input_mode] = mode
        if input_mode == self._input_mode:
            self._init_or_update_property_menu(
                self.letter_width_menu, mode)
        if update_gsettings:
            if input_mode:
                self._gsettings.set_value(
                    "tabdeffullwidthletter",
                    GLib.Variant.new_boolean(mode))
            else:
                self._gsettings.set_value(
                    "endeffullwidthletter",
                    GLib.Variant.new_boolean(mode))

    def get_letter_width(self) -> List[Optional[bool]]:
        '''Return the current full width letter modes: [Boolean, Boolean]'''
        return self._full_width_letter

    def set_punctuation_width(
            self,
            mode: bool = False,
            input_mode: int = 0,
            update_gsettings: bool = True) -> None:
        '''
        Sets whether full width punctuation should be used.

        :param mode: Whether to use full width punctuation
        :param input_mode: The input mode (direct input: 0, table: 1)
                           for which to set the full width punctuation mode.
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if mode == self._full_width_punct[input_mode]:
            return
        self._full_width_punct[input_mode] = mode
        if input_mode == self._input_mode:
            self._init_or_update_property_menu(
                self.punctuation_width_menu, mode)
        if update_gsettings:
            if input_mode:
                self._gsettings.set_value(
                    "tabdeffullwidthpunct",
                    GLib.Variant.new_boolean(mode))
            else:
                self._gsettings.set_value(
                    "endeffullwidthpunct",
                    GLib.Variant.new_boolean(mode))

    def get_punctuation_width(self) -> List[Optional[bool]]:
        '''Return the current full width punctuation modes: [Boolean, Boolean]
        '''
        return self._full_width_punct

    def set_chinese_mode(
            self, mode: int = 0, update_gsettings: bool = True) -> None:
        '''Sets the candidate filter mode used for Chinese

        0 means to show simplified Chinese only
        1 means to show traditional Chinese only
        2 means to show all characters but show simplified Chinese first
        3 means to show all characters but show traditional Chinese first
        4 means to show all characters

        :param mode: The Chinese filter mode, 0 <= mode <= 4
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the dconf key changed
                                 to avoid endless loops when the dconf
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('mode=%s', mode)
        if mode == self._chinese_mode:
            return
        self._chinese_mode = mode
        self.database.reset_phrases_cache()
        self._init_or_update_property_menu(
            self.chinese_mode_menu, mode)
        if update_gsettings:
            self._gsettings.set_value(
                "chinesemode",
                GLib.Variant.new_int32(mode))

    def get_chinese_mode(self) -> int:
        '''
        Return the current Chinese mode.

        0 means to show simplified Chinese only
        1 means to show traditional Chinese only
        2 means to show all characters but show simplified Chinese first
        3 means to show all characters but show traditional Chinese first
        4 means to show all characters
        '''
        return self._chinese_mode

    def _init_or_update_property_menu(
            self,
            menu: Dict[str, Any],
            current_mode: Union[int, bool, None] = 0) -> None:
        '''
        Initialize or update a ibus property menu
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'menu=%s current_mode=%s', repr(menu), current_mode)
        if not current_mode:
            current_mode = 0
        menu_key = menu['key']
        sub_properties_dict = menu['sub_properties']
        for prop in sub_properties_dict:
            if sub_properties_dict[prop]['number'] == int(current_mode):
                symbol = sub_properties_dict[prop]['symbol']
                icon = sub_properties_dict[prop]['icon']
                label = '%(label)s (%(symbol)s) %(shortcut_hint)s' % {
                    'label': menu['label'],
                    'symbol': symbol,
                    'shortcut_hint': menu['shortcut_hint']}
                tooltip = '%(tooltip)s\n%(shortcut_hint)s' % {
                    'tooltip': menu['tooltip'],
                    'shortcut_hint': menu['shortcut_hint']}
        visible = True
        self._init_or_update_sub_properties(
            menu_key, sub_properties_dict, current_mode=current_mode)
        if not menu_key in self._prop_dict: # initialize property
            self._prop_dict[menu_key] = IBus.Property(
                key=menu_key,
                prop_type=IBus.PropType.MENU,
                label=IBus.Text.new_from_string(label),
                symbol=IBus.Text.new_from_string(symbol),
                icon=os.path.join(self._icon_dir, icon),
                tooltip=IBus.Text.new_from_string(tooltip),
                sensitive=visible,
                visible=visible,
                state=IBus.PropState.UNCHECKED,
                sub_props=self._sub_props_dict[menu_key])
            self.main_prop_list.append(self._prop_dict[menu_key])
        else: # update the property
            self._prop_dict[menu_key].set_label(
                IBus.Text.new_from_string(label))
            self._prop_dict[menu_key].set_symbol(
                IBus.Text.new_from_string(symbol))
            self._prop_dict[menu_key].set_icon(
                os.path.join(self._icon_dir, icon))
            self._prop_dict[menu_key].set_tooltip(
                IBus.Text.new_from_string(tooltip))
            self._prop_dict[menu_key].set_sensitive(visible)
            self._prop_dict[menu_key].set_visible(visible)
            self.update_property(self._prop_dict[menu_key]) # important!

    def _init_or_update_sub_properties(
            self,
            menu_key: str,
            modes: Dict[str, Any],
            current_mode: int = 0) -> None:
        '''
        Initialize or update the sub-properties of a property menu entry.
        '''
        if not menu_key in self._sub_props_dict:
            update = False
            self._sub_props_dict[menu_key] = IBus.PropList()
        else:
            update = True
        visible = True
        for mode in sorted(modes, key=lambda x: (modes[x]['number'])):
            if modes[mode]['number'] == int(current_mode):
                state = IBus.PropState.CHECKED
            else:
                state = IBus.PropState.UNCHECKED
            label = modes[mode]['label']
            if 'tooltip' in modes[mode]:
                tooltip = modes[mode]['tooltip']
            else:
                tooltip = ''
            if not update: # initialize property
                self._prop_dict[mode] = IBus.Property(
                    key=mode,
                    prop_type=IBus.PropType.RADIO,
                    label=IBus.Text.new_from_string(label),
                    icon=os.path.join(modes[mode]['icon']),
                    tooltip=IBus.Text.new_from_string(tooltip),
                    sensitive=visible,
                    visible=visible,
                    state=state,
                    sub_props=None)
                self._sub_props_dict[menu_key].append(
                    self._prop_dict[mode])
            else: # update property
                self._prop_dict[mode].set_label(
                    IBus.Text.new_from_string(label))
                self._prop_dict[mode].set_tooltip(
                    IBus.Text.new_from_string(tooltip))
                self._prop_dict[mode].set_sensitive(visible)
                self._prop_dict[mode].set_visible(visible)
                self._prop_dict[mode].set_state(state)
                self.update_property(self._prop_dict[mode]) # important!

    def _init_properties(self) -> None:
        '''
        Initialize the ibus property menus
        '''
        self._prop_dict = {}
        self._sub_props_dict = {}
        self.main_prop_list = IBus.PropList()

        self._init_or_update_property_menu(
            self.input_mode_menu,
            self._input_mode)

        if self.database._is_chinese and self._chinese_mode != -1:
            self._init_or_update_property_menu(
                self.chinese_mode_menu,
                self._chinese_mode)

        if self.database._is_cjk:
            self._init_or_update_property_menu(
                self.letter_width_menu,
                self._full_width_letter[self._input_mode])
            self._init_or_update_property_menu(
                self.punctuation_width_menu,
                self._full_width_punct[self._input_mode])

        if self._ime_py:
            self._init_or_update_property_menu(
                self.pinyin_mode_menu,
                self._py_mode)

        if self._ime_sg:
            self._init_or_update_property_menu(
                self.suggestion_mode_menu,
                self._sg_mode)

        if self.database._is_cjk:
            self._init_or_update_property_menu(
                self.onechar_mode_menu,
                self._onechar)

        if self.database.user_can_define_phrase and self.database.rules:
            self._init_or_update_property_menu(
                self.autocommit_mode_menu,
                self._auto_commit)

        self._setup_property = IBus.Property(
            key=u'setup',
            label=IBus.Text.new_from_string(_('Setup')),
            icon='gtk-preferences',
            tooltip=IBus.Text.new_from_string(
                _('Configure ibus-table “%(engine-name)s”')
                % {'engine-name': self._engine_name}),
            sensitive=True,
            visible=True)
        self.main_prop_list.append(self._setup_property)
        self.register_properties(self.main_prop_list)

    def do_property_activate(
            self,
            ibus_property: str,
            prop_state=IBus.PropState.UNCHECKED) -> None:
        '''
        Handle clicks on properties
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'ibus_property=%s prop_state=%s', ibus_property, prop_state)
        if ibus_property == "setup":
            self._start_setup()
            return
        if prop_state != IBus.PropState.CHECKED:
            # If the mouse just hovered over a menu button and
            # no sub-menu entry was clicked, there is nothing to do:
            return
        if ibus_property.startswith(self.input_mode_menu['key']+'.'):
            self.set_input_mode(
                self.input_mode_properties[ibus_property]['number'])
            return
        if (ibus_property.startswith(self.pinyin_mode_menu['key']+'.')
                and self._ime_py):
            self.set_pinyin_mode(
                bool(self.pinyin_mode_properties[ibus_property]['number']))
            return
        if (ibus_property.startswith(self.suggestion_mode_menu['key']+'.')
                and self._ime_sg):
            self.set_suggestion_mode(
                bool(self.suggestion_mode_properties[ibus_property]['number']))
            return
        if (ibus_property.startswith(self.onechar_mode_menu['key']+'.')
                and self.database._is_cjk):
            self.set_onechar_mode(
                bool(self.onechar_mode_properties[ibus_property]['number']))
            return
        if (ibus_property.startswith(self.autocommit_mode_menu['key']+'.')
                and self.database.user_can_define_phrase
                and self.database.rules):
            self.set_autocommit_mode(
                bool(self.autocommit_mode_properties[ibus_property]['number']))
            return
        if (ibus_property.startswith(self.letter_width_menu['key']+'.')
                and self.database._is_cjk):
            self.set_letter_width(
                bool(self.letter_width_properties[ibus_property]['number']),
                input_mode=self._input_mode)
            return
        if (ibus_property.startswith(self.punctuation_width_menu['key']+'.')
                and self.database._is_cjk):
            self.set_punctuation_width(
                bool(self.punctuation_width_properties[
                    ibus_property]['number']),
                input_mode=self._input_mode)
            return
        if (ibus_property.startswith(self.chinese_mode_menu['key']+'.')
                and self.database._is_chinese
                and self._chinese_mode != -1):
            self.set_chinese_mode(
                self.chinese_mode_properties[ibus_property]['number'])
            return

    def _start_setup(self) -> None:
        '''
        Start the setup tool if it is not running yet.
        '''
        if self._setup_pid != 0:
            pid, dummy_state = os.waitpid(self._setup_pid, os.P_NOWAIT)
            if pid != self._setup_pid:
                # If the last setup tool started from here is still
                # running the pid returned by the above os.waitpid()
                # is 0. In that case just return, don’t start a
                # second setup tool.
                return
            self._setup_pid = 0
        setup_cmd = os.path.join(
            str(os.getenv('IBUS_TABLE_LIB_LOCATION')),
            'ibus-setup-table')
        self._setup_pid = os.spawnl(
            os.P_NOWAIT,
            setup_cmd,
            'ibus-setup-table',
            '--engine-name table:%s' %self._engine_name)

    def _play_error_sound(self) -> None:
        '''Play an error sound if enabled and possible'''
        if self._error_sound and self._error_sound_object:
            try:
                dummy = self._error_sound_object.play()
            except:
                LOGGER.exception('Playing error sound failed.')

    def _update_preedit(self) -> None:
        '''Update Preedit String in UI'''

        if self._sg_mode_active:
            self.hide_preedit_text()
            return

        preedit_string_parts = self.get_preedit_string_parts()
        left_of_current_edit = u''.join(preedit_string_parts[0])
        current_edit = preedit_string_parts[1]
        right_of_current_edit = u''.join(preedit_string_parts[2])
        if self._input_mode and not self._sg_mode_active:
            current_edit_new = u''
            for char in current_edit:
                if char in self._prompt_characters:
                    current_edit_new += self._prompt_characters[char]
                else:
                    current_edit_new += char
            current_edit = current_edit_new
        preedit_string_complete = (
            left_of_current_edit + current_edit + right_of_current_edit)
        if not preedit_string_complete:
            super().update_preedit_text(
                IBus.Text.new_from_string(u''), 0, False)
            return
        color_left = self.theme["preedit_left"] # bright red
        color_right = self.theme["preedit_right"] # light green
        color_invalid = self.theme["preedit_invalid"] # magenta
        attrs = IBus.AttrList()
        attrs.append(
            IBus.attr_foreground_new(
                color_left,
                0,
                len(left_of_current_edit)))
        attrs.append(
            IBus.attr_foreground_new(
                color_right,
                len(left_of_current_edit) + len(current_edit),
                len(preedit_string_complete)))
        if self._chars_invalid:
            self._play_error_sound()
            attrs.append(
                IBus.attr_foreground_new(
                    color_invalid,
                    len(left_of_current_edit) + len(current_edit)
                    - len(self._chars_invalid),
                    len(left_of_current_edit) + len(current_edit)
                    ))
        attrs.append(
            IBus.attr_underline_new(
                IBus.AttrUnderline.SINGLE,
                0,
                len(preedit_string_complete)))
        text = IBus.Text.new_from_string(preedit_string_complete)
        i = 0
        while attrs.get(i) is not None:
            attr = attrs.get(i)
            text.append_attribute(attr.get_attr_type(),
                                  attr.get_value(),
                                  attr.get_start_index(),
                                  attr.get_end_index())
            i += 1
        super().update_preedit_text(
            text, self.get_caret(), True)

    def _update_aux(self) -> None:
        '''Update Aux String in UI'''
        if self._sg_mode_active:
            return

        aux_string = self.get_aux_strings()
        if self._candidates:
            aux_string += u' (%d / %d)' % (
                self._lookup_table.get_cursor_pos() +1,
                self._lookup_table.get_number_of_candidates())
        if aux_string:
            attrs = IBus.AttrList()
            attrs.append(IBus.attr_foreground_new(
                self.theme["aux_text"], 0, len(aux_string)))
            text = IBus.Text.new_from_string(aux_string)
            i = 0
            while attrs.get(i) is not None:
                attr = attrs.get(i)
                text.append_attribute(attr.get_attr_type(),
                                      attr.get_value(),
                                      attr.get_start_index(),
                                      attr.get_end_index())
                i += 1
            visible = True
            if not aux_string or not self._always_show_lookup:
                visible = False
            super().update_auxiliary_text(text, visible)
        else:
            self.hide_auxiliary_text()

    def _update_lookup_table(self) -> None:
        '''Update Lookup Table in UI'''
        if not self._candidates:
            # Also make sure to hide lookup table if there are
            # no candidates to display. On f17, this makes no
            # difference but gnome-shell in f18 will display
            # an empty suggestion popup if the number of candidates
            # is zero!
            self.hide_lookup_table()
            return

        if self._input_mode and not self._sg_mode_active:
            if self.is_empty():
                self.hide_lookup_table()
                return

        if not self._always_show_lookup:
            self.hide_lookup_table()
            return

        self.update_lookup_table(self.get_lookup_table(), True)

    def _update_ui(self) -> None:
        '''Update User Interface'''
        self._update_lookup_table()
        self._update_preedit()
        self._update_aux()

    def _check_phrase(self, tabkeys: str = u'', phrase: str = u'') -> None:
        """Check the given phrase and update save user db info"""
        if not tabkeys or not phrase:
            return
        self.database.check_phrase(
            tabkeys=tabkeys,
            phrase=phrase,
            dynamic_adjust=self._dynamic_adjust)

        if self._save_user_count <= 0:
            self._save_user_start = time.time()
        self._save_user_count += 1

    def _sync_user_db(self) -> bool:
        """Save user db to disk"""
        if self._save_user_count >= 0:
            now = time.time()
            time_delta = now - self._save_user_start
            if (self._save_user_count > self._save_user_count_max or
                    time_delta >= self._save_user_timeout):
                self.database.sync_usrdb()
                self._save_user_count = 0
                self._save_user_start = now
        return True

    def commit_string(self, phrase: str, tabkeys: str = u'') -> None:
        '''
        Commit the string “phrase”, update the user database,
        and clear the preëdit.

        :param phrase: The text to commit
        :param tabkeys: The keys typed to produce this text
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('phrase=%s', phrase)
        self.clear_all_input_and_preedit()
        self._update_ui()
        self._prefix = phrase

        super().commit_text(IBus.Text.new_from_string(phrase))
        if phrase:
            self._prev_char = phrase[-1]
        else:
            self._prev_char = None
        self._check_phrase(tabkeys=tabkeys, phrase=phrase)

    def commit_everything_unless_invalid(self) -> bool:
        '''
        Commits the current input to the preëdit and then
        commits the preëdit to the application unless there are
        invalid input characters.

        Returns “True” if something was committed, “False” if not.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('self._chars_invalid=%s',
                         self._chars_invalid)
        if self._chars_invalid:
            return False

        if self._input_mode and self._sg_mode_active:
            self.commit_to_preedit()

        if not self.is_empty():
            self.commit_to_preedit()

        self.commit_string(self.get_preedit_string_complete(),
                           tabkeys=self.get_preedit_tabkeys_complete())
        return True

    def _convert_to_full_width(self, char: str) -> str:
        '''Convert half width character to full width'''

        # This function handles punctuation that does not comply to the
        # Unicode conversion formula in unichar_half_to_full(char).
        # For ".", "\"", "'"; there are even variations under specific
        # cases. This function should be more abstracted by extracting
        # that to another handling function later on.
        special_punct_dict = {u"<": u"《", # 《 U+300A LEFT DOUBLE ANGLE BRACKET
                              u">": u"》", # 》 U+300B RIGHT DOUBLE ANGLE BRACKET
                              u"[": u"「", # 「 U+300C LEFT CORNER BRACKET
                              u"]": u"」", # 」U+300D RIGHT CORNER BRACKET
                              u"{": u"『", # 『 U+300E LEFT WHITE CORNER BRACKET
                              u"}": u"』", # 』U+300F RIGHT WHITE CORNER BRACKET
                              u"\\": u"、", # 、 U+3001 IDEOGRAPHIC COMMA
                              u"^": u"……", # … U+2026 HORIZONTAL ELLIPSIS
                              u"_": u"——", # — U+2014 EM DASH
                              u"$": u"￥" # ￥ U+FFE5 FULLWIDTH YEN SIGN
                             }

        # special puncts w/o further conditions
        if char in special_punct_dict.keys():
            if char in [u"\\", u"^", u"_", u"$"]:
                return special_punct_dict[char]
            if self._input_mode:
                return special_punct_dict[char]

        # special puncts w/ further conditions
        if char == u".":
            if (self._prev_char
                    and self._prev_char.isdigit()
                    and self._prev_key
                    and chr(self._prev_key.val) == self._prev_char):
                return u"."
            return u"。" # 。U+3002 IDEOGRAPHIC FULL STOP
        if char == u"\"":
            self._double_quotation_state = not self._double_quotation_state
            if self._double_quotation_state:
                return u"“" # “ U+201C LEFT DOUBLE QUOTATION MARK
            return u"”" # ” U+201D RIGHT DOUBLE QUOTATION MARK
        if char == u"'":
            self._single_quotation_state = not self._single_quotation_state
            if self._single_quotation_state:
                return u"‘" # ‘ U+2018 LEFT SINGLE QUOTATION MARK
            return u"’" # ’ U+2019 RIGHT SINGLE QUOTATION MARK

        return unichar_half_to_full(char)

    def do_candidate_clicked(self, index: int, _button, _state) -> bool:
        if self.commit_to_preedit_current_page(index):
            # commits to preëdit
            self.commit_string(
                self.get_preedit_string_complete(),
                tabkeys=self.get_preedit_tabkeys_complete())
            return True
        return False

    def _command_setup(self) -> bool:
        '''Handle hotkey for the command “setup”

        :return: True if the key was completely handled, False if not.
        '''
        self._start_setup()
        return True

    def _command_toggle_input_mode_on_off(self) -> bool:
        '''Handle hotkey for the command “toggle_input_mode_on_off”

        :return: True if the key was completely handled, False if not.
        '''
        if not self.is_empty():
            commit_string = self.get_preedit_tabkeys_complete()
            self.commit_string(commit_string)
        self.set_input_mode(int(not self._input_mode))
        return True

    def _command_toggle_letter_width(self) -> bool:
        '''Handle hotkey for the command “toggle_letter_width”

        :return: True if the key was completely handled, False if not.
        '''
        if not self.database._is_cjk:
            return False
        self.set_letter_width(
            not self._full_width_letter[self._input_mode],
            input_mode=self._input_mode)
        return True

    def _command_toggle_punctuation_width(self) -> bool:
        '''Handle hotkey for the command “toggle_punctuation_width”

        :return: True if the key was completely handled, False if not.
        '''
        if not self.database._is_cjk:
            return False
        self.set_punctuation_width(
            not self._full_width_punct[self._input_mode],
            input_mode=self._input_mode)
        return True

    def _command_cancel(self) -> bool:
        '''Handle hotkey for the command “cancel”

        :return: True if the key was completely handled, False if not.
        '''
        if self.is_empty():
            return False
        self.reset()
        self._update_ui()
        return True

    def _command_toggle_suggestion_mode(self) -> bool:
        '''Handle hotkey for the command “toggle_suggestion_mode”

        :return: True if the key was completely handled, False if not.
        '''
        if not self._ime_sg:
            return False
        self.set_suggestion_mode(not self._sg_mode)
        return True

    def _command_commit_to_preedit(self) -> bool:
        '''Handle hotkey for the command “commit_to_preedit”

        :return: True if the key was completely handled, False if not.
        '''
        if self.is_empty():
            return False
        res = self.commit_to_preedit()
        self._update_ui()
        return res

    def _command_toggle_pinyin_mode(self) -> bool:
        '''Handle hotkey for the command “toggle_pinyin_mode”

        :return: True if the key was completely handled, False if not.
        '''
        if not self._ime_py:
            return False
        self.set_pinyin_mode(not self._py_mode)
        if not self.is_empty():
            # Feed the current input in once again to get
            # the candidates and preedit to update correctly
            # for the new mode:
            chars = self._chars_valid + self._chars_invalid
            self._chars_valid = ''
            self._chars_invalid = ''
            for char in chars:
                self.add_input(char)
            self.update_candidates(force=True)
            self._update_ui()
        return True

    def _command_select_next_candidate_in_current_page(self) -> bool:
        '''Handle hotkey for the command
        “select_next_candidate_in_current_page”

        :return: True if the key was completely handled, False if not.
        '''
        res = self.select_next_candidate_in_current_page()
        self._update_ui()
        return res

    def _command_select_previous_candidate_in_current_page(self) -> bool:
        '''Handle hotkey for the command
        “select_previous_candidate_in_current_page”

        :return: True if the key was completely handled, False if not.
        '''
        res = self.select_previous_candidate_in_current_page()
        self._update_ui()
        return res

    def _command_toggle_onechar_mode(self) -> bool:
        '''Handle hotkey for the command “toggle_onechar_mode”

        :return: True if the key was completely handled, False if not.
        '''
        if not self.database._is_cjk:
            return False
        self.set_onechar_mode(not self._onechar)

        if not self.is_empty():
            self.update_candidates(True)
            self._update_ui()
        return True

    def _command_toggle_autocommit_mode(self) -> bool:
        '''Handle hotkey for the command “toggle_autocommit_mode”

        :return: True if the key was completely handled, False if not.
        '''
        if self.database.user_can_define_phrase and self.database.rules:
            self.set_autocommit_mode(not self._auto_commit)
            return True
        return False

    def _command_switch_to_next_chinese_mode(self) -> bool:
        '''Handle hotkey for the command “switch_to_next_chinese_mode”

        :return: True if the key was completely handled, False if not.
        '''
        if not self.database._is_chinese:
            return False
        self.set_chinese_mode((self._chinese_mode+1) % 5)

        if not self.is_empty():
            self.update_candidates(True)
            self._update_ui()
        return True

    def _command_commit(self) -> bool:
        '''Handle hotkey for the command “commit”

        :return: True if the key was completely handled, False if not.
        '''
        if (self._u_chars
            or not self.is_empty()
            or self._sg_mode_active):
            if self.commit_everything_unless_invalid():
                if self._auto_select:
                    self.commit_string(u' ')

            if (self._sg_mode
                and self._input_mode
                and not self._sg_mode_active):
                self._sg_mode_active = True

            self.update_candidates()
            self._update_ui()
            return True
        return False

    def _command_lookup_table_page_down(self) -> bool:
        '''Handle hotkey for the command “lookup_table_page_down”

        :return: True if the key was completely handled, False if not.
        '''
        if not self._candidates:
            return False
        res = self.page_down()
        self._update_ui()
        return res

    def _command_lookup_table_page_up(self) -> bool:
        '''Handle hotkey for the command “lookup_table_page_up”

        :return: True if the key was completely handled, False if not.
        '''
        if not self._candidates:
            return False
        res = self.page_up()
        self._update_ui()
        return res

    def _execute_commit_candidate_to_preedit_number(self, number: int) -> bool:
        '''Execute the hotkey command “commit_candidate_to_preedit_<number>”

        :return: True if the key was completely handled, False if not.
        :param number: The number of the candidate
        '''
        if not self._candidates:
            return False
        index = number - 1
        res = self.commit_to_preedit_current_page(index)
        self._update_ui()
        return res

    def _command_commit_candidate_to_preedit_1(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_to_preedit_1”

        :return: True if the key was completely handled, False if not.
        '''
        return self._execute_commit_candidate_to_preedit_number(1)

    def _command_commit_candidate_to_preedit_2(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_to_preedit_2”

        :return: True if the key was completely handled, False if not.
        '''
        return self._execute_commit_candidate_to_preedit_number(2)

    def _command_commit_candidate_to_preedit_3(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_to_preedit_3”

        :return: True if the key was completely handled, False if not.
        '''
        return self._execute_commit_candidate_to_preedit_number(3)

    def _command_commit_candidate_to_preedit_4(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_to_preedit_4”

        :return: True if the key was completely handled, False if not.
        '''
        return self._execute_commit_candidate_to_preedit_number(4)

    def _command_commit_candidate_to_preedit_5(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_to_preedit_5”

        :return: True if the key was completely handled, False if not.
        '''
        return self._execute_commit_candidate_to_preedit_number(5)

    def _command_commit_candidate_to_preedit_6(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_to_preedit_6”

        :return: True if the key was completely handled, False if not.
        '''
        return self._execute_commit_candidate_to_preedit_number(6)

    def _command_commit_candidate_to_preedit_7(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_to_preedit_7”

        :return: True if the key was completely handled, False if not.
        '''
        return self._execute_commit_candidate_to_preedit_number(7)

    def _command_commit_candidate_to_preedit_8(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_to_preedit_8”

        :return: True if the key was completely handled, False if not.
        '''
        return self._execute_commit_candidate_to_preedit_number(8)

    def _command_commit_candidate_to_preedit_9(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_to_preedit_9”

        :return: True if the key was completely handled, False if not.
        '''
        return self._execute_commit_candidate_to_preedit_number(9)

    def _command_commit_candidate_to_preedit_10(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_to_preedit_10”

        :return: True if the key was completely handled, False if not.
        '''
        return self._execute_commit_candidate_to_preedit_number(10)

    def _execute_remove_candidate_number(self, number: int) -> bool:
        '''Execute the hotkey command “remove_candidate_<number>”

        :return: True if the key was completely handled, False if not.
        :param number: The number of the candidate
        '''
        if not self._candidates:
            return False
        index = number - 1
        res = self.remove_candidate_from_user_database(index)
        self._update_ui()
        return res

    def _command_remove_candidate_1(self) -> bool:
        '''Handle hotkey for the command “remove_candidate_1”

        :return: True if the key was completely handled, False if not.
        '''
        return self._execute_remove_candidate_number(1)

    def _command_remove_candidate_2(self) -> bool:
        '''Handle hotkey for the command “remove_candidate_2”

        :return: True if the key was completely handled, False if not.
        '''
        return self._execute_remove_candidate_number(2)

    def _command_remove_candidate_3(self) -> bool:
        '''Handle hotkey for the command “remove_candidate_3”

        :return: True if the key was completely handled, False if not.
        '''
        return self._execute_remove_candidate_number(3)

    def _command_remove_candidate_4(self) -> bool:
        '''Handle hotkey for the command “remove_candidate_4”

        :return: True if the key was completely handled, False if not.
        '''
        return self._execute_remove_candidate_number(4)

    def _command_remove_candidate_5(self) -> bool:
        '''Handle hotkey for the command “remove_candidate_5”

        :return: True if the key was completely handled, False if not.
        '''
        return self._execute_remove_candidate_number(5)

    def _command_remove_candidate_6(self) -> bool:
        '''Handle hotkey for the command “remove_candidate_6”

        :return: True if the key was completely handled, False if not.
        '''
        return self._execute_remove_candidate_number(6)

    def _command_remove_candidate_7(self) -> bool:
        '''Handle hotkey for the command “remove_candidate_7”

        :return: True if the key was completely handled, False if not.
        '''
        return self._execute_remove_candidate_number(7)

    def _command_remove_candidate_8(self) -> bool:
        '''Handle hotkey for the command “remove_candidate_8”

        :return: True if the key was completely handled, False if not.
        '''
        return self._execute_remove_candidate_number(8)

    def _command_remove_candidate_9(self) -> bool:
        '''Handle hotkey for the command “remove_candidate_9”

        :return: True if the key was completely handled, False if not.
        '''
        return self._execute_remove_candidate_number(9)

    def _command_remove_candidate_10(self) -> bool:
        '''Handle hotkey for the command “remove_candidate_10”

        :return: True if the key was completely handled, False if not.
        '''
        return self._execute_remove_candidate_number(10)

    def _execute_command_commit_candidate_number(self, number: int) -> bool:
        '''Execute the hotkey command “commit_candidate_<number>”

        :return: True if the key was completely handled, False if not.
        :param number: The number of the candidate
        '''
        if not self._candidates or number > len(self._candidates):
            return False
        index = number - 1
        if not 0 <= index < self._page_size:
            return False
        if self.commit_to_preedit_current_page(index):
            self.commit_string(
                self.get_preedit_string_complete(),
                tabkeys=self.get_preedit_tabkeys_complete())

            if (self._sg_mode
                and self._input_mode
                and not self._sg_mode_active):
                self._sg_mode_active = True

            self.update_candidates()
            self._update_ui()
            return True
        return False

    def _command_commit_candidate_1(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_1”

        :return: True if the key was completely handled, False if not.
        '''
        return self._execute_command_commit_candidate_number(1)

    def _command_commit_candidate_2(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_2”

        :return: True if the key was completely handled, False if not.
        '''
        return self._execute_command_commit_candidate_number(2)

    def _command_commit_candidate_3(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_3”

        :return: True if the key was completely handled, False if not.
        '''
        return self._execute_command_commit_candidate_number(3)

    def _command_commit_candidate_4(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_4”

        :return: True if the key was completely handled, False if not.
        '''
        return self._execute_command_commit_candidate_number(4)

    def _command_commit_candidate_5(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_5”

        :return: True if the key was completely handled, False if not.
        '''
        return self._execute_command_commit_candidate_number(5)

    def _command_commit_candidate_6(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_6”

        :return: True if the key was completely handled, False if not.
        '''
        return self._execute_command_commit_candidate_number(6)

    def _command_commit_candidate_7(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_7”

        :return: True if the key was completely handled, False if not.
        '''
        return self._execute_command_commit_candidate_number(7)

    def _command_commit_candidate_8(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_8”

        :return: True if the key was completely handled, False if not.
        '''
        return self._execute_command_commit_candidate_number(8)

    def _command_commit_candidate_9(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_9”

        :return: True if the key was completely handled, False if not.
        '''
        return self._execute_command_commit_candidate_number(9)

    def _command_commit_candidate_10(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_10”

        :return: True if the key was completely handled, False if not.
        '''
        return self._execute_command_commit_candidate_number(10)

    def _handle_hotkeys(
            self,
            key: it_util.KeyEvent,
            commands: Iterable[str] = ()) -> bool:
        '''Handle hotkey commands

        :return: True if the key was completely handled, False if not.
        :param key: The typed key. If this is a hotkey,
                    execute the command for this hotkey.
        :param commands: A list of commands to check whether
                         the key matches the keybinding for one of
                         these commands.
                         If the list of commands is empty, check
                         *all* commands in the self._keybindings
                         dictionary.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('KeyEvent object: %s\n', key)
        if DEBUG_LEVEL > 5:
            LOGGER.debug('self._hotkeys=%s\n', str(self._hotkeys))

        if not commands:
            # If no specific command list to match is given, try to
            # match against all commands. Sorting shouldn’t really
            # matter, but maybe better do it sorted, then it is done
            # in the same order as the commands are displayed by
            # default in the setup tool.
            commands = sorted(self._keybindings.keys())
        for command in commands:
            if (self._prev_key, key, command) in self._hotkeys: # type: ignore
                if DEBUG_LEVEL > 1:
                    LOGGER.debug('matched command=%s', command)
                command_function_name = '_command_%s' % command
                try:
                    command_function = getattr(self, command_function_name)
                except (AttributeError,):
                    LOGGER.exception('There is no function %s',
                                     command_function_name)
                    return False
                if command_function():
                    return True
        return False

    def _return_false(self, keyval: int, keycode: int, state: int) -> bool:
        '''A replacement for “return False” in do_process_key_event()

        do_process_key_event should return “True” if a key event has
        been handled completely. It should return “False” if the key
        event should be passed to the application.

        But just doing “return False” doesn’t work well when trying to
        do the unit tests. The MockEngine class in the unit tests
        cannot get that return value. Therefore, it cannot do the
        necessary updates to the self._mock_committed_text etc. which
        prevents proper testing of the effects of such keys passed to
        the application. Instead of “return False”, one can also use
        self.forward_key_event(keyval, keycode, keystate) to pass the
        key to the application. And this works fine with the unit
        tests because a forward_key_event function is implemented in
        MockEngine as well which then gets the key and can test its
        effects.

        Unfortunately, “forward_key_event()” does not work in Qt5
        applications because the ibus module in Qt5 does not implement
        “forward_key_event()”. Therefore, always using
        “forward_key_event()” instead of “return False” in
        “do_process_key_event()” would break ibus-typing-booster
        completely for all Qt5 applictions.

        To work around this problem and make unit testing possible
        without breaking Qt5 applications, we use this helper function
        which uses “forward_key_event()” when unit testing and “return
        False” during normal usage.

        '''
        if self._unit_test:
            self.forward_key_event(keyval, keycode, state)
            return True
        return False

    def __do_process_key_event(
            self, _obj, keyval: int, keycode: int, state: int) -> bool:
        '''
        This function is connected to the 'process-key-event' signal.
        '''
        return self._do_process_key_event(keyval, keycode, state)

    def _do_process_key_event(
            self, keyval: int, keycode: int, state: int) -> bool:
        '''Process Key Events
        Key Events include Key Press and Key Release,
        modifier means Key Pressed
        '''
        key = it_util.KeyEvent(keyval, keycode, state)
        if DEBUG_LEVEL > 1:
            LOGGER.debug('KeyEvent object: %s', key)

        if (self._has_input_purpose
                and self._input_purpose
                in [IBus.InputPurpose.PASSWORD, IBus.InputPurpose.PIN]):
            return self._return_false(keyval, keycode, state)

        result = self._process_key_event(key)
        self._prev_key = key
        return result

    def _process_key_event(self, key: it_util.KeyEvent) -> bool:
        '''
        Internal method to process key event

        Returns True if the key event has been completely handled by
        ibus-table and should not be passed through anymore.
        Returns False if the key event has not been handled completely
        and is passed through.
        '''
        if self._handle_hotkeys(
                key, commands=['toggle_input_mode_on_off',
                               'toggle_letter_width',
                               'toggle_punctuation_width',
                               'setup']):
            return True
        if self._input_mode:
            if self._handle_hotkeys(key):
                return True
            return self._table_mode_process_key_event(key)
        return self._english_mode_process_key_event(key)

    def cond_letter_translate(self, char: str) -> str:
        '''Converts “char” to full width *if* full width letter mode is on for
        the current input mode (direct input or table mode) *and* if
        the current table is for CJK.

        :param char: The character to maybe convert to full width
        '''
        if self._full_width_letter[self._input_mode] and self.database._is_cjk:
            return self._convert_to_full_width(char)
        return char

    def cond_punct_translate(self, char: str) -> str:
        '''Converts “char” to full width *if* full width punctuation mode is
        on for the current input mode (direct input or table mode)
        *and* if the current table is for CJK.

        :param char: The character to maybe convert to full width
        '''
        if self._full_width_punct[self._input_mode] and self.database._is_cjk:
            return self._convert_to_full_width(char)
        return char

    def _english_mode_process_key_event(self, key: it_util.KeyEvent) -> bool:
        '''
        Process a key event in “English” (“Direct input”) mode.
        '''
        # Ignore key release events
        if key.state & IBus.ModifierType.RELEASE_MASK:
            return self._return_false(key.val, key.code, key.state)
        if key.val >= 128:
            return self._return_false(key.val, key.code, key.state)
        # we ignore all hotkeys here
        if (key.state
                & (IBus.ModifierType.CONTROL_MASK
                   |IBus.ModifierType.MOD1_MASK)):
            return self._return_false(key.val, key.code, key.state)
        keychar = IBus.keyval_to_unicode(key.val)
        if ascii_ispunct(keychar):
            trans_char = self.cond_punct_translate(keychar)
        else:
            trans_char = self.cond_letter_translate(keychar)
        if trans_char == keychar:
            return self._return_false(key.val, key.code, key.state)
        self.commit_string(trans_char)
        return True

    def _table_mode_process_key_event(self, key: it_util.KeyEvent) -> bool:
        '''
        Process a key event in “Table” mode, i.e. when the
        table is actually used and not switched off by using
        direct input.
        '''
        if DEBUG_LEVEL > 0:
            LOGGER.debug('repr(key)=%s', repr(key))

        # Ignore key release events (Should be below all hotkey matches
        # because some of them might match on a release event)
        if key.state & IBus.ModifierType.RELEASE_MASK:
            return self._return_false(key.val, key.code, key.state)

        keychar = IBus.keyval_to_unicode(key.val)

        # Section to handle leading invalid input:
        #
        # This is the first character typed, if it is invalid
        # input, handle it immediately here, if it is valid, continue.
        if (self.is_empty()
                and not self.get_preedit_string_complete()):
            if ((keychar not in (
                    self._valid_input_chars
                    + self._single_wildcard_char
                    + self._multi_wildcard_char)
                 or (self.database.startchars
                     and keychar not in self.database.startchars))
                    and (not key.state &
                         (IBus.ModifierType.MOD1_MASK |
                          IBus.ModifierType.CONTROL_MASK))):
                if DEBUG_LEVEL > 0:
                    LOGGER.debug(
                        'leading invalid input: '
                        'keychar=%s',
                        keychar)
                if ascii_ispunct(keychar):
                    trans_char = self.cond_punct_translate(keychar)
                else:
                    trans_char = self.cond_letter_translate(keychar)
                if trans_char == keychar:
                    self._prev_char = trans_char
                    return self._return_false(key.val, key.code, key.state)
                self.commit_string(trans_char)
                return True

        if key.val in (IBus.KEY_Return, IBus.KEY_KP_Enter):
            if (self.is_empty()
                    and not self.get_preedit_string_complete()):
                # When IBus.KEY_Return is typed,
                # IBus.keyval_to_unicode(key.val) returns a non-empty
                # string. But when IBus.KEY_KP_Enter is typed it
                # returns an empty string. Therefore, when typing
                # IBus.KEY_KP_Enter as leading input, the key is not
                # handled by the section to handle leading invalid
                # input but it ends up here.  If it is leading input
                # (i.e. the preëdit is empty) we should always pass
                # IBus.KEY_KP_Enter to the application:
                return self._return_false(key.val, key.code, key.state)
            if self._auto_select:
                self.commit_to_preedit()
                commit_string = self.get_preedit_string_complete()
                self.commit_string(commit_string)
                return self._return_false(key.val, key.code, key.state)
            commit_string = self.get_preedit_tabkeys_complete()
            self.commit_string(commit_string)
            return True

        if key.val in (IBus.KEY_Tab, IBus.KEY_KP_Tab) and self._auto_select:
            # Used for example for the Russian transliteration method
            # “translit”, which uses “auto select”. If for example
            # a file with the name “шшш” exists and one types in
            # a bash shell:
            #
            #     “ls sh”
            #
            # the “sh” is converted to “ш” and one sees
            #
            #     “ls ш”
            #
            # in the shell where the “ш” is still in preëdit
            # because “shh” would be converted to “щ”, i.e. there
            # is more than one candidate and the input method is still
            # waiting whether one more “h” will be typed or not. But
            # if the next character typed is a Tab, the preëdit is
            # committed here and “False” is returned to pass the Tab
            # character through to the bash to complete the file name
            # to “шшш”.
            self.commit_to_preedit()
            self.commit_string(self.get_preedit_string_complete())
            return self._return_false(key.val, key.code, key.state)

        if key.val in (IBus.KEY_Down, IBus.KEY_KP_Down):
            if not self.get_preedit_string_complete():
                return self._return_false(key.val, key.code, key.state)
            res = self.cursor_down()
            self._update_ui()
            return res

        if key.val in (IBus.KEY_Up, IBus.KEY_KP_Up):
            if not self.get_preedit_string_complete():
                return self._return_false(key.val, key.code, key.state)
            res = self.cursor_up()
            self._update_ui()
            return res

        if (key.val in (IBus.KEY_Left, IBus.KEY_KP_Left)
                and key.state & IBus.ModifierType.CONTROL_MASK):
            if not self.get_preedit_string_complete():
                return self._return_false(key.val, key.code, key.state)
            self.control_arrow_left()
            self._update_ui()
            return True

        if (key.val in (IBus.KEY_Right, IBus.KEY_KP_Right)
                and key.state & IBus.ModifierType.CONTROL_MASK):
            if not self.get_preedit_string_complete():
                return self._return_false(key.val, key.code, key.state)
            self.control_arrow_right()
            self._update_ui()
            return True

        if key.val in (IBus.KEY_Left, IBus.KEY_KP_Left):
            if not self.get_preedit_string_complete():
                return self._return_false(key.val, key.code, key.state)
            self.arrow_left()
            self._update_ui()
            return True

        if key.val in (IBus.KEY_Right, IBus.KEY_KP_Right):
            if not self.get_preedit_string_complete():
                return self._return_false(key.val, key.code, key.state)
            self.arrow_right()
            self._update_ui()
            return True

        if (key.val == IBus.KEY_BackSpace
                and key.state & IBus.ModifierType.CONTROL_MASK):
            if not self.get_preedit_string_complete():
                return self._return_false(key.val, key.code, key.state)
            self.remove_preedit_before_cursor()
            self._update_ui()
            return True

        if key.val == IBus.KEY_BackSpace:
            if not self.get_preedit_string_complete():
                return self._return_false(key.val, key.code, key.state)
            self.remove_char()
            self._update_ui()
            return True

        if (key.val == IBus.KEY_Delete
                and key.state & IBus.ModifierType.CONTROL_MASK):
            if not self.get_preedit_string_complete():
                return self._return_false(key.val, key.code, key.state)
            self.remove_preedit_after_cursor()
            self._update_ui()
            return True

        if key.val == IBus.KEY_Delete:
            if not self.get_preedit_string_complete():
                return self._return_false(key.val, key.code, key.state)
            self.delete()
            self._update_ui()
            return True

        # now we ignore all other hotkeys
        if (key.state
                & (IBus.ModifierType.CONTROL_MASK
                   |IBus.ModifierType.MOD1_MASK)):
            return self._return_false(key.val, key.code, key.state)

        if key.state & IBus.ModifierType.MOD1_MASK:
            return self._return_false(key.val, key.code, key.state)

        # Section to handle valid input characters:
        if (keychar
                and (keychar in (self._valid_input_chars
                                 + self._single_wildcard_char
                                 + self._multi_wildcard_char)
                     or (self._input_mode and self._py_mode
                         and keychar in self._pinyin_valid_input_chars))):
            if DEBUG_LEVEL > 0:
                LOGGER.debug(
                    'valid input: keychar=%s', keychar)

            # Deactivate suggestion mode:
            if self._input_mode and self._sg_mode_active:
                self.clear_all_input_and_preedit()
                self._sg_mode_active = False

            if self._input_mode and self._py_mode:
                if ((len(self._chars_valid)
                     == self._max_key_length_pinyin)
                        or (len(self._chars_valid) > 1
                            and self._chars_valid[-1] in '!@#$%')):
                    if self._auto_commit:
                        self.commit_everything_unless_invalid()
                    else:
                        self.commit_to_preedit()
            elif self._input_mode and not self._py_mode:
                if ((len(self._chars_valid)
                     == self._max_key_length)
                        or (len(self._chars_valid)
                            in self.database.possible_tabkeys_lengths)):
                    if self._auto_commit:
                        self.commit_everything_unless_invalid()
                    else:
                        self.commit_to_preedit()
            else:
                assert False
            res = self.add_input(keychar)
            if not res:
                if self._auto_select and self._candidates_previous:
                    # Used for example for the Russian transliteration method
                    # “translit”, which uses “auto select”.
                    # The “translit” table contains:
                    #
                    #     sh ш
                    #     shh щ
                    #
                    # so typing “sh” matches “ш” and “щ”. The
                    # candidate with the shortest key sequence comes
                    # first in the lookup table, therefore “sh ш”
                    # is shown in the preëdit (The other candidate,
                    # “shh щ” comes second in the lookup table and
                    # could be selected using arrow-down. But
                    # “translit” hides the lookup table by default).
                    #
                    # Now, when after typing “sh” one types “s”,
                    # the key “shs” has no match, so add_input('s')
                    # returns “False” and we end up here. We pop the
                    # last character “s” which caused the match to
                    # fail, commit first of the previous candidates,
                    # i.e. “sh ш” and feed the “s” into the
                    # key event handler again.
                    self.pop_input()
                    self.commit_everything_unless_invalid()
                    return self._table_mode_process_key_event(key)
                self.commit_everything_unless_invalid()
                self._update_ui()
                return True
            if (self._auto_commit and self.one_candidate()
                    and
                    (self._chars_valid
                     == self._candidates[0][0])):
                self.commit_everything_unless_invalid()
            self._update_ui()
            return True

        # Section to handle trailing invalid input:
        #
        # If the key has still not been handled when this point is
        # reached, it cannot be a valid input character. Neither can
        # it be a select key nor a page-up/page-down key. Adding this
        # key to the tabkeys and search for matching candidates in the
        # table would thus be pointless.
        #
        # So we commit all pending input immediately and then commit
        # this invalid input character as well, possibly converted to
        # fullwidth or halfwidth.
        if keychar:
            if DEBUG_LEVEL > 0:
                LOGGER.debug(
                    'trailing invalid input: keychar=%s', keychar)
            if not self._candidates:
                self.commit_string(self.get_preedit_tabkeys_complete())
            else:
                self.commit_to_preedit()
                self.commit_string(self.get_preedit_string_complete())
            if ascii_ispunct(keychar):
                self.commit_string(self.cond_punct_translate(keychar))
            else:
                self.commit_string(self.cond_letter_translate(keychar))
            return True

        # What kind of key was this??
        #
        #     keychar = IBus.keyval_to_unicode(key.val)
        #
        # returned no result. So whatever this was, we cannot handle it,
        # just pass it through to the application by returning “False”.
        return self._return_false(key.val, key.code, key.state)

    def do_focus_in(self) -> None:
        if DEBUG_LEVEL > 1:
            LOGGER.debug('do_focus_in()')
        if self._on:
            self.register_properties(self.main_prop_list)
            self._update_ui()

    def do_focus_out(self) -> None:
        if self._has_input_purpose:
            self._input_purpose = 0
        self.clear_all_input_and_preedit()

    def do_set_content_type(self, purpose: int, _hints: int) -> None:
        if self._has_input_purpose:
            self._input_purpose = purpose

    def do_enable(self) -> None:
        self._on = True
        self.do_focus_in()

    def do_disable(self) -> None:
        self._on = False

    def do_page_up(self) -> bool:
        '''Called when the page up button in the lookup table is clicked with
        the mouse

        '''
        if self.page_up():
            self._update_ui()
            return True
        return False

    def do_page_down(self) -> bool:
        '''Called when the page down button in the lookup table is clicked with
        the mouse

        '''
        if self.page_down():
            self._update_ui()
            return True
        return False

    def do_cursor_up(self) -> bool:
        '''Called when the mouse wheel is rolled up in the candidate area of
        the lookup table

        '''
        res = self.cursor_up()
        self._update_ui()
        return res

    def do_cursor_down(self) -> bool:
        '''Called when the mouse wheel is rolled down in the candidate area of
        the lookup table

        '''
        res = self.cursor_down()
        self._update_ui()
        return res

    def on_gsettings_value_changed(self, _settings, key) -> None:
        '''
        Called when a value in the settings has been changed.
        '''
        value = it_util.variant_to_value(self._gsettings.get_value(key))
        LOGGER.debug('Settings changed for engine “%s”: key=%s value=%s',
                     self._engine_name, key, value)
        set_functions = {
            'debuglevel':
            {'set_function': self.set_debug_level, 'kwargs': {}},
            'dynamicadjust':
            {'set_function': self.set_dynamic_adjust, 'kwargs': {}},
            'errorsound':
            {'set_function': self.set_error_sound, 'kwargs': {}},
            'errorsoundfile':
            {'set_function': self.set_error_sound_file, 'kwargs': {}},
            'keybindings':
            {'set_function': self.set_keybindings, 'kwargs': {}},
            'autoselect':
            {'set_function': self.set_autoselect_mode, 'kwargs': {}},
            'autocommit':
            {'set_function': self.set_autocommit_mode, 'kwargs': {}},
            'chinesemode':
            {'set_function': self.set_chinese_mode, 'kwargs': {}},
            'lookuptableorientation':
            {'set_function': self.set_lookup_table_orientation, 'kwargs': {}},
            'lookuptablepagesize':
            {'set_function': self.set_page_size, 'kwargs': {}},
            'onechar':
            {'set_function': self.set_onechar_mode, 'kwargs': {}},
            'alwaysshowlookup':
            {'set_function': self.set_always_show_lookup, 'kwargs': {}},
            'singlewildcardchar':
            {'set_function': self.set_single_wildcard_char, 'kwargs': {}},
            'multiwildcardchar':
            {'set_function': self.set_multi_wildcard_char, 'kwargs': {}},
            'autowildcard':
            {'set_function': self.set_autowildcard_mode, 'kwargs': {}},
            'endeffullwidthletter':
            {'set_function': self.set_letter_width,
             'kwargs': dict(input_mode=0)},
            'endeffullwidthpunct':
            {'set_function': self.set_punctuation_width,
             'kwargs': dict(input_mode=0)},
            'tabdeffullwidthletter':
            {'set_function': self.set_letter_width,
             'kwargs': dict(input_mode=1)},
            'tabdeffullwidthpunct':
            {'set_function': self.set_punctuation_width,
             'kwargs': dict(input_mode=1)},
            'inputmode':
            {'set_function': self.set_input_mode, 'kwargs': {}},
            'darktheme':
            {'set_function': self.set_dark_theme, 'kwargs': {}},
        }
        if key in set_functions:
            set_function = set_functions[key]['set_function']
            kwargs = set_functions[key]['kwargs']
            if key != 'inputmode':
                kwargs.update(dict(update_gsettings=False)) # type: ignore
            set_function(value, **kwargs) # type: ignore
            return
        LOGGER.debug('Unknown key')
        return

if __name__ == "__main__":
    LOG_HANDLER = logging.StreamHandler(stream=sys.stderr)
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.addHandler(LOG_HANDLER)
    import doctest
    (FAILED, ATTEMPTED) = doctest.testmod()
    if FAILED:
        sys.exit(1)
    else:
        sys.exit(0)
