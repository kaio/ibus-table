#!/usr/bin/python3

# ibus-table - The Tables engine for IBus
#
# Copyright (c) 2018, 2021 Mike FABIAN <mfabian@redhat.com>
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
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
#

'''
This file implements the test cases for the unit tests of ibus-table
'''
from typing import Any, Optional
import sys
import os
import logging
import time
import sqlite3
import shutil
import tempfile
import unittest
import importlib
from unittest import mock

# pylint: disable=wrong-import-position
from gi import require_version
require_version('IBus', '1.0')
from gi.repository import IBus
# pylint: enable=wrong-import-position

LOGGER = logging.getLogger('ibus-table')

# Get more verbose output in the test log:
os.environ['IBUS_TABLE_DEBUG_LEVEL'] = '255'

# pylint: disable=import-error
from mock_engine import MockEngine
from mock_engine import MockLookupTable
from mock_engine import MockProperty
from mock_engine import MockPropList
# pylint: enable=import-error

# pylint: disable=wrong-import-order
sys.path.insert(0, "../engine")
# pylint: disable=import-error
import table
import tabsqlitedb
# pylint: enable=import-error
sys.path.pop(0)
# pylint: enable=wrong-import-order

# pylint: disable=protected-access
# pylint: disable=missing-function-docstring
# pylint: disable=invalid-name
# pylint: disable=global-statement

ENGINE_PATCHER = mock.patch.object(
    IBus, 'Engine', new=MockEngine)
ENGINE_SIMPLE_PATCHER = mock.patch.object(
    IBus, 'EngineSimple', new=MockEngine)
LOOKUP_TABLE_PATCHER = mock.patch.object(
    IBus, 'LookupTable', new=MockLookupTable)
PROPERTY_PATCHER = mock.patch.object(
    IBus, 'Property', new=MockProperty)
PROP_LIST_PATCHER = mock.patch.object(
    IBus, 'PropList', new=MockPropList)
IBUS_ENGINE = IBus.Engine
IBUS_ENGINE_SIMPLE = IBus.EngineSimple
IBUS_LOOKUP_TABLE = IBus.LookupTable
IBUS_PROPERTY = IBus.Property
IBUS_PROP_LIST = IBus.PropList

ENGINE: Optional[table.TabEngine] = None
TABSQLITEDB = None
ORIG_INPUT_MODE: Optional[int] = None
ORIG_CHINESE_MODE: Optional[int] = None
ORIG_LETTER_WIDTH: Optional[list[Optional[bool]]] = None
ORIG_PUNCTUATION_WIDTH: Optional[list[Optional[bool]]] = None
ORIG_ALWAYS_SHOW_LOOKUP: Optional[bool] = None
ORIG_LOOKUP_TABLE_ORIENTATION: Optional[int] = None
ORIG_PAGE_SIZE: Optional[int] = None
ORIG_ONECHAR_MODE: Optional[bool] = None
ORIG_AUTOSELECT_MODE: Optional[bool] = None
ORIG_AUTOCOMMIT_MODE: Optional[bool] = None
ORIG_COMMIT_INVALID_MODE: Optional[int] = None
ORIG_AUTOWILDCARD_MODE: Optional[bool] = None
ORIG_SINGLE_WILDCARD_CHAR: Optional[str] = None
ORIG_MULTI_WILDCARD_CHAR: Optional[str] = None
ORIG_PINYIN_MODE: Optional[bool] = None
ORIG_SUGGESTION_MODE: Optional[bool] = None
ORIG_KEYBINDINGS = None
ORIG_DYNAMIC_ADJUST: Optional[bool] = None
ORIG_DEBUG_LEVEL: Optional[int] = None

def backup_original_settings() -> None:
    global ORIG_KEYBINDINGS
    global ORIG_INPUT_MODE
    global ORIG_CHINESE_MODE
    global ORIG_LETTER_WIDTH
    global ORIG_PUNCTUATION_WIDTH
    global ORIG_ALWAYS_SHOW_LOOKUP
    global ORIG_LOOKUP_TABLE_ORIENTATION
    global ORIG_PAGE_SIZE
    global ORIG_ONECHAR_MODE
    global ORIG_AUTOSELECT_MODE
    global ORIG_AUTOCOMMIT_MODE
    global ORIG_COMMIT_INVALID_MODE
    global ORIG_AUTOWILDCARD_MODE
    global ORIG_SINGLE_WILDCARD_CHAR
    global ORIG_MULTI_WILDCARD_CHAR
    global ORIG_PINYIN_MODE
    global ORIG_SUGGESTION_MODE
    global ORIG_DYNAMIC_ADJUST
    global ORIG_DEBUG_LEVEL
    assert ENGINE is not None
    ORIG_KEYBINDINGS = ENGINE.get_keybindings()
    ORIG_INPUT_MODE = ENGINE.get_input_mode()
    ORIG_CHINESE_MODE = ENGINE.get_chinese_mode()
    ORIG_LETTER_WIDTH = ENGINE.get_letter_width()
    ORIG_PUNCTUATION_WIDTH = ENGINE.get_punctuation_width()
    ORIG_ALWAYS_SHOW_LOOKUP = ENGINE.get_always_show_lookup()
    ORIG_LOOKUP_TABLE_ORIENTATION = ENGINE.get_lookup_table_orientation()
    ORIG_PAGE_SIZE = ENGINE.get_page_size()
    ORIG_ONECHAR_MODE = ENGINE.get_onechar_mode()
    ORIG_AUTOSELECT_MODE = ENGINE.get_autoselect_mode()
    ORIG_AUTOCOMMIT_MODE = ENGINE.get_autocommit_mode()
    ORIG_COMMIT_INVALID_MODE = ENGINE.get_commit_invalid_mode()
    ORIG_AUTOWILDCARD_MODE = ENGINE.get_autowildcard_mode()
    ORIG_SINGLE_WILDCARD_CHAR = ENGINE.get_single_wildcard_char()
    ORIG_MULTI_WILDCARD_CHAR = ENGINE.get_multi_wildcard_char()
    ORIG_PINYIN_MODE = ENGINE.get_pinyin_mode()
    ORIG_SUGGESTION_MODE = ENGINE.get_suggestion_mode()
    ORIG_DYNAMIC_ADJUST = ENGINE.get_dynamic_adjust()
    ORIG_DEBUG_LEVEL = ENGINE.get_debug_level()

def restore_original_settings() -> None:
    assert ENGINE is not None
    ENGINE.set_keybindings(
        ORIG_KEYBINDINGS, update_gsettings=False)
    assert ORIG_INPUT_MODE is not None
    ENGINE.set_input_mode(ORIG_INPUT_MODE)
    assert ORIG_CHINESE_MODE is not None
    ENGINE.set_chinese_mode(
        ORIG_CHINESE_MODE, update_gsettings=False)
    assert ORIG_LETTER_WIDTH is not None
    assert ORIG_LETTER_WIDTH[0] is not None
    assert ORIG_LETTER_WIDTH[1] is not None
    ENGINE.set_letter_width(
        ORIG_LETTER_WIDTH[0], input_mode=0, update_gsettings=False)
    ENGINE.set_letter_width(
        ORIG_LETTER_WIDTH[1], input_mode=1, update_gsettings=False)
    assert ORIG_PUNCTUATION_WIDTH is not None
    assert ORIG_PUNCTUATION_WIDTH[0] is not None
    assert ORIG_PUNCTUATION_WIDTH[1] is not None
    ENGINE.set_punctuation_width(
        ORIG_PUNCTUATION_WIDTH[0], input_mode=0, update_gsettings=False)
    ENGINE.set_punctuation_width(
        ORIG_PUNCTUATION_WIDTH[1], input_mode=1, update_gsettings=False)
    assert ORIG_ALWAYS_SHOW_LOOKUP is not None
    ENGINE.set_always_show_lookup(
        ORIG_ALWAYS_SHOW_LOOKUP, update_gsettings=False)
    assert ORIG_LOOKUP_TABLE_ORIENTATION is not None
    ENGINE.set_lookup_table_orientation(
        ORIG_LOOKUP_TABLE_ORIENTATION, update_gsettings=False)
    assert ORIG_PAGE_SIZE is not None
    ENGINE.set_page_size(
        ORIG_PAGE_SIZE, update_gsettings=False)
    assert ORIG_ONECHAR_MODE is not None
    ENGINE.set_onechar_mode(ORIG_ONECHAR_MODE, update_gsettings=False)
    assert ORIG_AUTOSELECT_MODE is not None
    ENGINE.set_autoselect_mode(
        ORIG_AUTOSELECT_MODE, update_gsettings=False)
    assert ORIG_AUTOCOMMIT_MODE is not None
    ENGINE.set_autocommit_mode(
        ORIG_AUTOCOMMIT_MODE, update_gsettings=False)
    assert ORIG_COMMIT_INVALID_MODE is not None
    ENGINE.set_commit_invalid_mode(
        ORIG_COMMIT_INVALID_MODE, update_gsettings=False)
    assert ORIG_AUTOWILDCARD_MODE is not None
    ENGINE.set_autowildcard_mode(
        ORIG_AUTOWILDCARD_MODE, update_gsettings=False)
    assert ORIG_SINGLE_WILDCARD_CHAR is not None
    ENGINE.set_single_wildcard_char(
        ORIG_SINGLE_WILDCARD_CHAR, update_gsettings=False)
    assert ORIG_MULTI_WILDCARD_CHAR is not None
    ENGINE.set_multi_wildcard_char(
        ORIG_MULTI_WILDCARD_CHAR, update_gsettings=False)
    assert ORIG_PINYIN_MODE is not None
    ENGINE.set_pinyin_mode(ORIG_PINYIN_MODE)
    assert ORIG_SUGGESTION_MODE is not None
    ENGINE.set_suggestion_mode(ORIG_SUGGESTION_MODE)
    assert ORIG_DYNAMIC_ADJUST is not None
    ENGINE.set_dynamic_adjust(ORIG_DYNAMIC_ADJUST)
    assert ORIG_DEBUG_LEVEL is not None
    ENGINE.set_debug_level(ORIG_DEBUG_LEVEL, update_gsettings=False)

# pylint: disable=too-many-branches
def set_default_settings() -> None:
    assert ENGINE is not None
    assert TABSQLITEDB is not None
    ENGINE.set_input_mode(input_mode=1)
    chinese_mode = 4
    language_filter = TABSQLITEDB.ime_properties.get('language_filter')
    if language_filter in ('cm0', 'cm1', 'cm2', 'cm3', 'cm4'):
        chinese_mode = int(language_filter[-1])
    ENGINE.set_chinese_mode(
        mode=chinese_mode, update_gsettings=False)

    letter_width_mode = False
    def_full_width_letter = TABSQLITEDB.ime_properties.get(
        'def_full_width_letter')
    if def_full_width_letter:
        letter_width_mode = def_full_width_letter.lower() == 'true'
    ENGINE.set_letter_width(
        mode=False, input_mode=0, update_gsettings=False)
    ENGINE.set_letter_width(
        mode=letter_width_mode, input_mode=1, update_gsettings=False)

    punctuation_width_mode = False
    def_full_width_punct = TABSQLITEDB.ime_properties.get(
        'def_full_width_punct')
    if def_full_width_punct:
        punctuation_width_mode = def_full_width_punct.lower() == 'true'
    ENGINE.set_punctuation_width(
        mode=False, input_mode=0, update_gsettings=False)
    ENGINE.set_punctuation_width(
        mode=punctuation_width_mode, input_mode=1, update_gsettings=False)

    always_show_lookup_mode = True
    always_show_lookup = TABSQLITEDB.ime_properties.get(
        'always_show_lookup')
    if always_show_lookup:
        always_show_lookup_mode = always_show_lookup.lower() == 'true'
    ENGINE.set_always_show_lookup(
        always_show_lookup_mode, update_gsettings=False)

    orientation = TABSQLITEDB.get_orientation()
    ENGINE.set_lookup_table_orientation(
        orientation, update_gsettings=False)

    page_size = 6
    select_keys_csv = TABSQLITEDB.ime_properties.get('select_keys')
    # select_keys_csv is something like: "1,2,3,4,5,6,7,8,9,0"
    if select_keys_csv:
        page_size = len(select_keys_csv.split(","))
    ENGINE.set_page_size(
        page_size, update_gsettings=False)

    onechar = False
    ENGINE.set_onechar_mode(
        onechar, update_gsettings=False)

    dynamic_adjust = False
    dynamic_adjust = TABSQLITEDB.ime_properties.get('dynamic_adjust')
    if dynamic_adjust:
        dynamic_adjust = dynamic_adjust.lower() == 'true'
    else:
        dynamic_adjust = True
    ENGINE.set_dynamic_adjust(
        dynamic_adjust, update_gsettings=False)

    auto_select_mode = False
    auto_select = TABSQLITEDB.ime_properties.get('auto_select')
    if auto_select:
        auto_select_mode = auto_select.lower() == 'true'
    ENGINE.set_autoselect_mode(
        auto_select_mode, update_gsettings=False)

    auto_commit_mode = False
    auto_commit = TABSQLITEDB.ime_properties.get('auto_commit')
    if auto_commit:
        auto_commit_mode = auto_commit.lower() == 'true'
    ENGINE.set_autocommit_mode(
        auto_commit_mode, update_gsettings=False)

    commit_invalid_mode = 0
    ENGINE.set_commit_invalid_mode(
        commit_invalid_mode, update_gsettings=False)

    page_down_keys_csv = TABSQLITEDB.ime_properties.get(
        'page_down_keys')
    if page_down_keys_csv:
        page_down_keys = [
            IBus.keyval_from_name(x)
            for x in page_down_keys_csv.split(',')]
    commit_keys_csv = TABSQLITEDB.ime_properties.get('commit_keys')
    if commit_keys_csv:
        commit_keys = [
            IBus.keyval_from_name(x)
            for x in commit_keys_csv.split(',')]

    auto_wildcard_mode = True
    auto_wildcard = TABSQLITEDB.ime_properties.get('auto_wildcard')
    if auto_wildcard:
        auto_wildcard_mode = auto_wildcard.lower() == 'true'
    ENGINE.set_autowildcard_mode(
        auto_wildcard_mode, update_gsettings=False)

    single_wildcard_char = TABSQLITEDB.ime_properties.get(
        'single_wildcard_char')
    if not single_wildcard_char:
        single_wildcard_char = ''
    if len(single_wildcard_char) > 1:
        single_wildcard_char = single_wildcard_char[0]
    ENGINE.set_single_wildcard_char(
        single_wildcard_char, update_gsettings=False)

    multi_wildcard_char = TABSQLITEDB.ime_properties.get(
        'multi_wildcard_char')
    if not multi_wildcard_char:
        multi_wildcard_char = ''
    if len(multi_wildcard_char) > 1:
        multi_wildcard_char = multi_wildcard_char[0]
    ENGINE.set_multi_wildcard_char(
        multi_wildcard_char, update_gsettings=False)

    ENGINE.set_pinyin_mode(False)
    ENGINE.set_suggestion_mode(False)

    page_up_keys_csv = TABSQLITEDB.ime_properties.get(
        'page_up_keys')
    if page_up_keys_csv:
        page_up_keys = [
            IBus.keyval_from_name(x)
            for x in page_up_keys_csv.split(',')]
    ENGINE._commit_key_names = [
        IBus.keyval_name(keyval) for keyval in commit_keys]
    ENGINE._page_down_key_names = [
        IBus.keyval_name(keyval) for keyval in page_down_keys]
    ENGINE._page_up_key_names = [
        IBus.keyval_name(keyval) for keyval in page_up_keys]
    user_keybindings={}
    ENGINE.set_keybindings(user_keybindings, update_gsettings=False)

    # Get more verbose output in the test log:
    ENGINE.set_debug_level(255)
# pylint: enable=too-many-branches

def set_up(engine_name: str) -> bool:
    '''
    Setup an ibus table engine

    :param engine_name: The name of the engine to setup
    :return: True if the engine could be setup successfully, False if not.
    '''
    global TABSQLITEDB
    global ENGINE
    ENGINE_PATCHER.start()
    ENGINE_SIMPLE_PATCHER.start()
    LOOKUP_TABLE_PATCHER.start()
    PROPERTY_PATCHER.start()
    PROP_LIST_PATCHER.start()
    assert IBus.Engine is not IBUS_ENGINE
    assert IBus.Engine is MockEngine  # type: ignore[comparison-overlap]
    assert IBus.EngineSimple is not IBUS_ENGINE_SIMPLE
    assert IBus.EngineSimple is MockEngine  # type: ignore[comparison-overlap]
    assert IBus.LookupTable is not IBUS_LOOKUP_TABLE
    assert IBus.LookupTable is MockLookupTable  # type: ignore[comparison-overlap]
    assert IBus.Property is not IBUS_PROPERTY
    assert IBus.Property is MockProperty  # type: ignore[comparison-overlap]
    assert IBus.PropList is not IBUS_PROP_LIST
    assert IBus.PropList is MockPropList  # type: ignore[comparison-overlap]
    # Reload the table module so that the patches
    # are applied to TabEngine:
    sys.path.insert(0, '../engine')
    importlib.reload(table)
    sys.path.pop(0)
    bus = IBus.Bus()
    db_dir = '/usr/share/ibus-table/tables'
    db_file = os.path.join(db_dir, engine_name + '.db')
    if not os.path.isfile(db_file):
        TABSQLITEDB = None
        ENGINE = None
        tear_down()
        return False
    TABSQLITEDB = tabsqlitedb.TabSqliteDb(
        filename=db_file, user_db=':memory:')
    ENGINE = table.TabEngine(
        bus,
        f'/com/redhat/IBus/engines/table/{engine_name}/engine/0',
        TABSQLITEDB,
        unit_test=True)
    backup_original_settings()
    set_default_settings()
    return True

def tear_down() -> None:
    global TABSQLITEDB
    global ENGINE
    if ENGINE:
        restore_original_settings()
        TABSQLITEDB = None
        ENGINE = None
    # Remove the patches from the IBus stuff:
    ENGINE_PATCHER.stop()
    ENGINE_SIMPLE_PATCHER.stop()
    LOOKUP_TABLE_PATCHER.stop()
    PROPERTY_PATCHER.stop()
    PROP_LIST_PATCHER.stop()
    assert IBus.Engine is IBUS_ENGINE
    assert IBus.Engine is not MockEngine  # type: ignore[comparison-overlap]
    assert IBus.EngineSimple is IBUS_ENGINE_SIMPLE
    assert IBus.EngineSimple is not MockEngine  # type: ignore[comparison-overlap]
    assert IBus.LookupTable is IBUS_LOOKUP_TABLE
    assert IBus.LookupTable is not MockLookupTable  # type: ignore[comparison-overlap]
    assert IBus.Property is IBUS_PROPERTY
    assert IBus.Property is not MockProperty  # type: ignore[comparison-overlap]
    assert IBus.PropList is IBUS_PROP_LIST
    assert IBus.PropList is not MockPropList  # type: ignore[comparison-overlap]

def require_serial_number(required_serial_number: int) -> bool:
    if TABSQLITEDB is None:
        return False
    serial_number = int(TABSQLITEDB.ime_properties.get('serial_number'))
    return serial_number >= required_serial_number

class ErbiQsTestCase(unittest.TestCase):
    '''Test cases for the erbi-qs table'''
    def setUp(self) -> None:
        engine_name = 'erbi-qs'
        if not set_up(engine_name):
            self.skipTest(f'Could not setup “{engine_name}”, skipping test.')

    def tearDown(self) -> None:
        tear_down()

    def test_dummy(self) -> None:
        self.assertEqual(True, True)

    def test_get_goucima(self) -> None:
        if not require_serial_number(20220111):
            self.skipTest('serial_number too small')
        assert TABSQLITEDB is not None
        self.assertEqual(
            'sxr.',
            TABSQLITEDB.get_goucima('松'))
        self.assertEqual(
            'thr',
            TABSQLITEDB.get_goucima('天'))
        self.assertEqual(
            'xjv',
            TABSQLITEDB.get_goucima('下'))
        self.assertEqual(
            'dkv',
            TABSQLITEDB.get_goucima('大'))
        self.assertEqual(
            'sjnb',
            TABSQLITEDB.get_goucima('事'))

    def test_parse_phrase(self) -> None:
        if not require_serial_number(20220111):
            self.skipTest('serial_number too small')
        assert TABSQLITEDB is not None
        self.assertEqual(
            'txds',
            TABSQLITEDB.parse_phrase('天下大事'))

class WubiJidian86TestCase(unittest.TestCase):
    '''Test cases for the wubi-jidian86 table'''
    def setUp(self) -> None:
        engine_name = 'wubi-jidian86'
        if not set_up(engine_name):
            self.skipTest(f'Could not setup “{engine_name}”, skipping test.')

    def tearDown(self) -> None:
        tear_down()

    def test_dummy(self) -> None:
        self.assertEqual(True, True)

    def test_parse_phrase(self) -> None:
        assert TABSQLITEDB is not None
        self.assertEqual(
            'ggdg',
            TABSQLITEDB.parse_phrase('天下大事'))

    def test_single_char_commit_with_space(self) -> None:
        assert ENGINE is not None
        ENGINE._do_process_key_event(IBus.KEY_a, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(ENGINE.mock_committed_text, '工')

    def test_toggle_suggestion_mode_with_keybinding(self) -> None:
        assert ENGINE is not None
        if not ENGINE._ime_sg:
            self.skipTest("This engine does not have a suggestion mode.")
        self.assertEqual(ENGINE.get_suggestion_mode(), False)
        ENGINE._do_process_key_event(
            IBus.KEY_F6, 0,
            IBus.ModifierType.SUPER_MASK | IBus.ModifierType.MOD4_MASK)
        self.assertEqual(ENGINE.get_suggestion_mode(), True)
        ENGINE._do_process_key_event(
            IBus.KEY_F6, 0,
            IBus.ModifierType.SUPER_MASK | IBus.ModifierType.MOD4_MASK)
        self.assertEqual(ENGINE.get_suggestion_mode(), False)

    def test_toggle_input_mode_with_keybinding(self) -> None:
        assert ENGINE is not None
        self.assertEqual(ENGINE.get_input_mode(), 1)
        ENGINE._do_process_key_event(
            IBus.KEY_Shift_L, 0,
            IBus.ModifierType.SHIFT_MASK | IBus.ModifierType.RELEASE_MASK)
        # This should have successfully switched, although there was
        # only a key release, no key press. Matching on modifiers keys
        # like Shift_L matches only on key release and checks whether
        # the previous key pressed was exactly the same key (To avoid
        # matching on something like “Shift_L” + “a”).  But when this
        # is very first key event after the startup of ibus-table, the
        # previous key is still empty. The it_util.HotKey class then
        # assumes that the previous key was the same automatically.
        self.assertEqual(ENGINE.get_input_mode(), 0)
        ENGINE._do_process_key_event(
            IBus.KEY_Shift_L, 0,
            IBus.ModifierType.SHIFT_MASK)
        ENGINE._do_process_key_event(
            IBus.KEY_Control_L, 0,
            IBus.ModifierType.CONTROL_MASK)
        ENGINE._do_process_key_event(
            IBus.KEY_Shift_L, 0,
            IBus.ModifierType.SHIFT_MASK | IBus.ModifierType.RELEASE_MASK)
        # This should have failed to switch because the key before the
        # release of “Shift_L” was not a “Shift_L” key.
        self.assertEqual(ENGINE.get_input_mode(), 0)
        ENGINE._do_process_key_event(
            IBus.KEY_Shift_L, 0,
            IBus.ModifierType.SHIFT_MASK | IBus.ModifierType.RELEASE_MASK)
        # This switch should succeed because the previous key was
        # also a “Shift_L” (also a key release, but this doesn’t matter
        # I don’t check for this case as it cannot happen in reality).
        self.assertEqual(ENGINE.get_input_mode(), 1)

    def test_switch_to_next_chinese_mode_with_keybinding(self) -> None:
        assert ENGINE is not None
        self.assertEqual(ENGINE.get_chinese_mode(), 2)
        # Now change with the keybinding:
        ENGINE._do_process_key_event(IBus.KEY_semicolon, 0, IBus.ModifierType.CONTROL_MASK)
        self.assertEqual(ENGINE.get_chinese_mode(), 3)

    def test_toggle_onechar_mode_with_keybinding(self) -> None:
        assert ENGINE is not None
        self.assertEqual(ENGINE.get_onechar_mode(), False)
        ENGINE.set_onechar_mode(True, update_gsettings=False)
        self.assertEqual(ENGINE.get_onechar_mode(), True)
        ENGINE.set_onechar_mode(False, update_gsettings=False)
        self.assertEqual(ENGINE.get_onechar_mode(), False)
        # Now change with the keybinding:
        ENGINE._do_process_key_event(
            IBus.KEY_comma, 0, IBus.ModifierType.CONTROL_MASK)
        self.assertEqual(ENGINE.get_onechar_mode(), True)
        # Using the keybinding updates gsettings,
        # wait until the update is effective:
        time.sleep(1)
        self.assertEqual(ENGINE.get_onechar_mode(), True)
        ENGINE._do_process_key_event(
            IBus.KEY_comma, 0, IBus.ModifierType.CONTROL_MASK)
        self.assertEqual(ENGINE.get_onechar_mode(), False)
        # Using the keybinding updates gsettings,
        # wait until the update is effective:
        time.sleep(1)
        self.assertEqual(ENGINE.get_onechar_mode(), False)

    def test_toggle_autocommit_mode_with_keybinding(self) -> None:
        assert ENGINE is not None
        self.assertEqual(ENGINE.get_autocommit_mode(), False)
        ENGINE.set_autocommit_mode(True, update_gsettings=False)
        self.assertEqual(ENGINE.get_autocommit_mode(), True)
        ENGINE.set_autocommit_mode(False, update_gsettings=False)
        self.assertEqual(ENGINE.get_autocommit_mode(), False)
        # Now change with the keybinding:
        ENGINE._do_process_key_event(
            IBus.KEY_slash, 0, IBus.ModifierType.CONTROL_MASK)
        self.assertEqual(ENGINE.get_autocommit_mode(), True)
        # Using the keybinding updates gsettings,
        # wait until the update is effective:
        time.sleep(1)
        self.assertEqual(ENGINE.get_autocommit_mode(), True)
        ENGINE._do_process_key_event(
            IBus.KEY_slash, 0, IBus.ModifierType.CONTROL_MASK)
        self.assertEqual(ENGINE.get_autocommit_mode(), False)
        # Using the keybinding updates gsettings,
        # wait until the update is effective:
        time.sleep(1)
        self.assertEqual(ENGINE.get_autocommit_mode(), False)

    def test_change_letter_width(self) -> None:
        assert ENGINE is not None
        # The defaults come from the wubi-jidian86.txt source:
        # DEF_FULL_WIDTH_LETTER = FALSE
        self.assertEqual(ENGINE.get_letter_width(), [False, False])
        ENGINE.set_letter_width(mode=True, input_mode=0, update_gsettings=False)
        self.assertEqual(ENGINE.get_letter_width(), [True, False])
        ENGINE.set_letter_width(mode=True, input_mode=1, update_gsettings=False)
        self.assertEqual(ENGINE.get_letter_width(), [True, True])
        # Restore the default:
        ENGINE.set_letter_width(mode=False, input_mode=0, update_gsettings=False)
        ENGINE.set_letter_width(mode=False, input_mode=1, update_gsettings=False)
        self.assertEqual(ENGINE.get_letter_width(), [False, False])
        # Now change it for input mode 1 with the default keybinding:
        self.assertEqual(ENGINE.get_input_mode(), 1)
        ENGINE._do_process_key_event(IBus.KEY_space, 0, IBus.ModifierType.SHIFT_MASK)
        self.assertEqual(ENGINE.get_letter_width(), [False, True])
        # Restore it for input mode 1 with the default keybinding:
        ENGINE._do_process_key_event(IBus.KEY_space, 0, IBus.ModifierType.SHIFT_MASK)
        self.assertEqual(ENGINE.get_letter_width(), [False, False])
        # Now change it for input mode 0 with the default keybinding:
        ENGINE.set_input_mode(0)
        self.assertEqual(ENGINE.get_input_mode(), 0)
        ENGINE._do_process_key_event(IBus.KEY_space, 0, IBus.ModifierType.SHIFT_MASK)
        self.assertEqual(ENGINE.get_letter_width(), [True, False])
        # Restore it for input mode 0 with the default keybinding:
        ENGINE._do_process_key_event(IBus.KEY_space, 0, IBus.ModifierType.SHIFT_MASK)
        self.assertEqual(ENGINE.get_letter_width(), [False, False])

    def test_change_punctuation_width(self) -> None:
        assert ENGINE is not None
        # The defaults come from the wubi-jidian86.txt source:
        # DEF_FULL_WIDTH_PUNCT = TRUE
        self.assertEqual(ENGINE.get_punctuation_width(), [False, True])
        ENGINE.set_punctuation_width(mode=True, input_mode=0, update_gsettings=False)
        self.assertEqual(ENGINE.get_punctuation_width(), [True, True])
        ENGINE.set_punctuation_width(mode=False, input_mode=1, update_gsettings=False)
        self.assertEqual(ENGINE.get_punctuation_width(), [True, False])
        # Restore the default:
        ENGINE.set_punctuation_width(mode=False, input_mode=0, update_gsettings=False)
        ENGINE.set_punctuation_width(mode=False, input_mode=1, update_gsettings=False)
        self.assertEqual(ENGINE.get_punctuation_width(), [False, False])
        # Now change it for input mode 1 with the default keybinding:
        self.assertEqual(ENGINE.get_input_mode(), 1)
        ENGINE._do_process_key_event(IBus.KEY_period, 0, IBus.ModifierType.CONTROL_MASK)
        self.assertEqual(ENGINE.get_punctuation_width(), [False, True])
        # Restore it for input mode 1 with the default keybinding:
        ENGINE._do_process_key_event(IBus.KEY_period, 0, IBus.ModifierType.CONTROL_MASK)
        self.assertEqual(ENGINE.get_punctuation_width(), [False, False])
        # Now change it for input mode 0 with the default keybinding:
        ENGINE.set_input_mode(0)
        self.assertEqual(ENGINE.get_input_mode(), 0)
        ENGINE._do_process_key_event(IBus.KEY_period, 0, IBus.ModifierType.CONTROL_MASK)
        self.assertEqual(ENGINE.get_punctuation_width(), [True, False])
        # Restore it for input mode 0 with the default keybinding:
        ENGINE._do_process_key_event(IBus.KEY_period, 0, IBus.ModifierType.CONTROL_MASK)
        self.assertEqual(ENGINE.get_punctuation_width(), [False, False])

    def test_next_and_previous_candidates_in_page(self) -> None:
        assert ENGINE is not None
        ENGINE._do_process_key_event(IBus.KEY_a, 0, 0)
        # Candidate results are capped to at most 100 entries (see
        # best_candidates() in tabsqlitedb.py) and are all loaded into
        # the lookup table immediately, not just the first page of 10.
        self.assertEqual(len(ENGINE._lookup_table.mock_candidates), 100)
        self.assertEqual(ENGINE._lookup_table.mock_candidates[:10],
                         ['工  99454797 0',
                          '区 qi 1730000000 0',
                          '或 kg 1250000000 0',
                          '或 kgd 1250000000 0',
                          '其 dw 1150000000 0',
                          '其 dwu 1150000000 0',
                          '其他 dwb 685000000 0',
                          '世界 nlw 684000000 0',
                          '花 wx 598000000 0',
                          '花 wxb 598000000 0'])
        self.assertEqual(ENGINE.mock_preedit_text, '工')
        self.assertEqual(ENGINE.mock_committed_text, '')
        # Go one candidate down in the candidate list:
        ENGINE._do_process_key_event(
            IBus.KEY_Alt_L, 0,
            IBus.ModifierType.MOD1_MASK)
        ENGINE._do_process_key_event(
            IBus.KEY_Alt_L, 0,
            IBus.ModifierType.MOD1_MASK | IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(ENGINE.mock_preedit_text, '区')
        self.assertEqual(ENGINE.mock_committed_text, '')
        # Go one candidate up in the candidate list:
        ENGINE._do_process_key_event(
            IBus.KEY_Alt_L, 0,
            IBus.ModifierType.MOD1_MASK
            | IBus.ModifierType.CONTROL_MASK)
        ENGINE._do_process_key_event(
            IBus.KEY_Alt_L, 0,
            IBus.ModifierType.MOD1_MASK
            | IBus.ModifierType.CONTROL_MASK
            | IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(ENGINE.mock_preedit_text, '工')
        self.assertEqual(ENGINE.mock_committed_text, '')
        # Go three candidates up in the candidate list
        # (should wrap around in the current page):
        #
        # 1
        ENGINE._do_process_key_event(
            IBus.KEY_Alt_L, 0,
            IBus.ModifierType.MOD1_MASK
            | IBus.ModifierType.CONTROL_MASK)
        ENGINE._do_process_key_event(
            IBus.KEY_Alt_L, 0,
            IBus.ModifierType.MOD1_MASK
            | IBus.ModifierType.CONTROL_MASK
            | IBus.ModifierType.RELEASE_MASK)
        # 2
        ENGINE._do_process_key_event(
            IBus.KEY_Alt_L, 0,
            IBus.ModifierType.MOD1_MASK
            | IBus.ModifierType.CONTROL_MASK)
        ENGINE._do_process_key_event(
            IBus.KEY_Alt_L, 0,
            IBus.ModifierType.MOD1_MASK
            | IBus.ModifierType.CONTROL_MASK
            | IBus.ModifierType.RELEASE_MASK)
        # 3
        ENGINE._do_process_key_event(
            IBus.KEY_Alt_L, 0,
            IBus.ModifierType.MOD1_MASK
            | IBus.ModifierType.CONTROL_MASK)
        ENGINE._do_process_key_event(
            IBus.KEY_Alt_L, 0,
            IBus.ModifierType.MOD1_MASK
            | IBus.ModifierType.CONTROL_MASK
            | IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(ENGINE.mock_preedit_text, '世界')
        self.assertEqual(ENGINE.mock_committed_text, '')
        ENGINE._do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, '世界')

    def test_cancel_key_binding_changed(self) -> None:
        assert ENGINE is not None
        ENGINE._do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '工')
        self.assertEqual(ENGINE.mock_committed_text, '')
        # This 'Insert' does not 'cancel' because the default key for
        # 'cancel' is 'Escape':
        ENGINE._do_process_key_event(IBus.KEY_Insert, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '工')
        self.assertEqual(ENGINE.mock_committed_text, '')
        ENGINE._do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(ENGINE.mock_committed_text, '工')
        # Changing the key binding for 'cancel':
        ENGINE.set_keybindings({
            'cancel': ['Insert'],
            }, update_gsettings=False)
        ENGINE._do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '工')
        self.assertEqual(ENGINE.mock_committed_text, '工')
        # Now this 'Insert' should cancel, i.e. empty the preedit:
        ENGINE._do_process_key_event(IBus.KEY_Insert, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, '工')
        # And as the preedit is empty now, there is nothing to commit
        # and the 'space' key just adds a space:
        ENGINE._do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(ENGINE.mock_committed_text, '工 ')

    def test_pinyin_mode(self) -> None:
        assert ENGINE is not None
        # Pinyin mode is False by default:
        self.assertEqual(ENGINE.get_pinyin_mode(), False)
        ENGINE._do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '工')
        ENGINE._do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, '工')
        ENGINE.set_pinyin_mode(True)
        ENGINE._do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '啊')
        # Capped to at most 100 entries (see best_candidates() in
        # tabsqlitedb.py) and all loaded immediately, not just page 1.
        self.assertEqual(len(ENGINE._lookup_table.mock_candidates), 100)
        self.assertEqual(ENGINE._lookup_table.mock_candidates[:10],
                         ['啊 ↑5   kbsk 464000000 0',
                          '阿 ↑1   bskg 319000000 0',
                          '阿 ↑3   bskg 319000000 0',
                          '阿 ↑4   bskg 319000000 0',
                          '阿 ↑5   bskg 319000000 0',
                          '吖 ↑1   kuhh 9910000 0',
                          '腌 ↑1   edjn 4100000 0',
                          '锕 ↑1   qbsk 1690000 0',
                          '嗄 ↑2   kdht 1510000 0',
                          '錒 ↑1   qbsk 503000 0'])
        ENGINE._do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, '工啊')
        ENGINE.set_pinyin_mode(False)
        ENGINE._do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '工')
        ENGINE._do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, '工啊工')

    def test_pinyin_mode_chinese_mode(self) -> None:
        assert ENGINE is not None
        # Pinyin mode is False by default:
        self.assertEqual(ENGINE.get_pinyin_mode(), False)
        ENGINE.set_pinyin_mode(True)
        ENGINE.set_chinese_mode(0) # simplified only
        ENGINE._do_process_key_event(IBus.KEY_m, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_a, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_numbersign, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '吗')
        # All matching entries are loaded immediately now, not just
        # the first page, so this list is longer than it used to be.
        self.assertEqual(ENGINE._lookup_table.mock_candidates,
                         ['吗    kcg 959000000 0',
                          '码    dcg 274000000 0',
                          '马    cnng 236000000 0',
                          '玛    gcg 51300000 0',
                          '蚂    jcg 3110000 0',
                          '杩    scg 1280000 0',
                          '犸    qtcg 120000 0',
                          '鰢    qocy 36500 0',
                          '㐷    wcg 9070 0',
                          '䣕    cbh 3340 0',
                          '䣖    ckcn 3160 0',
                          '𥉵    yfjh 0 0'])
        ENGINE._do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, '吗')
        ENGINE.set_chinese_mode(1) # traditional only
        ENGINE._do_process_key_event(IBus.KEY_m, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_a, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_numbersign, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '嗎')
        self.assertEqual(ENGINE._lookup_table.mock_candidates,
                         ['嗎    kcy 148000000 0',
                          '馬    cghy 99400000 0',
                          '碼    dcy 38600000 0',
                          '瑪    gcy 15900000 0',
                          '鎷    qcy 1650000 0',
                          '螞    jcy 662000 0',
                          '榪    scy 142000 0',
                          '獁    qtcy 41200 0',
                          '溤    icy 38700 0',
                          '鰢    qocy 36500 0',
                          '鷌    wvgc 25500 0',
                          '䣕    cbh 3340 0',
                          '䣖    ckcn 3160 0',
                          '𥉵    yfjh 0 0'])
        ENGINE._do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, '吗嗎')
        ENGINE.set_chinese_mode(2) # simplified first
        ENGINE._do_process_key_event(IBus.KEY_m, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_a, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_numbersign, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '吗')
        self.assertEqual(ENGINE._lookup_table.mock_candidates,
                         ['吗    kcg 959000000 0',
                          '码    dcg 274000000 0',
                          '马    cnng 236000000 0',
                          '玛    gcg 51300000 0',
                          '蚂    jcg 3110000 0',
                          '杩    scg 1280000 0',
                          '犸    qtcg 120000 0',
                          '鰢    qocy 36500 0',
                          '㐷    wcg 9070 0',
                          '䣕    cbh 3340 0',
                          '䣖    ckcn 3160 0',
                          '𥉵    yfjh 0 0',
                          '嗎    kcy 148000000 0',
                          '馬    cghy 99400000 0',
                          '碼    dcy 38600000 0',
                          '瑪    gcy 15900000 0',
                          '鎷    qcy 1650000 0',
                          '螞    jcy 662000 0',
                          '榪    scy 142000 0',
                          '獁    qtcy 41200 0',
                          '溤    icy 38700 0',
                          '鷌    wvgc 25500 0'])
        ENGINE._do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, '吗嗎吗')
        ENGINE.set_chinese_mode(3) # traditional first
        ENGINE._do_process_key_event(IBus.KEY_m, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_a, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_numbersign, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '嗎')
        self.assertEqual(ENGINE._lookup_table.mock_candidates,
                         ['嗎    kcy 148000000 0',
                          '馬    cghy 99400000 0',
                          '碼    dcy 38600000 0',
                          '瑪    gcy 15900000 0',
                          '鎷    qcy 1650000 0',
                          '螞    jcy 662000 0',
                          '榪    scy 142000 0',
                          '獁    qtcy 41200 0',
                          '溤    icy 38700 0',
                          '鰢    qocy 36500 0',
                          '鷌    wvgc 25500 0',
                          '䣕    cbh 3340 0',
                          '䣖    ckcn 3160 0',
                          '𥉵    yfjh 0 0',
                          '吗    kcg 959000000 0',
                          '码    dcg 274000000 0',
                          '马    cnng 236000000 0',
                          '玛    gcg 51300000 0',
                          '蚂    jcg 3110000 0',
                          '杩    scg 1280000 0',
                          '犸    qtcg 120000 0',
                          '㐷    wcg 9070 0'])
        ENGINE._do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, '吗嗎吗嗎')
        ENGINE.set_chinese_mode(4) # all characters
        ENGINE._do_process_key_event(IBus.KEY_m, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_a, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_numbersign, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '吗')
        self.assertEqual(ENGINE._lookup_table.mock_candidates,
                         ['吗    kcg 959000000 0',
                          '码    dcg 274000000 0',
                          '马    cnng 236000000 0',
                          '嗎    kcy 148000000 0',
                          '馬    cghy 99400000 0',
                          '玛    gcg 51300000 0',
                          '碼    dcy 38600000 0',
                          '瑪    gcy 15900000 0',
                          '蚂    jcg 3110000 0',
                          '鎷    qcy 1650000 0',
                          '杩    scg 1280000 0',
                          '螞    jcy 662000 0',
                          '榪    scy 142000 0',
                          '犸    qtcg 120000 0',
                          '獁    qtcy 41200 0',
                          '溤    icy 38700 0',
                          '鰢    qocy 36500 0',
                          '鷌    wvgc 25500 0',
                          '㐷    wcg 9070 0',
                          '䣕    cbh 3340 0',
                          '䣖    ckcn 3160 0',
                          '𥉵    yfjh 0 0'])
        ENGINE._do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, '吗嗎吗嗎吗')

    def test_suggestion_mode(self) -> None:
        assert ENGINE is not None
        if not ENGINE._ime_sg:
            self.skipTest("This engine does not have a suggestion mode.")
        # Suggestion mode is False by default:
        self.assertEqual(ENGINE.get_suggestion_mode(), False)
        self.assertEqual(ENGINE.get_pinyin_mode(), False)
        ENGINE._do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '工')
        ENGINE._do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, '工')
        self.assertEqual(ENGINE._lookup_table.mock_candidates, [])
        ENGINE.set_suggestion_mode(True)
        ENGINE._do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '工')
        ENGINE._do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, '工工')
        # Capped to at most 100 entries (see select_suggestion_candidate()
        # in tabsqlitedb.py) and all loaded immediately, not just page 1.
        self.assertEqual(len(ENGINE._lookup_table.mock_candidates), 100)
        self.assertEqual(ENGINE._lookup_table.mock_candidates[:10],
                         ['工作人员 673 0',
                          '工作会议 310 0',
                          '工作报告 267 0',
                          '工人阶级 146 0',
                          '工作重点 78 0',
                          '工作小组 73 0',
                          '工业企业 71 0',
                          '工业大学 69 0',
                          '工作单位 61 0',
                          '工业生产 58 0'])
        ENGINE._do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, '工工作人员')
        ENGINE.set_pinyin_mode(True)
        ENGINE._do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '啊')
        ENGINE._do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, '工工作人员啊')
        self.assertEqual(ENGINE._lookup_table.mock_candidates,
                         ['啊呀 145 0',
                          '啊哈 103 0',
                          '啊哟 23 0',
                          '啊唷 7 0'])
        ENGINE._do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, '工工作人员啊呀')
        ENGINE._do_process_key_event(IBus.KEY_a, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_i, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '爱')
        ENGINE._do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, '工工作人员啊呀爱')
        self.assertEqual(len(ENGINE._lookup_table.mock_candidates), 100)
        self.assertEqual(ENGINE._lookup_table.mock_candidates[:10],
                         ['爱因斯坦 1109 0',
                          '爱情故事 519 0',
                          '爱国主义 191 0',
                          '爱尔兰语 91 0',
                          '爱好和平 62 0',
                          '爱情小说 58 0',
                          '爱不释手 39 0',
                          '爱国热情 35 0',
                          '爱莫能助 34 0',
                          '爱理不理 32 0'])
        ENGINE._do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, '工工作人员啊呀爱因斯坦')

    def test_suggestion_mode_cancel(self) -> None:
        '''See: https://github.com/mike-fabian/ibus-table/pull/215'''
        assert ENGINE is not None
        if not ENGINE._ime_sg:
            self.skipTest("This engine does not have a suggestion mode.")
        # Suggestion mode is False by default:
        self.assertEqual(ENGINE.get_suggestion_mode(), False)
        self.assertEqual(ENGINE.get_pinyin_mode(), False)
        ENGINE._do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '工')
        ENGINE._do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, '工')
        self.assertEqual(ENGINE._lookup_table.mock_candidates, [])
        ENGINE.set_suggestion_mode(True)
        ENGINE._do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '工')
        ENGINE._do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, '工工')
        self.assertEqual(len(ENGINE._lookup_table.mock_candidates), 100)
        self.assertEqual(ENGINE._lookup_table.mock_candidates[:10],
                         ['工作人员 673 0',
                          '工作会议 310 0',
                          '工作报告 267 0',
                          '工人阶级 146 0',
                          '工作重点 78 0',
                          '工作小组 73 0',
                          '工业企业 71 0',
                          '工业大学 69 0',
                          '工作单位 61 0',
                          '工业生产 58 0'])
        handled = ENGINE._do_process_key_event(IBus.KEY_Escape, 0, 0)
        self.assertTrue(handled)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, '工工')
        self.assertEqual(ENGINE._lookup_table.mock_candidates, [])
        ENGINE._do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '工')
        ENGINE._do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, '工工工')
        self.assertEqual(len(ENGINE._lookup_table.mock_candidates), 100)
        self.assertEqual(ENGINE._lookup_table.mock_candidates[:10],
                         ['工作人员 673 0',
                          '工作会议 310 0',
                          '工作报告 267 0',
                          '工人阶级 146 0',
                          '工作重点 78 0',
                          '工作小组 73 0',
                          '工业企业 71 0',
                          '工业大学 69 0',
                          '工作单位 61 0',
                          '工业生产 58 0'])
        handled = ENGINE._do_process_key_event(IBus.KEY_BackSpace, 0, 0)
        self.assertTrue(handled)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, '工工工')
        self.assertEqual(ENGINE._lookup_table.mock_candidates, [])


    def test_commit_to_preedit_switching_to_pinyin_defining_a_phrase(self) -> None:
        assert ENGINE is not None
        ENGINE._do_process_key_event(IBus.KEY_a, 0, 0)
        # commit to preëdit needs a press and release of either
        # the left or the right shift key:
        ENGINE._do_process_key_event(
            IBus.KEY_Shift_L, 0,
            IBus.ModifierType.CONTROL_MASK | IBus.ModifierType.SHIFT_MASK)
        ENGINE._do_process_key_event(
            IBus.KEY_Shift_L, 0,
            IBus.ModifierType.CONTROL_MASK | IBus.ModifierType.SHIFT_MASK
            | IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(ENGINE.mock_preedit_text, '工')
        self.assertEqual(ENGINE.mock_committed_text, '')
        ENGINE._do_process_key_event(IBus.KEY_b, 0, 0)
        ENGINE._do_process_key_event(
            IBus.KEY_Shift_R, 0,
            IBus.ModifierType.CONTROL_MASK | IBus.ModifierType.SHIFT_MASK)
        ENGINE._do_process_key_event(
            IBus.KEY_Shift_R, 0,
            IBus.ModifierType.CONTROL_MASK | IBus.ModifierType.SHIFT_MASK
            | IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(ENGINE.mock_preedit_text, '工了')
        self.assertEqual(ENGINE.mock_committed_text, '')
        ENGINE._do_process_key_event(IBus.KEY_c, 0, 0)
        ENGINE._do_process_key_event(
            IBus.KEY_Shift_R, 0,
            IBus.ModifierType.CONTROL_MASK | IBus.ModifierType.SHIFT_MASK)
        ENGINE._do_process_key_event(
            IBus.KEY_Shift_R, 0,
            IBus.ModifierType.CONTROL_MASK | IBus.ModifierType.SHIFT_MASK
            | IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(ENGINE.mock_preedit_text, '工了以')
        self.assertEqual(ENGINE.mock_committed_text, '')
        ENGINE._do_process_key_event(IBus.KEY_d, 0, 0)
        ENGINE._do_process_key_event(
            IBus.KEY_Shift_L, 0,
            IBus.ModifierType.CONTROL_MASK | IBus.ModifierType.SHIFT_MASK)
        ENGINE._do_process_key_event(
            IBus.KEY_Shift_L, 0,
            IBus.ModifierType.CONTROL_MASK | IBus.ModifierType.SHIFT_MASK
            | IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(ENGINE.mock_preedit_text, '工了以在')
        self.assertEqual(ENGINE.mock_committed_text, '')
        # Move left two characters in the preëdit:
        ENGINE._do_process_key_event(IBus.KEY_Left, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_Left, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '工了以在')
        self.assertEqual(ENGINE.mock_committed_text, '')
        self.assertEqual(ENGINE._chars_valid, '')
        self.assertEqual(ENGINE._chars_invalid, '')
        # Switch to pinyin mode by pressing and releasing the right
        # shift key:
        ENGINE._do_process_key_event(
            IBus.KEY_Shift_R, 0,
            IBus.ModifierType.SHIFT_MASK)
        ENGINE._do_process_key_event(
            IBus.KEY_Shift_R, 0,
            IBus.ModifierType.SHIFT_MASK | IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(ENGINE.get_pinyin_mode(), True)
        self.assertEqual(ENGINE.mock_preedit_text, '工了以在')
        self.assertEqual(ENGINE.mock_committed_text, '')
        ENGINE._do_process_key_event(IBus.KEY_n, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_i, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_numbersign, 0, 0)
        self.assertEqual(ENGINE.mock_committed_text, '')
        self.assertEqual(ENGINE.mock_preedit_text, '工了你以在')
        ENGINE._do_process_key_event(
            IBus.KEY_Shift_L, 0,
            IBus.ModifierType.CONTROL_MASK | IBus.ModifierType.SHIFT_MASK)
        ENGINE._do_process_key_event(
            IBus.KEY_Shift_L, 0,
            IBus.ModifierType.CONTROL_MASK | IBus.ModifierType.SHIFT_MASK
            | IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(ENGINE.mock_preedit_text, '工了你以在')
        self.assertEqual(ENGINE.mock_committed_text, '')
        ENGINE._do_process_key_event(IBus.KEY_h, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_a, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_o, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '工了你好以在')
        self.assertEqual(ENGINE.mock_committed_text, '')
        ENGINE._do_process_key_event(IBus.KEY_numbersign, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '工了你好以在')
        self.assertEqual(ENGINE.mock_committed_text, '')
        ENGINE._do_process_key_event(
            IBus.KEY_Shift_L, 0,
            IBus.ModifierType.CONTROL_MASK | IBus.ModifierType.SHIFT_MASK)
        ENGINE._do_process_key_event(
            IBus.KEY_Shift_L, 0,
            IBus.ModifierType.CONTROL_MASK | IBus.ModifierType.SHIFT_MASK
            | IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(ENGINE.mock_preedit_text, '工了你好以在')
        self.assertEqual(ENGINE.mock_committed_text, '')
        # Move right two characters in the preëdit
        # (triggers a commit to preëdit):
        ENGINE._do_process_key_event(IBus.KEY_Right, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_Right, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '工了你好以在')
        self.assertEqual(ENGINE.mock_committed_text, '')
        self.assertEqual(ENGINE.mock_auxiliary_text, 'd dhf dhfd\t#: abwd')
        # commit the preëdit:
        ENGINE._do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, '工了你好以在')
        # Switch out of pinyin mode:
        ENGINE._do_process_key_event(
            IBus.KEY_Shift_R, 0,
            IBus.ModifierType.SHIFT_MASK)
        ENGINE._do_process_key_event(
            IBus.KEY_Shift_R, 0,
            IBus.ModifierType.SHIFT_MASK | IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(ENGINE.get_pinyin_mode(), False)
        # “abwd” shown on the right of the auxiliary text above shows the
        # newly defined shortcut for this phrase. Let’s  try to type
        # the same phrase again using the new shortcut:
        ENGINE._do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '工')
        ENGINE._do_process_key_event(IBus.KEY_b, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '节')
        ENGINE._do_process_key_event(IBus.KEY_w, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '工了你好以在')
        ENGINE._do_process_key_event(IBus.KEY_d, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '工了你好以在')
        # commit the preëdit:
        ENGINE._do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(ENGINE.mock_committed_text, '工了你好以在工了你好以在')

    def test_switch_to_direct_mode_and_commit_english(self) -> None:
        '''
        When in Chinese mode and the preedit is not empty, switching to
        direct mode should be possible and it should not discard the
        input but commit as English.

        See: https://github.com/kaio/ibus-table/issues/68
        '''
        assert ENGINE is not None
        ENGINE._do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '工')
        self.assertEqual(ENGINE.mock_committed_text, '')
        # Shift_L is the default key binding to switch to direct mode
        ENGINE._do_process_key_event(
            IBus.KEY_Shift_L, 0,
            IBus.ModifierType.SHIFT_MASK)
        ENGINE._do_process_key_event(
            IBus.KEY_Shift_L, 0,
            IBus.ModifierType.SHIFT_MASK
            | IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, 'a')

    def test_switch_between_table_and_pinyin_mode(self) -> None:
        '''
        The switch between table and pinyin mode should happen immediately
        even if the preedit is not empty
        '''
        assert ENGINE is not None
        ENGINE._do_process_key_event(IBus.KEY_a, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_i, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '东')
        self.assertEqual(ENGINE.mock_committed_text, '')
        # Shift_R is the default key binding to switch between table
        # and pinyin mode
        ENGINE._do_process_key_event(
            IBus.KEY_Shift_R, 0,
            IBus.ModifierType.SHIFT_MASK)
        ENGINE._do_process_key_event(
            IBus.KEY_Shift_R, 0,
            IBus.ModifierType.SHIFT_MASK
            | IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(ENGINE.mock_preedit_text, '爱')
        self.assertEqual(ENGINE.mock_committed_text, '')
        ENGINE._do_process_key_event(
            IBus.KEY_Shift_R, 0,
            IBus.ModifierType.SHIFT_MASK)
        ENGINE._do_process_key_event(
            IBus.KEY_Shift_R, 0,
            IBus.ModifierType.SHIFT_MASK
            | IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(ENGINE.mock_preedit_text, '东')
        self.assertEqual(ENGINE.mock_committed_text, '')
        ENGINE._do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, '东')

    def test_chinese_mode(self) -> None:
        assert ENGINE is not None
        ENGINE.set_chinese_mode(
            mode=0, update_gsettings=False) # show simplified Chinese only
        ENGINE._do_process_key_event(IBus.KEY_c, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_g, 0, 0)
        # All matching entries are loaded immediately now, not just
        # the first page, so these lists are longer than before.
        self.assertEqual(['对不起 fh 44400000 0',
                          '能不能 ce 21400000 0',
                          '又不是 jg 19000000 0',
                          '马来西亚 sg 14100000 0',
                          '参与者 ft 6390000 0',
                          '骊 m 5420000 0',
                          '骊 my 5420000 0',
                          '邓丽君 vt 4160000 0',
                          '对不对 cf 2720000 0',
                          '对不住 wy 2110000 0',
                          '难不成 dn 1990000 0',
                          '马不停蹄 wk 1470000 0',
                          '巴不得 tj 1420000 0',
                          '马列主义 yy 1140000 0',
                          '欢天喜地 ff 1100000 0',
                          '马王堆 fw 552000 0',
                          '马来亚 go 454000 0',
                          '马到成功 da 294000 0',
                          '参政党 ip 234000 0',
                          '巴甫洛夫 if 232000 0',
                          '骊歌 sk 137000 0',
                          '馷 mh 36500 0',
                          '駵 an 25800 0',
                          '驑 al 24300 0',
                          '驑 jl 24300 0',
                          '难于登天 wg 14700 0',
                          '䮥 kh 6060 0',
                          '䭶 jh 4230 0',
                          '䮋 qj 3670 0',
                          '䮯 qt 3540 0',
                          '䮊 xw 3530 0',
                          '䮆 if 3450 0',
                          '䮒 ey 3360 0',
                          '䮏 kg 3280 0',
                          '𩧩 t 0 0',
                          '𦤵 cf 0 0',
                          '𠫛 cu 0 0',
                          '𨓔 ep 0 0',
                          '𩤕 ey 0 0',
                          '𩤃 hg 0 0',
                          '𩤷 hh 0 0',
                          '𠝌 ij 0 0',
                          '𩣚 ik 0 0',
                          '𩢩 jg 0 0',
                          '𩣳 ji 0 0',
                          '𩣬 kc 0 0',
                          '𩦙 kd 0 0',
                          '𩦣 kh 0 0',
                          '𩨉 kj 0 0',
                          '𩤬 kk 0 0',
                          '𩧿 kl 0 0',
                          '𢁑 km 0 0',
                          '𩥹 kt 0 0',
                          '𩤳 mc 0 0',
                          '𩡸 mh 0 0',
                          '𠫧 mw 0 0',
                          '𠮔 mx 0 0',
                          '𩣪 va 0 0',
                          '𠚔 wb 0 0',
                          '𢚥 yn 0 0',
                          '𩢤 yy 0 0'],
                         ENGINE._lookup_table.mock_candidates,)
        ENGINE._do_process_key_event(IBus.KEY_BackSpace, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_BackSpace, 0, 0)
        self.assertEqual(ENGINE._lookup_table.mock_candidates, [])
        ENGINE.set_chinese_mode(
            mode=1, update_gsettings=False) # show traditional Chinese only
        ENGINE._do_process_key_event(IBus.KEY_c, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_g, 0, 0)
        self.assertEqual(['驪  0 0',
                          '馬 gy 99400000 0',
                          '馬 hy 99400000 0',
                          '对不起 fh 44400000 0',
                          '能不能 ce 21400000 0',
                          '又不是 jg 19000000 0',
                          '对不对 cf 2720000 0',
                          '对不住 wy 2110000 0',
                          '难不成 dn 1990000 0',
                          '巴不得 tj 1420000 0',
                          '欢天喜地 ff 1100000 0',
                          '驪 mx 283000 0',
                          '参政党 ip 234000 0',
                          '巴甫洛夫 if 232000 0',
                          '駷 ki 54200 0',
                          '馷 mh 36500 0',
                          '駵 an 25800 0',
                          '駓 ig 25600 0',
                          '駤 cf 24500 0',
                          '驑 al 24300 0',
                          '驑 jl 24300 0',
                          '駍 uh 24300 0',
                          '难于登天 wg 14700 0',
                          '䮠 kl 6390 0',
                          '䮥 kh 6060 0',
                          '䭶 jh 4230 0',
                          '䮋 qj 3670 0',
                          '䮯 qt 3540 0',
                          '䮊 xw 3530 0',
                          '䮆 if 3450 0',
                          '䮒 ey 3360 0',
                          '䮏 kg 3280 0',
                          '𩢀 bn 0 0',
                          '𦤵 cf 0 0',
                          '𠫛 cu 0 0',
                          '𨓔 ep 0 0',
                          '𩤕 ey 0 0',
                          '𩤃 hg 0 0',
                          '𩤷 hh 0 0',
                          '𠝌 ij 0 0',
                          '𩣚 ik 0 0',
                          '𩢩 jg 0 0',
                          '𩣳 ji 0 0',
                          '𩣬 kc 0 0',
                          '𩦙 kd 0 0',
                          '𩦣 kh 0 0',
                          '𩤲 kj 0 0',
                          '𩤬 kk 0 0',
                          '𢁑 km 0 0',
                          '𩢲 kq 0 0',
                          '𩧐 ks 0 0',
                          '𩥹 kt 0 0',
                          '𩥲 kw 0 0',
                          '𩤳 mc 0 0',
                          '𩡸 mh 0 0',
                          '𠫧 mw 0 0',
                          '𠮔 mx 0 0',
                          '𩢖 sy 0 0',
                          '𩣪 va 0 0',
                          '𠚔 wb 0 0',
                          '𢚥 yn 0 0',
                          '𩢤 yy 0 0'],
                         ENGINE._lookup_table.mock_candidates)
        ENGINE._do_process_key_event(IBus.KEY_BackSpace, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_BackSpace, 0, 0)
        self.assertEqual(ENGINE._lookup_table.mock_candidates, [])
        ENGINE.set_chinese_mode(
            mode=2, update_gsettings=False) # show simplified Chinese first
        ENGINE._do_process_key_event(IBus.KEY_c, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_g, 0, 0)
        self.assertEqual(['驪  0 0',
                          '对不起 fh 44400000 0',
                          '能不能 ce 21400000 0',
                          '又不是 jg 19000000 0',
                          '马来西亚 sg 14100000 0',
                          '参与者 ft 6390000 0',
                          '骊 m 5420000 0',
                          '骊 my 5420000 0',
                          '邓丽君 vt 4160000 0',
                          '对不对 cf 2720000 0',
                          '对不住 wy 2110000 0',
                          '难不成 dn 1990000 0',
                          '马不停蹄 wk 1470000 0',
                          '巴不得 tj 1420000 0',
                          '马列主义 yy 1140000 0',
                          '欢天喜地 ff 1100000 0',
                          '马王堆 fw 552000 0',
                          '马来亚 go 454000 0',
                          '马到成功 da 294000 0',
                          '参政党 ip 234000 0',
                          '巴甫洛夫 if 232000 0',
                          '骊歌 sk 137000 0',
                          '馷 mh 36500 0',
                          '駵 an 25800 0',
                          '驑 al 24300 0',
                          '驑 jl 24300 0',
                          '难于登天 wg 14700 0',
                          '䮥 kh 6060 0',
                          '䭶 jh 4230 0',
                          '䮋 qj 3670 0',
                          '䮯 qt 3540 0',
                          '䮊 xw 3530 0',
                          '䮆 if 3450 0',
                          '䮒 ey 3360 0',
                          '䮏 kg 3280 0',
                          '𩧩 t 0 0',
                          '𦤵 cf 0 0',
                          '𠫛 cu 0 0',
                          '𨓔 ep 0 0',
                          '𩤕 ey 0 0',
                          '𩤃 hg 0 0',
                          '𩤷 hh 0 0',
                          '𠝌 ij 0 0',
                          '𩣚 ik 0 0',
                          '𩢩 jg 0 0',
                          '𩣳 ji 0 0',
                          '𩣬 kc 0 0',
                          '𩦙 kd 0 0',
                          '𩦣 kh 0 0',
                          '𩨉 kj 0 0',
                          '𩤬 kk 0 0',
                          '𩧿 kl 0 0',
                          '𢁑 km 0 0',
                          '𩥹 kt 0 0',
                          '𩤳 mc 0 0',
                          '𩡸 mh 0 0',
                          '𠫧 mw 0 0',
                          '𠮔 mx 0 0',
                          '𩣪 va 0 0',
                          '𠚔 wb 0 0',
                          '𢚥 yn 0 0',
                          '𩢤 yy 0 0',
                          '馬 gy 99400000 0',
                          '馬 hy 99400000 0',
                          '驪 mx 283000 0',
                          '駷 ki 54200 0',
                          '駓 ig 25600 0',
                          '駤 cf 24500 0',
                          '駍 uh 24300 0',
                          '䮠 kl 6390 0',
                          '𩢀 bn 0 0',
                          '𩤲 kj 0 0',
                          '𩢲 kq 0 0',
                          '𩧐 ks 0 0',
                          '𩥲 kw 0 0',
                          '𩢖 sy 0 0'],
                         ENGINE._lookup_table.mock_candidates)
        ENGINE._do_process_key_event(IBus.KEY_BackSpace, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_BackSpace, 0, 0)
        self.assertEqual(ENGINE._lookup_table.mock_candidates, [])
        ENGINE.set_chinese_mode(
            mode=3, update_gsettings=False) # show traditional Chinese first
        ENGINE._do_process_key_event(IBus.KEY_c, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_g, 0, 0)
        self.assertEqual(['驪  0 0',
                          '馬 gy 99400000 0',
                          '馬 hy 99400000 0',
                          '对不起 fh 44400000 0',
                          '能不能 ce 21400000 0',
                          '又不是 jg 19000000 0',
                          '对不对 cf 2720000 0',
                          '对不住 wy 2110000 0',
                          '难不成 dn 1990000 0',
                          '巴不得 tj 1420000 0',
                          '欢天喜地 ff 1100000 0',
                          '驪 mx 283000 0',
                          '参政党 ip 234000 0',
                          '巴甫洛夫 if 232000 0',
                          '駷 ki 54200 0',
                          '馷 mh 36500 0',
                          '駵 an 25800 0',
                          '駓 ig 25600 0',
                          '駤 cf 24500 0',
                          '驑 al 24300 0',
                          '驑 jl 24300 0',
                          '駍 uh 24300 0',
                          '难于登天 wg 14700 0',
                          '䮠 kl 6390 0',
                          '䮥 kh 6060 0',
                          '䭶 jh 4230 0',
                          '䮋 qj 3670 0',
                          '䮯 qt 3540 0',
                          '䮊 xw 3530 0',
                          '䮆 if 3450 0',
                          '䮒 ey 3360 0',
                          '䮏 kg 3280 0',
                          '𩢀 bn 0 0',
                          '𦤵 cf 0 0',
                          '𠫛 cu 0 0',
                          '𨓔 ep 0 0',
                          '𩤕 ey 0 0',
                          '𩤃 hg 0 0',
                          '𩤷 hh 0 0',
                          '𠝌 ij 0 0',
                          '𩣚 ik 0 0',
                          '𩢩 jg 0 0',
                          '𩣳 ji 0 0',
                          '𩣬 kc 0 0',
                          '𩦙 kd 0 0',
                          '𩦣 kh 0 0',
                          '𩤲 kj 0 0',
                          '𩤬 kk 0 0',
                          '𢁑 km 0 0',
                          '𩢲 kq 0 0',
                          '𩧐 ks 0 0',
                          '𩥹 kt 0 0',
                          '𩥲 kw 0 0',
                          '𩤳 mc 0 0',
                          '𩡸 mh 0 0',
                          '𠫧 mw 0 0',
                          '𠮔 mx 0 0',
                          '𩢖 sy 0 0',
                          '𩣪 va 0 0',
                          '𠚔 wb 0 0',
                          '𢚥 yn 0 0',
                          '𩢤 yy 0 0',
                          '马来西亚 sg 14100000 0',
                          '参与者 ft 6390000 0',
                          '骊 m 5420000 0',
                          '骊 my 5420000 0',
                          '邓丽君 vt 4160000 0',
                          '马不停蹄 wk 1470000 0',
                          '马列主义 yy 1140000 0',
                          '马王堆 fw 552000 0',
                          '马来亚 go 454000 0',
                          '马到成功 da 294000 0',
                          '骊歌 sk 137000 0',
                          '𩧩 t 0 0',
                          '𩨉 kj 0 0',
                          '𩧿 kl 0 0'],
                         ENGINE._lookup_table.mock_candidates)
        ENGINE._do_process_key_event(IBus.KEY_BackSpace, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_BackSpace, 0, 0)
        self.assertEqual(ENGINE._lookup_table.mock_candidates, [])
        ENGINE.set_chinese_mode(
            mode=4, update_gsettings=False) # show all characters
        ENGINE._do_process_key_event(IBus.KEY_c, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_g, 0, 0)
        self.assertEqual(['驪  0 0',
                          '馬 gy 99400000 0',
                          '馬 hy 99400000 0',
                          '对不起 fh 44400000 0',
                          '能不能 ce 21400000 0',
                          '又不是 jg 19000000 0',
                          '马来西亚 sg 14100000 0',
                          '参与者 ft 6390000 0',
                          '骊 m 5420000 0',
                          '骊 my 5420000 0',
                          '邓丽君 vt 4160000 0',
                          '对不对 cf 2720000 0',
                          '对不住 wy 2110000 0',
                          '难不成 dn 1990000 0',
                          '马不停蹄 wk 1470000 0',
                          '巴不得 tj 1420000 0',
                          '马列主义 yy 1140000 0',
                          '欢天喜地 ff 1100000 0',
                          '马王堆 fw 552000 0',
                          '马来亚 go 454000 0',
                          '马到成功 da 294000 0',
                          '驪 mx 283000 0',
                          '参政党 ip 234000 0',
                          '巴甫洛夫 if 232000 0',
                          '骊歌 sk 137000 0',
                          '駷 ki 54200 0',
                          '馷 mh 36500 0',
                          '駵 an 25800 0',
                          '駓 ig 25600 0',
                          '駤 cf 24500 0',
                          '驑 al 24300 0',
                          '驑 jl 24300 0',
                          '駍 uh 24300 0',
                          '难于登天 wg 14700 0',
                          '䮠 kl 6390 0',
                          '䮥 kh 6060 0',
                          '䭶 jh 4230 0',
                          '䮋 qj 3670 0',
                          '䮯 qt 3540 0',
                          '䮊 xw 3530 0',
                          '䮆 if 3450 0',
                          '䮒 ey 3360 0',
                          '䮏 kg 3280 0',
                          '𩧩 t 0 0',
                          '𩢀 bn 0 0',
                          '𦤵 cf 0 0',
                          '𠫛 cu 0 0',
                          '𨓔 ep 0 0',
                          '𩤕 ey 0 0',
                          '𩤃 hg 0 0',
                          '𩤷 hh 0 0',
                          '𠝌 ij 0 0',
                          '𩣚 ik 0 0',
                          '𩢩 jg 0 0',
                          '𩣳 ji 0 0',
                          '𩣬 kc 0 0',
                          '𩦙 kd 0 0',
                          '𩦣 kh 0 0',
                          '𩤲 kj 0 0',
                          '𩨉 kj 0 0',
                          '𩤬 kk 0 0',
                          '𩧿 kl 0 0',
                          '𢁑 km 0 0',
                          '𩢲 kq 0 0',
                          '𩧐 ks 0 0',
                          '𩥹 kt 0 0',
                          '𩥲 kw 0 0',
                          '𩤳 mc 0 0',
                          '𩡸 mh 0 0',
                          '𠫧 mw 0 0',
                          '𠮔 mx 0 0',
                          '𩢖 sy 0 0',
                          '𩣪 va 0 0',
                          '𠚔 wb 0 0',
                          '𢚥 yn 0 0',
                          '𩢤 yy 0 0'],
                         ENGINE._lookup_table.mock_candidates)
        ENGINE._do_process_key_event(IBus.KEY_BackSpace, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_BackSpace, 0, 0)
        self.assertEqual(ENGINE._lookup_table.mock_candidates, [])

class Stroke5TestCase(unittest.TestCase):
    '''Test cases for the stroke5 table'''
    def setUp(self) -> None:
        engine_name = 'stroke5'
        if not set_up(engine_name):
            self.skipTest(f'Could not setup “{engine_name}”, skipping test.')

    def tearDown(self) -> None:
        tear_down()

    def test_dummy(self) -> None:
        self.assertEqual(True, True)

    def test_single_char_commit_with_space(self) -> None:
        assert ENGINE is not None
        ENGINE._do_process_key_event(IBus.KEY_comma, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_slash, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_n, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_m, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_m, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(ENGINE.mock_committed_text, '的')

class TelexTestCase(unittest.TestCase):
    '''Test cases for the telex table'''
    def setUp(self) -> None:
        engine_name = 'telex'
        if not set_up(engine_name):
            self.skipTest(f'Could not setup “{engine_name}”, skipping test.')

    def tearDown(self) -> None:
        tear_down()

    def test_dummy(self) -> None:
        self.assertEqual(True, True)

    def test_telex(self) -> None:
        assert ENGINE is not None
        ENGINE._do_process_key_event(IBus.KEY_o, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, 'o')
        self.assertEqual(ENGINE.mock_committed_text, '')
        ENGINE._do_process_key_event(IBus.KEY_backslash, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, 'o')
        ENGINE._do_process_key_event(IBus.KEY_o, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_f, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, 'oò')
        ENGINE._do_process_key_event(IBus.KEY_o, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_o, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, 'ô')
        self.assertEqual(ENGINE.mock_committed_text, 'oò')
        ENGINE._do_process_key_event(IBus.KEY_backslash, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, 'oòô')
        ENGINE._do_process_key_event(IBus.KEY_o, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_o, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, 'ô')
        self.assertEqual(ENGINE.mock_committed_text, 'oòô')
        ENGINE._do_process_key_event(IBus.KEY_backslash, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, 'oòôô')
        ENGINE._do_process_key_event(IBus.KEY_o, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_o, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, 'ô')
        self.assertEqual(ENGINE.mock_committed_text, 'oòôô')
        ENGINE._do_process_key_event(IBus.KEY_j, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, 'oòôôộ')

class TranslitTestCase(unittest.TestCase):
    '''Test cases for the translit table'''
    def setUp(self) -> None:
        engine_name ='translit'
        if not set_up(engine_name):
            self.skipTest(f'Could not setup “{engine_name}”, skipping test.')

    def tearDown(self) -> None:
        tear_down()

    def test_dummy(self) -> None:
        self.assertEqual(True, True)

    def test_sh_multiple_match(self) -> None:
        assert ENGINE is not None
        ENGINE._do_process_key_event(IBus.KEY_s, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, 'с')
        ENGINE._do_process_key_event(IBus.KEY_h, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, 'ш')
        ENGINE._do_process_key_event(IBus.KEY_s, 0, 0)
        self.assertEqual(ENGINE.mock_committed_text, 'ш')
        self.assertEqual(ENGINE.mock_preedit_text, 'с')
        ENGINE._do_process_key_event(IBus.KEY_h, 0, 0)
        self.assertEqual(ENGINE.mock_committed_text, 'ш')
        self.assertEqual(ENGINE.mock_preedit_text, 'ш')
        ENGINE._do_process_key_event(IBus.KEY_h, 0, 0)
        self.assertEqual(ENGINE.mock_committed_text, 'шщ')
        self.assertEqual(ENGINE.mock_preedit_text, '')
        ENGINE._do_process_key_event(IBus.KEY_s, 0, 0)
        self.assertEqual(ENGINE.mock_committed_text, 'шщ')
        self.assertEqual(ENGINE.mock_preedit_text, 'с')
        ENGINE._do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(ENGINE.mock_committed_text, 'шщс ')

    def test_sh_multiple_match_slavic(self) -> None:
        assert ENGINE is not None
        ENGINE._do_process_key_event(IBus.KEY_scaron, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, 'ш')
        self.assertEqual(ENGINE.mock_committed_text, '')
        ENGINE._do_process_key_event(IBus.KEY_h, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, 'щ')
        ENGINE._do_process_key_event(IBus.KEY_scaron, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, 'ш')
        self.assertEqual(ENGINE.mock_committed_text, 'щ')
        ENGINE._do_process_key_event(IBus.KEY_ccaron, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, 'щщ')

class Cangjie5TestCase(unittest.TestCase):
    '''Test cases for the cangjie5 table'''
    def setUp(self) -> None:
        engine_name = 'cangjie5'
        if not set_up(engine_name):
            self.skipTest(f'Could not setup “{engine_name}”, skipping test.')

    def tearDown(self) -> None:
        tear_down()

    def test_dummy(self) -> None:
        self.assertEqual(True, True)

    def test_single_char_commit_with_space(self) -> None:
        assert ENGINE is not None
        ENGINE._do_process_key_event(IBus.KEY_a, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(ENGINE.mock_committed_text, '日')

    def test_type_one_char_and_check_auxiliary(self) -> None:
        if not require_serial_number(20261123):
            self.skipTest('serial_number too small')
        assert ENGINE is not None
        ENGINE._do_process_key_event(IBus.KEY_d, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '木')
        self.assertEqual(ENGINE._lookup_table.mock_candidates[6],
                         '寸 戈 1000 0')
        ENGINE._do_process_key_event(IBus.KEY_v, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_i, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_i, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '機')
        self.assertEqual(ENGINE.mock_auxiliary_text, '木女戈戈 (1 / 1)')
        self.assertEqual(ENGINE._lookup_table.mock_candidates,
                         ['機  1000 0'])
        ENGINE._do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(ENGINE.mock_committed_text, '機')

    def test_dynamic_adjust(self) -> None:
        if not require_serial_number(20220111):
            self.skipTest('serial_number too small')
        assert ENGINE is not None
        ENGINE.set_dynamic_adjust(False)
        ENGINE._do_process_key_event(IBus.KEY_i, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_r, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_p, 0, 0)
        self.assertEqual('感', ENGINE.mock_preedit_text)
        # Big5 code of 怠 is ABE5 (see
        # https://www.unicode.org/cgi-bin/GetUnihanData.pl?codepoint=%E6%84%9F)
        # Big5 code of 感 is B750 (see
        # https://www.unicode.org/cgi-bin/GetUnihanData.pl?codepoint=%E6%80%A0)
        #
        # In the improved cangjie5 table, 感 has higher priority now.
        self.assertEqual(
            ['感  1000 0',
             '怠  900 0'],
            ENGINE._lookup_table.mock_candidates)
        ENGINE._do_process_key_event(IBus.KEY_2, 0, 0)
        self.assertEqual(
            [],
            ENGINE._lookup_table.mock_candidates)
        self.assertEqual('', ENGINE.mock_preedit_text)
        self.assertEqual('怠', ENGINE.mock_committed_text)
        # repeat the same input, result should be the same
        # because dynamic adjust is False:
        ENGINE._do_process_key_event(IBus.KEY_i, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_r, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_p, 0, 0)
        self.assertEqual('感', ENGINE.mock_preedit_text)
        self.assertEqual(
            ['感  1000 0',
             '怠  900 0'],
            ENGINE._lookup_table.mock_candidates)
        ENGINE._do_process_key_event(IBus.KEY_2, 0, 0)
        self.assertEqual(
            [],
            ENGINE._lookup_table.mock_candidates)
        self.assertEqual('', ENGINE.mock_preedit_text)
        self.assertEqual('怠怠', ENGINE.mock_committed_text)
        # Now set dynamic adjust to True:
        ENGINE.set_dynamic_adjust(True)
        # repeat the same input, result should still be the same
        # because no dynamic adjustment has happened yet:
        ENGINE._do_process_key_event(IBus.KEY_i, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_r, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_p, 0, 0)
        self.assertEqual('感', ENGINE.mock_preedit_text)
        self.assertEqual(
            ['感  1000 0',
             '怠  900 0'],
            ENGINE._lookup_table.mock_candidates)
        ENGINE._do_process_key_event(IBus.KEY_2, 0, 0)
        self.assertEqual(
            [],
            ENGINE._lookup_table.mock_candidates)
        self.assertEqual('', ENGINE.mock_preedit_text)
        self.assertEqual('怠怠怠', ENGINE.mock_committed_text)
        # Try once again, now 怠 should be preferred because
        # 怠 has been selected once while dynamic adjustment was used
        # whereas 感 has not been selected:
        ENGINE._do_process_key_event(IBus.KEY_i, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_r, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_p, 0, 0)
        self.assertEqual('怠', ENGINE.mock_preedit_text)
        self.assertEqual(
            ['怠  900 1',
             '感  1000 0'],
            ENGINE._lookup_table.mock_candidates)
        ENGINE._do_process_key_event(IBus.KEY_1, 0, 0)
        self.assertEqual(
            [],
            ENGINE._lookup_table.mock_candidates)
        self.assertEqual('', ENGINE.mock_preedit_text)
        self.assertEqual('怠怠怠怠', ENGINE.mock_committed_text)
        # Try once again with dynamic adjust, now 怠 should have
        # user count 2:
        ENGINE._do_process_key_event(IBus.KEY_i, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_r, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_p, 0, 0)
        self.assertEqual('怠', ENGINE.mock_preedit_text)
        self.assertEqual(
            ['怠  900 2',
             '感  1000 0'],
            ENGINE._lookup_table.mock_candidates)
        ENGINE._do_process_key_event(IBus.KEY_1, 0, 0)
        self.assertEqual(
            [],
            ENGINE._lookup_table.mock_candidates)
        self.assertEqual('', ENGINE.mock_preedit_text)
        self.assertEqual('怠怠怠怠怠', ENGINE.mock_committed_text)
        # 怠 should have user count 3 now. This should be remembered
        # in the user data base, i.e. if we switch off dynamic adjust
        # and later switch it back on, the previous user count should
        # still be there.
        #
        # Switch dynamic adjust off again:
        ENGINE.set_dynamic_adjust(False)
        # And try again, now 感 should be preferred again
        # because of its higher weight in the cangjie5 table and the user counts
        # displayed should be 0:
        ENGINE._do_process_key_event(IBus.KEY_i, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_r, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_p, 0, 0)
        self.assertEqual('感', ENGINE.mock_preedit_text)
        self.assertEqual(
            ['感  1000 0',
             '怠  900 0'],
            ENGINE._lookup_table.mock_candidates)
        ENGINE._do_process_key_event(IBus.KEY_2, 0, 0)
        self.assertEqual(
            [],
            ENGINE._lookup_table.mock_candidates)
        self.assertEqual('', ENGINE.mock_preedit_text)
        self.assertEqual('怠怠怠怠怠怠', ENGINE.mock_committed_text)
        # Switch dynamic adjust on again:
        ENGINE.set_dynamic_adjust(True)
        # Try once again with dynamic adjust, now 感 should be preferred
        # again and have user count 3:
        ENGINE._do_process_key_event(IBus.KEY_i, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_r, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_p, 0, 0)
        self.assertEqual('怠', ENGINE.mock_preedit_text)
        self.assertEqual(
            ['怠  900 3',
             '感  1000 0'],
            ENGINE._lookup_table.mock_candidates)
        ENGINE._do_process_key_event(IBus.KEY_1, 0, 0)
        self.assertEqual(
            [],
            ENGINE._lookup_table.mock_candidates)
        self.assertEqual('', ENGINE.mock_preedit_text)
        self.assertEqual('怠怠怠怠怠怠怠', ENGINE.mock_committed_text)

class QuickClassicTestCase(unittest.TestCase):
    '''Test cases for the quick-classic table'''
    def setUp(self) -> None:
        engine_name = 'quick-classic'
        if not set_up(engine_name):
            self.skipTest(f'Could not setup “{engine_name}”, skipping test.')

    def tearDown(self) -> None:
        tear_down()

    def test_dummy(self) -> None:
        self.assertEqual(True, True)

    def test_lookup_table_total_shown_immediately(self) -> None:
        '''
        Regression test: typing a code with more candidates than fit
        on one page used to only fill one page of the lookup table at
        a time, so the “x/y” page indicator’s “y” grew by one page
        size on every page instead of showing the real total right
        away (e.g. 1/9, 10/18, ..., ending on the real total only on
        the last page).
        '''
        assert ENGINE is not None
        # “of”: 人 (code “o”) + 火 (code “f”), 65 candidates in
        # quick-classic, more than the page size of 9.
        ENGINE._do_process_key_event(IBus.KEY_o, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_f, 0, 0)
        self.assertEqual(65, len(ENGINE._candidates))
        self.assertIn('(1 / 65)', ENGINE.mock_auxiliary_text)
        self.assertEqual(9, ENGINE._lookup_table.get_page_size())
        # All 65 candidates should already be in the lookup table,
        # not just the first page of 9.
        self.assertEqual(
            65, len(ENGINE._lookup_table.mock_candidates))

class IpaXSampaTestCase(unittest.TestCase):
    '''Test cases for the ipa-x-sampa table'''
    def setUp(self) -> None:
        engine_name = 'ipa-x-sampa'
        if not set_up(engine_name):
            self.skipTest(f'Could not setup “{engine_name}”, skipping test.')

    def tearDown(self) -> None:
        tear_down()

    def test_dummy(self) -> None:
        self.assertEqual(True, True)

    def test_single_char_commit_with_space(self) -> None:
        assert ENGINE is not None
        ENGINE._do_process_key_event(IBus.KEY_at, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(ENGINE.mock_committed_text, 'ə ')

    def test_single_char_commit_with_f3(self) -> None:
        assert ENGINE is not None
        ENGINE._do_process_key_event(IBus.KEY_at, 0, 0)
        self.assertEqual(ENGINE._lookup_table.mock_candidates,
                         ['ə  0 0', 'ɘ \\ 0 0', 'ɚ ` 0 0'])
        ENGINE._do_process_key_event(IBus.KEY_F3, 0, 0)
        self.assertEqual(ENGINE.mock_committed_text, 'ɚ')

class LatexTestCase(unittest.TestCase):
    '''Test cases for the latex table'''
    def setUp(self) -> None:
        engine_name = 'latex'
        if not set_up(engine_name):
            self.skipTest(f'Could not setup “{engine_name}”, skipping test.')

    def tearDown(self) -> None:
        tear_down()

    def test_dummy(self) -> None:
        self.assertEqual(True, True)

    def test_single_char_commit_with_space(self) -> None:
        assert ENGINE is not None
        ENGINE._do_process_key_event(IBus.KEY_backslash, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_a, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_l, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_p, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_h, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, 'α')
        self.assertEqual(ENGINE.mock_committed_text, '')
        ENGINE._do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, 'α')

    def test_single_char_commit_with_space_fraktur(self) -> None:
        # needs ibus-table-others-1.3.10 which adds
        # most of Unicode 9.0 block Mathematical Alphanumeric Symbols
        assert ENGINE is not None
        ENGINE._do_process_key_event(IBus.KEY_backslash, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_m, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_a, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_t, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_h, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_f, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_r, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_a, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_k, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_F, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(ENGINE.mock_committed_text, '𝔉')

    def test_commit_invalid_mode(self) -> None:
        assert ENGINE is not None
        self.assertEqual(ENGINE.get_commit_invalid_mode(), 0)
        ENGINE._do_process_key_event(IBus.KEY_backslash, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_a, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_l, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_p, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_h, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, 'α')
        self.assertEqual(ENGINE.mock_committed_text, '')
        ENGINE._do_process_key_event(IBus.KEY_exclam, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, 'α!')
        ENGINE.set_commit_invalid_mode(1, update_gsettings=False)
        self.assertEqual(ENGINE.get_commit_invalid_mode(), 1)
        ENGINE._do_process_key_event(IBus.KEY_backslash, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_a, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_l, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_p, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_h, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, 'α')
        self.assertEqual(ENGINE.mock_committed_text, 'α!')
        ENGINE._do_process_key_event(IBus.KEY_exclam, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, 'α!\\alpha!')

    def test_toggle_input_mode_on_off(self) -> None:
        assert ENGINE is not None
        ENGINE._do_process_key_event(IBus.KEY_backslash, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_a, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_l, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_p, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_h, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, 'α')
        self.assertEqual(ENGINE.mock_committed_text, '')
        ENGINE._do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, 'α')
        ENGINE._do_process_key_event(IBus.KEY_Shift_L, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_Shift_L, 0, IBus.ModifierType.RELEASE_MASK)
        ENGINE._do_process_key_event(IBus.KEY_backslash, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_a, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_l, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_p, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_h, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, 'α\\alpha')
        ENGINE._do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(ENGINE.mock_preedit_text, '')
        self.assertEqual(ENGINE.mock_committed_text, 'α\\alpha ')

    def test_single_char_commit_with_f3(self) -> None:
        assert ENGINE is not None
        # The latex.txt table in ibus-table-others-1.3.12 has
        # SELECT_KEYS = F1,F2,F3,F4,F5,F6,F7,F8,F9,F10
        # the older version in ibus-table-others-1.3.11
        # has SELECT_KEYS = F1,F2,F3,F4,F5,F6,F7,F8,F9
        # To make this test work for both versions, set the page size to 9:
        ENGINE.set_page_size(9)
        ENGINE._do_process_key_event(IBus.KEY_backslash, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_b, 0, 0)
        self.assertEqual(ENGINE._lookup_table.mock_candidates[0:9],
                         ['¯ ar 0 0',
                          '⊥ ot 0 0',
                          'β eta 0 0',
                          'ℶ eth 0 0',
                          '⋂ igcap 0 0',
                          '⋃ igcup 0 0',
                          '⋁ igvee 0 0',
                          '⋈ owtie 0 0',
                          '⊡ oxdot 0 0'])
        ENGINE._do_process_key_event(IBus.KEY_F3, 0, 0)
        self.assertEqual(ENGINE.mock_committed_text, 'β')
        ENGINE._do_process_key_event(IBus.KEY_backslash, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_b, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_Page_Down, 0, 0)
        self.assertEqual(ENGINE._lookup_table.mock_candidates[0:18],
                         ['β eta 0 1', # user freq for β increased to 1
                          '¯ ar 0 0',
                          '⊥ ot 0 0',
                          'ℶ eth 0 0',
                          '⋂ igcap 0 0',
                          '⋃ igcup 0 0',
                          '⋁ igvee 0 0',
                          '⋈ owtie 0 0',
                          '⊡ oxdot 0 0',
                          '• ullet 0 0',
                          '∙ ullet 0 0',
                          '≏ umpeq 0 0',
                          '∽ acksim 0 0',
                          '∵ ecause 0 0',
                          '≬ etween 0 0',
                          '⊞ oxplus 0 0',
                          '⊼ arwedge 0 0',
                          '⋀ igwedge 0 0'])
        self.assertEqual(ENGINE._lookup_table.get_cursor_pos(), 9)
        ENGINE._do_process_key_event(IBus.KEY_Down, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_Down, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_Down, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_Down, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_Down, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_Down, 0, 0)
        self.assertEqual(ENGINE._lookup_table.get_cursor_pos(), 15)
        self.assertEqual(ENGINE._lookup_table.mock_candidates[0:18],
                         ['β eta 0 1', # user freq for β increased to 1
                          '¯ ar 0 0',
                          '⊥ ot 0 0',
                          'ℶ eth 0 0',
                          '⋂ igcap 0 0',
                          '⋃ igcup 0 0',
                          '⋁ igvee 0 0',
                          '⋈ owtie 0 0',
                          '⊡ oxdot 0 0',
                          '• ullet 0 0',
                          '∙ ullet 0 0',
                          '≏ umpeq 0 0',
                          '∽ acksim 0 0',
                          '∵ ecause 0 0',
                          '≬ etween 0 0',
                          '⊞ oxplus 0 0',
                          '⊼ arwedge 0 0',
                          '⋀ igwedge 0 0'])
        ENGINE._do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(ENGINE.mock_committed_text, 'β⊞')
        ENGINE._do_process_key_event(IBus.KEY_backslash, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_b, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_Page_Down, 0, 0)
        self.assertEqual(ENGINE._lookup_table.mock_candidates[0:18],
                         ['β eta 0 1', # user freq for β increased to 1
                          '⊞ oxplus 0 1', # user freq for ⊞ increased to 1
                          '¯ ar 0 0',
                          '⊥ ot 0 0',
                          'ℶ eth 0 0',
                          '⋂ igcap 0 0',
                          '⋃ igcup 0 0',
                          '⋁ igvee 0 0',
                          '⋈ owtie 0 0',
                          '⊡ oxdot 0 0',
                          '• ullet 0 0',
                          '∙ ullet 0 0',
                          '≏ umpeq 0 0',
                          '∽ acksim 0 0',
                          '∵ ecause 0 0',
                          '≬ etween 0 0',
                          '⊼ arwedge 0 0',
                          '⋀ igwedge 0 0'])
        self.assertEqual(ENGINE._lookup_table.get_cursor_pos(), 9)
        ENGINE._do_process_key_event(IBus.KEY_Down, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_Down, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_Down, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_Down, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_Down, 0, 0)
        ENGINE._do_process_key_event(IBus.KEY_Down, 0, 0)
        self.assertEqual(ENGINE._lookup_table.get_cursor_pos(), 15)
        ENGINE._do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(ENGINE.mock_committed_text, 'β⊞≬')

class SelectWordsEscapeIndexTestCase(unittest.TestCase):
    '''
    Regression tests for the select_words() / create_indexes() fix: an
    ESCAPE clause unconditionally added to the LIKE query disabled
    SQLite's index-based range-scan optimization, and
    create_indexes()/drop_indexes() were a deliberate no-op even though
    their call sites already existed. Builds its own throwaway sqlite
    file so the real installed system databases are never touched.
    '''
    def setUp(self) -> None:
        '''Build a small throwaway system database with rows crafted to
        exercise plain prefixes, both wildcard characters, and literal
        occurrences of %, _, and the escape character.'''
        self._tmpdir = tempfile.mkdtemp(prefix='ibus_table_escape_index_test_')
        db_path = os.path.join(self._tmpdir, 'test_sys.db')
        con = sqlite3.connect(db_path)
        con.execute('CREATE TABLE ime (attr TEXT, val TEXT)')
        con.executemany('INSERT INTO ime VALUES (?,?)', [
            ('max_key_length', '4'), ('serial_number', '1'),
            ('languages', 'zh_CN'), ('user_can_define_phrase', 'false'),
            ('rules', ''), ('name', 'escapeindextest'),
            ('start_chars', 'abcdefghijklmnopqrstuvwxyz%_#')])
        con.execute('CREATE TABLE phrases (id INTEGER PRIMARY KEY, tabkeys TEXT,'
                    ' phrase TEXT, freq INTEGER, user_freq INTEGER)')
        con.executemany(
            'INSERT INTO phrases (tabkeys,phrase,freq,user_freq) VALUES (?,?,?,?)',
            [('ab', 'A', 900, 0), ('abc', 'B', 800, 0), ('abcd', 'C', 700, 0),
             ('axc', 'D', 600, 0), ('a%c', 'E', 500, 0), ('a_c', 'F', 400, 0),
             ('a#c', 'G', 300, 0)])
        con.commit()
        con.close()
        self.db = tabsqlitedb.TabSqliteDb(
            filename=db_path, user_db=':memory:')
        self._captured: list[str] = []
        self._real_db = self.db.db
        captured = self._captured
        real_db = self._real_db
        class Spy: # pylint: disable=missing-class-docstring
            def execute(self, # pylint: disable=missing-function-docstring,no-self-use
                        sql: str,
                        *args: Any) -> sqlite3.Cursor:
                captured.append(' '.join(sql.split()))
                return real_db.execute(sql, *args)
            def __getattr__(self, name: str) -> Any:
                return getattr(real_db, name)
        self.db.db = Spy() # type: ignore

    def tearDown(self) -> None:
        '''Remove the throwaway database directory created in setUp().'''
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _indexes(self) -> list[str]:
        '''Return the names of all indexes currently defined on the
        throwaway database, bypassing the Spy to query the real
        connection directly.'''
        return [r[0] for r in self._real_db.execute(
            "SELECT name FROM sqlite_master WHERE type='index'").fetchall()]

    def test_escape_omitted_for_plain_prefix(self) -> None:
        '''A plain alphabetic prefix contains no escape sequences, so the
        ESCAPE clause must not be emitted (it would otherwise block the
        index-based range scan for no reason).'''
        self._captured.clear()
        self.db.select_words(tabkeys='ab', auto_wildcard=True)
        self.assertNotIn('ESCAPE', self._captured[0])

    def test_escape_included_for_literal_percent(self) -> None:
        '''A literal “%” in the typed keys must still be escaped, and the
        ESCAPE clause must still be emitted for that query.'''
        self._captured.clear()
        self.db.select_words(tabkeys='a%c')
        self.assertIn('ESCAPE', self._captured[0])

    def test_escape_included_for_literal_underscore(self) -> None:
        '''A literal “_” in the typed keys must still be escaped, and the
        ESCAPE clause must still be emitted for that query.'''
        self._captured.clear()
        self.db.select_words(tabkeys='a_c')
        self.assertIn('ESCAPE', self._captured[0])

    def test_create_indexes_actually_creates_index(self) -> None:
        '''create_indexes() used to be a no-op; it must now actually add
        the tabkeys index to the target database.'''
        self.assertNotIn('phrases_tabkeys_index', self._indexes())
        self.db.create_indexes('main')
        self.assertIn('phrases_tabkeys_index', self._indexes())

    def test_drop_indexes_actually_drops_index(self) -> None:
        '''drop_indexes() used to be a no-op; it must now actually remove
        the tabkeys index it created.'''
        self.db.create_indexes('main')
        self.assertIn('phrases_tabkeys_index', self._indexes())
        self.db.drop_indexes('main')
        self.assertNotIn('phrases_tabkeys_index', self._indexes())

    def test_query_plan_uses_index_after_create_indexes(self) -> None:
        '''Once the index exists and no ESCAPE clause is emitted, SQLite's
        query plan must switch from a full table scan to an index
        search.'''
        self.db.create_indexes('main')
        self._captured.clear()
        self.db.select_words(tabkeys='ab', auto_wildcard=True)
        sql = self._captured[0]
        plan = '; '.join(r[-1] for r in self._real_db.execute(
            'EXPLAIN QUERY PLAN ' + sql, {'tabkeys': 'ab%'}).fetchall())
        self.assertIn('USING INDEX', plan)

    def test_results_identical_with_and_without_index(self) -> None:
        '''The whole point of the fix is a faster query plan, not
        different results: the candidate list for the same tabkeys must
        be byte-identical whether or not the index exists.'''
        before = list(self.db.select_words(tabkeys='a', auto_wildcard=True))
        self.db.create_indexes('main')
        after = list(self.db.select_words(tabkeys='a', auto_wildcard=True))
        self.assertEqual(before, after)

    def test_drop_indexes_then_optimize_compacts_database(self) -> None:
        '''DROP INDEX only frees pages onto SQLite's internal freelist --
        the file itself does not shrink until something VACUUMs it.
        tabcreatedb.py's --no-create-index path must run
        optimize_database() (which VACUUMs) after drop_indexes(), not
        only before, or a distributed database keeps the index-sized
        allocation despite ending up with no index.'''
        self.db.create_tables('main')
        self._real_db.executemany(
            'INSERT INTO phrases (tabkeys, phrase, freq, user_freq) '
            'VALUES (?, ?, ?, 0)',
            [(f'zz{i:04d}', f'P{i}', 1) for i in range(2000)])
        self._real_db.commit()
        self.db.create_indexes('main')
        self._real_db.execute('VACUUM')
        with_index_pages = self._real_db.execute(
            'PRAGMA page_count').fetchone()[0]
        self.db.drop_indexes('main')
        self.db.optimize_database()
        without_index_pages = self._real_db.execute(
            'PRAGMA page_count').fetchone()[0]
        self.assertLess(without_index_pages, with_index_pages)

if __name__ == '__main__':
    LOG_HANDLER = logging.StreamHandler(stream=sys.stderr)
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.addHandler(LOG_HANDLER)
    unittest.main()
