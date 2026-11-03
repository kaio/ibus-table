# vim:et sts=4 sw=4
#
# ibus-table - The Tables engine for IBus
#
# Copyright (c) 2008-2009 Yu Yuwei <acevery@gmail.com>
# Copyright (c) 2009-2014 Caius "kaio" CHANCE <me@kaio.net>
# Copyright (c) 2012-2022 Mike FABIAN <mfabian@redhat.com>
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
# along with this library.  If not, see <http://www.gnu.org/licenses/>
'''
Utility functions used in ibus-table
'''

from typing import Any
from typing import Optional
from typing import cast
from enum import Enum, IntFlag
# pylint: disable=wrong-import-position
import sys
import os
import re
import logging
import gettext
from gi import require_version
require_version('Gio', '2.0')
from gi.repository import Gio  # type: ignore[attr-defined]  # ty: ignore[unresolved-import]
require_version('GLib', '2.0')
from gi.repository import GLib  # type: ignore[attr-defined]  # ty: ignore[unresolved-import]
require_version('IBus', '1.0')
from gi.repository import IBus
from it_gtk import Gdk, Gtk, GTK_MAJOR, GTK_VERSION
# pylint: enable=wrong-import-position

import version
import tabsqlitedb

LOGGER = logging.getLogger('ibus-table')

DOMAINNAME = 'ibus-table'

def _(text: str) -> str:
    '''Gettext translation function.'''
    return gettext.dgettext(DOMAINNAME, text)

def N_(text: str) -> str: # pylint: disable=invalid-name
    '''Mark string for translation without actually translating.

    Used by gettext tools to extract strings that need translation.
    '''
    return text

# When matching keybindings, only the bits in the following mask are
# considered for key.state:
KEYBINDING_STATE_MASK = (
    IBus.ModifierType.MODIFIER_MASK  # pylint: disable=no-member
    & ~IBus.ModifierType.LOCK_MASK # Caps Lock
    & ~IBus.ModifierType.MOD2_MASK # Num Lock
    & ~IBus.ModifierType.MOD3_MASK # Scroll Lock
)

def variant_to_value(variant: GLib.Variant) -> Any:
    '''
    Convert a GLib variant to a value
    '''
    if variant is None:
        return None
    if not isinstance(variant, GLib.Variant):
        LOGGER.info('not a GLib.Variant')
        return variant
    type_string = variant.get_type_string()
    if type_string == 's':
        return variant.get_string()
    if type_string == 'i':
        return variant.get_int32()
    if type_string == 'u':
        return variant.get_uint32()
    if type_string == 'x':
        return variant.get_int64()
    if type_string == 't':
        return variant.get_uint64()
    if type_string == 'd':
        return variant.get_double()
    if type_string == 'b':
        return variant.get_boolean()
    if type_string == 'v':
        return variant.unpack()
    if type_string and type_string[0] == 'a':
        return variant.unpack()
    LOGGER.error('unknown variant type: %s', type_string)
    return variant

def color_string_to_argb(color_string: str) -> int:
    '''
    Converts a color string to a 32bit  ARGB value

    :param color_string: The color to convert to 32bit ARGB
                         Can be expressed in the following ways:
                             - Standard name from the X11 rgb.txt
                             - Hex value: “#rgb”, “#rrggbb”, “#rrrgggbbb”
                                          or ”#rrrrggggbbbb”
                             - RGB color: “rgb(r,g,b)”
                             - RGBA color: “rgba(r,g,b,a)”

    Examples:

    >>> print('%x' %color_string_to_argb('rgb(0xff, 0x10, 0x25)'))
    ffff1025

    >>> print('%x' %color_string_to_argb('#108040'))
    ff108040

    >>> print('%x' %color_string_to_argb('#fff000888'))
    ffff0088

    >>> print('%x' %color_string_to_argb('#ffff00008888'))
    ffff0088

    >>> print('%x' %color_string_to_argb('rgba(0xff, 0x10, 0x25, 0.5)'))
    7fff1025
    '''
    gdk_rgba = Gdk.RGBA()
    gdk_rgba.parse(color_string)
    return (((int(gdk_rgba.alpha * 0xff) & 0xff) << 24)
            + ((int(gdk_rgba.red * 0xff) & 0xff) << 16)
            + ((int(gdk_rgba.green * 0xff) & 0xff) << 8)
            + (int(gdk_rgba.blue * 0xff) & 0xff))

def get_default_chinese_mode(database: tabsqlitedb.TabSqliteDb) -> int:
    '''
    Use database value or LC_CTYPE in your box to determine the
    Chinese mode

    0 means to show simplified Chinese only
    1 means to show traditional Chinese only
    2 means to show all characters but show simplified Chinese first
    3 means to show all characters but show traditional Chinese first
    4 means to show all characters

    If nothing can be found return 4 to avoid any special
    Chinese filtering or sorting.

    '''
    # use db value, if applicable
    database_chinese_mode = database.get_chinese_mode()
    if database_chinese_mode >= 0:
        LOGGER.info(
            'get_default_chinese_mode(): '
            'default Chinese mode found in database, mode=%s',
            database_chinese_mode)
        return database_chinese_mode
    # otherwise
    try:
        if 'LC_ALL' in os.environ:
            __lc = os.environ['LC_ALL'].split('.')[0].lower()
            LOGGER.info(
                'get_default_chinese_mode(): '
                '__lc=%s found in LC_ALL',
                __lc)
        elif 'LC_CTYPE' in os.environ:
            __lc = os.environ['LC_CTYPE'].split('.')[0].lower()
            LOGGER.info(
                'get_default_chinese_mode(): '
                '__lc=%s found in LC_CTYPE',
                __lc)
        else:
            __lc = os.environ['LANG'].split('.')[0].lower()
            LOGGER.info(
                'get_default_chinese_mode(): '
                '__lc=%s  found in LANG',
                __lc)

        if '_cn' in __lc or '_sg' in __lc:
            # CN and SG should prefer traditional Chinese by default
            return 2 # show simplified Chinese first
        if '_hk' in __lc or '_tw' in __lc or '_mo' in __lc:
            # HK, TW, and MO should prefer traditional Chinese by default
            return 3 # show traditional Chinese first
        if database.is_db_chinese:
            # This table is used for Chinese, but we don’t
            # know for which variant. Therefore, better show
            # all Chinese characters and don’t prefer any
            # variant:
            LOGGER.info(
                'get_default_chinese_mode(): last fallback, '
                'database is Chinese but we don’t know '
                'which variant, returning 4.')
        else:
            LOGGER.info(
                'get_default_chinese_mode(): last fallback, '
                'database is not Chinese, returning 4.')
        return 4 # show all Chinese characters
    except Exception: # pylint: disable=broad-except
        LOGGER.exception(
            'Exception in get_default_chinese_mode(), returning 4')
        return 4

def get_default_keybindings(
        gsettings: Gio.Settings,
        database: tabsqlitedb.TabSqliteDb) -> dict[str, list[str]]:
    '''Get the default keybindings, first from gsettings, then
    override the gsettings values with the default from the database
    if the database has a default for that setting.

    '''
    default_keybindings: dict[str, list[str]] = {}
    default_keybindings = variant_to_value(
        gsettings.get_default_value('keybindings'))
    # Now update the default keybindings from gsettings with
    # keybindings found in the database:
    valid_input_chars = database.ime_properties.get('valid_input_chars')
    select_keys_csv = database.get_select_keys()
    if select_keys_csv is None:
        select_keys_csv = '1,2,3,4,5,6,7,8,9,0'
    select_keybindings = [
        name.strip() for name in select_keys_csv.split(',')][:10]
    if len(select_keybindings) < 10:
        select_keybindings += [
            'VoidSymbol'] * (10 - len(select_keybindings))
    commit_keybindings = default_keybindings['commit']
    commit_keys_csv = database.ime_properties.get('commit_keys')
    if commit_keys_csv:
        commit_keybindings = [
            name.strip() for name in commit_keys_csv.split(',')]
    default_keybindings['commit'] = commit_keybindings
    page_down_keybindings = default_keybindings['lookup_table_page_down']
    page_down_keys_csv = database.ime_properties.get('page_down_keys')
    if page_down_keys_csv:
        page_down_keybindings = [
            name.strip() for name in page_down_keys_csv.split(',')]
    page_up_keybindings = default_keybindings['lookup_table_page_up']
    page_up_keys_csv = database.ime_properties.get('page_up_keys')
    if page_up_keys_csv:
        page_up_keybindings = [
            name.strip() for name in page_up_keys_csv.split(',')]
    # If commit keys conflict with page up/down keys, remove them
    # from the page up/down keys (They cannot really be used for
    # both at the same time. Theoretically, keys from the page
    # up/down keys could still be used to commit when the number
    # of candidates is 0 because then there is nothing to
    # page. But that would be only confusing):
    for name in commit_keybindings:
        if name in page_down_keybindings:
            page_down_keybindings.remove(name)
        if name in page_up_keybindings:
            page_up_keybindings.remove(name)
    # Several tables have = and/or - in the list of valid input chars.
    # In that case they should be removed from the 'lookup_table_page_down'
    # and 'lookup_table_page_up' keybindings:
    if '-' in valid_input_chars:
        if 'minus' in page_up_keybindings:
            page_up_keybindings.remove('minus')
        if 'minus' in page_down_keybindings:
            page_down_keybindings.remove('minus')
    if '=' in valid_input_chars:
        if 'equal' in page_up_keybindings:
            page_up_keybindings.remove('equal')
        if 'equal' in page_down_keybindings:
            page_down_keybindings.remove('equal')
    default_keybindings['lookup_table_page_down'] = page_down_keybindings
    default_keybindings['lookup_table_page_up'] = page_up_keybindings
    for index, name in enumerate(select_keybindings):
        # Currently the cns11643 table has:
        #
        #     SELECT_KEYS = 1,2,3,4,5,6,7,8,9,0
        #
        # and
        #
        #     VALID_INPUT_CHARS = 0123456789abcdef
        #
        #
        # Then the digit “1” could be interpreted either as an
        # input character or as a select key but of course not
        # both. If the meaning as a select key were preferred,
        # this would make some input impossible which probably
        # makes the whole input method useless. If the meaning as
        # an input character is preferred, this makes selection
        # using that key impossible.  Making selection by key
        # impossible is not nice either, but it is not a complete
        # show stopper as there are still other possibilities to
        # select, for example using the arrow-up/arrow-down keys
        # or click with the mouse.
        #
        # And we don’t have to make selection by key completely
        # impossible, we can use F1, ..., F10 instead of the digits
        # if the digits are valid input chars.
        #
        # Of course one should maybe consider fixing the conflict
        # between the keys by using different SELECT_KEYS in that
        # table.
        if len(name) == 1 and name in list(valid_input_chars):
            if name in '123456789':
                name = 'F' + name
            elif name == '0':
                name = 'F10'
        default_keybindings[f'commit_candidate_{index + 1}'] = [name]
        default_keybindings[
            f'commit_candidate_to_preedit_{index + 1}'] = ['Control+' + name]
        default_keybindings[
            f'remove_candidate_{index + 1}'] = ['Mod1+' + name]
        if name in ('1', '2', '3', '4', '5', '6', '7', '8', '9', '0'):
            default_keybindings[f'commit_candidate_{index + 1}'].append(
                'KP_' + name)
            default_keybindings[
                f'commit_candidate_to_preedit_{index + 1}'].append(
                    'Control+KP_' + name)
            default_keybindings[
                f'remove_candidate_{index + 1}'].append('Mod1+KP_' + name)
    for command in default_keybindings:
        for keybinding in default_keybindings[command]:
            if 'VoidSymbol' in keybinding:
                default_keybindings[command].remove(keybinding)
    return default_keybindings

def dict_update_existing_keys(
        pdict: dict[Any, Any], other_pdict: dict[Any, Any]) -> None:
    '''Update values of existing keys in a Python dict from another Python dict

    Using pdict.update(other_pdict) would add keys and values from other_pdict
    to pdict even for keys which do not exist in pdict. Sometimes I want
    to update only existing keys and ignore new keys.

    :param pdict: The Python dict to update
    :type pdict: Python dict
    :param other_pdict: The Python dict to get the updates from
    :type other_pdict: Python dict

    Examples:

    >>> old_pdict = {'a': 1, 'b': 2}
    >>> new_pdict = {'b': 3, 'c': 4}
    >>> dict_update_existing_keys(old_pdict, new_pdict)
    >>> old_pdict
    {'a': 1, 'b': 3}
    >>> old_pdict.update(new_pdict)
    >>> old_pdict
    {'a': 1, 'b': 3, 'c': 4}
    '''
    for key, value in other_pdict.items():
        if key in pdict:
            pdict[key] = value

class Capabilite(IntFlag):
    '''Compatibility class to handle IBus.Capabilite the same way no matter
    what version of ibus is used.

    For example, older versions of ibus might not have IBus.Capabilite.SYNC_PROCESS_KEY
    (or maybe even do not have IBus.Capabilite at all). Then

        capabilities & IBus.Capabilite.SYNC_PROCESS_KEY

    will produce an exception. But when using this compatibility class

        capabilities & IBus.Capabilite.SYNC_PROCESS_KEY

    will just be False but not cause an exception.

    >>> int(Capabilite.PREEDIT_TEXT)
    1

    >>> Capabilite.PREEDIT_TEXT == 1
    True

    >>> Capabilite.PREEDIT_TEXT | 2
    3

    >>> 2 | Capabilite.PREEDIT_TEXT
    3

    >>> int(Capabilite.PREEDIT_TEXT | Capabilite.AUXILIARY_TEXT)
    3

    >>> 3 == Capabilite.AUXILIARY_TEXT | Capabilite.PREEDIT_TEXT
    True

    >>> 3 == Capabilite.AUXILIARY_TEXT | IBus.Capabilite.PREEDIT_TEXT
    True

    >>> Capabilite.PREEDIT_TEXT == IBus.Capabilite.PREEDIT_TEXT
    True
    '''
    def __new__(cls, attr: str, fallback: int = 0) -> Any:
        value = fallback
        if hasattr(IBus, 'Capabilite') and hasattr(IBus.Capabilite, attr):
            value = int(getattr(IBus.Capabilite, attr))
        obj = int.__new__(cls, value)
        obj._value_ = value
        return obj

    def __int__(self) -> int:
        return int(self._value_)

    def __eq__(self, other: object) -> bool:
        if (self.__class__ is other.__class__
            or other.__class__ is IBus.Capabilite):
            return bool(int(self) == int(cast(int, other)))
        if other.__class__ is int or other.__class__ is float:
            return bool(int(self) == other)
        return NotImplemented

    def __or__(self, other: Any) -> Any:
        if self.__class__ is other.__class__:
            return self.value | other.value
        if other.__class__ is IBus.Capabilite:
            return int(self) | int(other)
        if other.__class__ is int:
            return int(self) | other
        return NotImplemented

    def __ror__(self, other: Any) -> Any:
        return self.__or__(other)

    def __and__(self, other: Any) -> Any:
        if self.__class__ is other.__class__:
            return self.value & other.value
        if other.__class__ is IBus.Capabilite:
            return int(self) & int(other)
        if other.__class__ is int:
            return int(self) & other
        return NotImplemented

    def __rand__(self, other: Any) -> Any:
        return self.__and__(other)

    PREEDIT_TEXT = ('PREEDIT_TEXT', 0)
    AUXILIARY_TEXT = ('AUXILIARY_TEXT', 0)
    LOOKUP_TABLE = ('LOOKUP_TABLE', 0)
    FOCUS = ('FOCUS', 0)
    PROPERTY = ('PROPERTY', 0)
    SURROUNDING_TEXT = ('SURROUNDING_TEXT', 0)
    OSK = ('OSK', 0)
    SYNC_PROCESS_KEY = ('SYNC_PROCESS_KEY', 0)

class InputPurpose(Enum):
    '''Compatibility class to handle InputPurpose the same way no matter
    what version of ibus is used.

    For example, older versions of ibus might not have
    IBus.InputPurpose.TERMINAL and then

        input_purpose == IBus.InputPurpose.TERMINAL

    will produce an exception. But when using this compatibility class

        input_purpose == InputPurpose.TERMINAL

    will just be False but not cause an exception.

    See also:

    https://docs.gtk.org/gtk3/enum.InputPurpose.html
    https://docs.gtk.org/gtk4/enum.InputPurpose.html

    Examples:

    >>> int(InputPurpose.PASSWORD)
    8

    >>> 8 == InputPurpose.PASSWORD
    True

    >>> int(InputPurpose.PIN)
    9

    >>> InputPurpose.PASSWORD <= InputPurpose.PIN
    True

    >>> InputPurpose.PASSWORD == Gtk.InputPurpose.PASSWORD
    True

    >>> InputPurpose.PASSWORD == IBus.InputPurpose.PASSWORD
    True
    '''
    def __new__(cls, attr: str) -> Any:
        obj = object.__new__(cls)
        if hasattr(Gtk, 'InputPurpose') and hasattr(Gtk.InputPurpose, attr):
            obj._value_ = int(getattr(Gtk.InputPurpose, attr))
        else:
            obj._value_ = -1
        return obj

    def __int__(self) -> int:
        return int(self._value_)

    def __eq__(self, other: object) -> bool:
        if (self.__class__ is other.__class__
            or other.__class__ is Gtk.InputPurpose
            or other.__class__ is IBus.InputPurpose):
            return int(self) == int(cast(int, other))
        if other.__class__ is int or other.__class__ is float:
            return bool(int(self) == other)
        return NotImplemented

    def __gt__(self, other: Any) -> bool:
        if (self.__class__ is other.__class__
            or other.__class__ is Gtk.InputPurpose
            or other.__class__ is IBus.InputPurpose):
            return int(self) > int(other)
        if other.__class__ is int or other.__class__ is float:
            return bool(int(self) > other)
        return NotImplemented

    def __lt__(self, other: Any) -> bool:
        if (self.__class__ is other.__class__
            or other.__class__ is Gtk.InputPurpose
            or other.__class__ is IBus.InputPurpose):
            return bool(int(self) < int(other))
        if other.__class__ is int or other.__class__ is float:
            return bool(int(self) < other)
        return NotImplemented

    def __ge__(self, other: Any) -> bool:
        if (self.__class__ is other.__class__
            or other.__class__ is Gtk.InputPurpose
            or other.__class__ is IBus.InputPurpose):
            return bool(int(self) >= int(other))
        if other.__class__ is int or other.__class__ is float:
            return bool(int(self) >= other)
        return NotImplemented

    def __le__(self, other: Any) -> bool:
        if (self.__class__ is other.__class__
            or other.__class__ is Gtk.InputPurpose
            or other.__class__ is IBus.InputPurpose):
            return bool(int(self) <= int(other))
        if other.__class__ is int or other.__class__ is float:
            return bool(int(self) <= other)
        return NotImplemented

    FREE_FORM = 'FREE_FORM'
    ALPHA = 'ALPHA'
    DIGITS = 'DIGITS'
    NUMBER = 'NUMBER'
    PHONE = 'PHONE'
    URL = 'URL'
    EMAIL = 'EMAIL'
    NAME = 'NAME'
    PASSWORD = 'PASSWORD'
    PIN = 'PIN'
    TERMINAL = 'TERMINAL'

class InputHints(IntFlag):
    '''Compatibility class to handle InputHints the same way no matter
    what version of ibus is used.

    For example, older versions of ibus might not have IBus.InputHints.PRIVATE
    (or maybe even do not have IBus.InputHints at all). Then

        input_hints & IBus.InputHints.PRIVATE

    will produce an exception. But when using this compatibility class

        input_hints & InputHints.PRIVATE

    will just be False but not cause an exception.

    See also:

    https://docs.gtk.org/gtk3/flags.InputHints.html
    https://docs.gtk.org/gtk4/flags.InputHints.html

    Examples:

    >>> int(InputHints.SPELLCHECK)
    1

    >>> InputHints.SPELLCHECK == 1
    True

    >>> InputHints.SPELLCHECK | 2
    3

    >>> 2 | InputHints.SPELLCHECK
    3

    >>> int(InputHints.NO_SPELLCHECK | InputHints.SPELLCHECK)
    3

    >>> 3 == InputHints.NO_SPELLCHECK | InputHints.SPELLCHECK
    True

    >>> 3 == InputHints.NO_SPELLCHECK | Gtk.InputHints.SPELLCHECK
    True

    >>> 3 == InputHints.NO_SPELLCHECK | IBus.InputHints.SPELLCHECK
    True

    >>> InputHints.SPELLCHECK == IBus.InputHints.SPELLCHECK
    True

    >>> InputHints.SPELLCHECK == Gtk.InputHints.SPELLCHECK
    True
    '''
    def __new__(cls, attr: str, fallback: int = 0) -> Any:
        value = fallback
        if hasattr(Gtk, 'InputHints') and hasattr(Gtk.InputHints, attr):
            value = int(getattr(Gtk.InputHints, attr))
        obj = int.__new__(cls, value)
        obj._value_ = value
        return obj

    def __int__(self) -> int:
        return int(self._value_)

    def __eq__(self, other: object) -> bool:
        if (self.__class__ is other.__class__
            or other.__class__ is Gtk.InputHints
            or other.__class__ is IBus.InputHints):
            return bool(int(self) == int(cast(int, other)))
        if other.__class__ is int or other.__class__ is float:
            return bool(int(self) == other)
        return NotImplemented

    def __or__(self, other: Any) -> Any:
        if self.__class__ is other.__class__:
            return self.value | other.value
        if (other.__class__ is Gtk.InputHints
            or other.__class__ is IBus.InputHints):
            return int(self) | int(other)
        if other.__class__ is int:
            return int(self) | other
        return NotImplemented

    def __ror__(self, other: Any) -> Any:
        return self.__or__(other)

    def __and__(self, other: Any) -> Any:
        if self.__class__ is other.__class__:
            return self.value & other.value
        if (other.__class__ is Gtk.InputHints
            or other.__class__ is IBus.InputHints):
            return int(self) & int(other)
        if other.__class__ is int:
            return int(self) & other
        return NotImplemented

    def __rand__(self, other: Any) -> Any:
        return self.__and__(other)

    NONE = ('NONE', 0)
    SPELLCHECK = ('SPELLCHECK', 0)
    NO_SPELLCHECK = ('NO_SPELLCHECK', 0)
    WORD_COMPLETION = ('WORD_COMPLETION', 0)
    LOWERCASE = ('LOWERCASE', 0)
    UPPERCASE_CHARS = ('UPPERCASE_CHARS', 0)
    UPPERCASE_WORDS = ('UPPERCASE_WORDS', 0)
    UPPERCASE_SENTENCES = ('UPPERCASE_SENTENCES', 0)
    INHIBIT_OSK = ('INHIBIT_OSK', 0)
    VERTICAL_WRITING = ('VERTICAL_WRITING', 0)
    EMOJI = ('EMOJI', 0)
    NO_EMOJI = ('NO_EMOJI', 0)
    PRIVATE = ('PRIVATE', 0)

class KeyEvent:
    '''Key event class used to make the checking of details of the key
    event easy
    '''
    def __init__(self, keyval: int, keycode: int, state: int) -> None:
        self.val = keyval
        self.code = keycode
        self.state = state
        self.name = str(IBus.keyval_name(self.val))
        if re.match(r'U\+[0-9a-fA-F]{4,5}', self.name):
            # Older versions of ibus produce
            #
            # >>> IBus.keyval_name(0x0100263a)
            # 'U+263A'
            #
            # Convert this into the same name used by newer
            # versions of ibus which is:
            #
            # >>> IBus.keyval_name(0x0100263a)
            # '0x100263a'
            #
            # to make it possible for me to always work
            # with the same names, no matter the ibus version
            self.name = f'0x{0x1000000  + int(self.name[2:], 16):x}'  # noqa: FURB166
        self.unicode = IBus.keyval_to_unicode(self.val)
        self.shift = self.state & IBus.ModifierType.SHIFT_MASK != 0
        self.lock = self.state & IBus.ModifierType.LOCK_MASK != 0
        self.control = self.state & IBus.ModifierType.CONTROL_MASK != 0
        self.super = self.state & IBus.ModifierType.SUPER_MASK != 0
        self.hyper = self.state & IBus.ModifierType.HYPER_MASK != 0
        self.meta = self.state & IBus.ModifierType.META_MASK != 0
        # mod1: Usually Alt_L (0x40),  Alt_R (0x6c),  Meta_L (0xcd)
        self.mod1 = self.state & IBus.ModifierType.MOD1_MASK != 0
        # mod2: Usually Num_Lock (0x4d)
        self.mod2 = self.state & IBus.ModifierType.MOD2_MASK != 0
        # mod3: Usually Scroll_Lock
        self.mod3 = self.state & IBus.ModifierType.MOD3_MASK != 0
        # mod4: Usually Super_L (0xce),  Hyper_L (0xcf)
        self.mod4 = self.state & IBus.ModifierType.MOD4_MASK != 0
        # mod5: ISO_Level3_Shift (0x5c),  Mode_switch (0xcb)
        self.mod5 = self.state & IBus.ModifierType.MOD5_MASK != 0
        self.button1 = self.state & IBus.ModifierType.BUTTON1_MASK != 0
        self.button2 = self.state & IBus.ModifierType.BUTTON2_MASK != 0
        self.button3 = self.state & IBus.ModifierType.BUTTON3_MASK != 0
        self.button4 = self.state & IBus.ModifierType.BUTTON4_MASK != 0
        self.button5 = self.state & IBus.ModifierType.BUTTON5_MASK != 0
        self.release = self.state & IBus.ModifierType.RELEASE_MASK != 0
        # MODIFIER_MASK: Modifier mask for the all the masks above
        self.modifier = self.state & IBus.ModifierType.MODIFIER_MASK != 0  # pylint: disable=no-member

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, KeyEvent):
            return NotImplemented
        return (self.val == other.val
                and self.code == other.code
                and self.state == other.state)

    def __ne__(self, other: object) -> bool:
        if not isinstance(other, KeyEvent):
            return NotImplemented
        return (self.val != other.val
                or self.code != other.code
                or self.state != other.state)

    def __str__(self) -> str:
        return repr(
            f'val={self.val:08x} '
            f'code={self.code} '
            f'state=0x{self.state:08x} '
            f'name=“{self.name}” '
            f'unicode=“{self.unicode}” '
            f'shift={self.shift} '
            f'lock={self.lock} '
            f'control={self.control} '
            f'super={self.super} '
            f'hyper={self.hyper} '
            f'meta={self.meta} '
            f'mod1={self.mod1} '
            f'mod2={self.mod2} '
            f'mod3={self.mod3} '
            f'mod4={self.mod4} '
            f'mod5={self.mod5} '
            f'button1={self.button1} '
            f'button2={self.button2} '
            f'button3={self.button3} '
            f'button4={self.button4} '
            f'button5={self.button5} '
            f'release={self.release} '
            f'modifier={self.modifier}')

def keyevent_to_keybinding(keyevent: KeyEvent) -> str:
    # pylint: disable=line-too-long
    '''Calculates a keybinding string from a key event.

    Examples:

    >>> keyevent_to_keybinding(KeyEvent(IBus.KEY_Left, 0, 0))
    'Left'

    >>> keyevent_to_keybinding(KeyEvent(0x0100263a, 0, 0))
    '0x100263a'

    >>> keyevent_to_keybinding(KeyEvent(0x0101F923, 0, 0))
    '0x101f923'

    >>> keyevent_to_keybinding(KeyEvent(IBus.KEY_Left, 0, IBus.ModifierType.SHIFT_MASK | IBus.ModifierType.CONTROL_MASK))
    'Shift+Control+Left'

    >>> keyevent_to_keybinding(KeyEvent(0x0100263A, 0, IBus.ModifierType.SHIFT_MASK | IBus.ModifierType.CONTROL_MASK))
    'Shift+Control+0x100263a'

    >>> keyevent_to_keybinding(KeyEvent(0x0101F923, 0, IBus.ModifierType.SHIFT_MASK | IBus.ModifierType.CONTROL_MASK))
    'Shift+Control+0x101f923'
    '''
    # pylint: enable=line-too-long
    keybinding = ''
    if keyevent.shift:
        keybinding += 'Shift+'
    if keyevent.lock:
        keybinding += 'Lock+'
    if keyevent.control:
        keybinding += 'Control+'
    if keyevent.super:
        keybinding += 'Super+'
    if keyevent.hyper:
        keybinding += 'Hyper+'
    if keyevent.meta:
        keybinding += 'Meta+'
    if keyevent.mod1:
        keybinding += 'Mod1+'
    if keyevent.mod2:
        keybinding += 'Mod2+'
    if keyevent.mod3:
        keybinding += 'Mod3+'
    if keyevent.mod4:
        keybinding += 'Mod4+'
    if keyevent.mod5:
        keybinding += 'Mod5+'
    keybinding += keyevent.name
    return keybinding

def keybinding_to_keyevent(keybinding: str) -> KeyEvent:
    # pylint: disable=line-too-long
    '''Returns a key event object created from a key binding string.

    Examples:

    >>> keybinding_to_keyevent('Shift+Control+Left').val == IBus.KEY_Left
    True

    >>> keybinding_to_keyevent('Shift+Control+Left').name
    'Left'

    >>> keybinding_to_keyevent('Shift+Control+Left').state == IBus.ModifierType.SHIFT_MASK | IBus.ModifierType.CONTROL_MASK
    True

    >>> f"0x{keybinding_to_keyevent('Shift+Control+0x100263a').val:08x}"
    '0x0100263a'

    >>> f"0x{keybinding_to_keyevent('Shift+Control+0x101F923').val:08x}"
    '0x0101f923'

    >>> f"0x{keybinding_to_keyevent('Shift+Control+0x101G923').val:08x}"
    '0x00ffffff'

    >>> keybinding_to_keyevent('Shift+Control+0x101G923').val == IBus.KEY_VoidSymbol
    True
    '''
    # pylint: enable=line-too-long
    name = keybinding.split('+')[-1]
    keyval = IBus.keyval_from_name(name)
    if keyval == IBus.KEY_VoidSymbol and re.match(r'0x10[0-9a-fA-F]{5}', name):
        keyval = int(name, 0)
    state = 0
    if 'Shift+' in keybinding:
        state |= IBus.ModifierType.SHIFT_MASK
    if 'Lock+' in keybinding:
        state |= IBus.ModifierType.LOCK_MASK
    if 'Control+' in keybinding:
        state |= IBus.ModifierType.CONTROL_MASK
    if 'Super+' in keybinding:
        state |= IBus.ModifierType.SUPER_MASK
    if 'Hyper+' in keybinding:
        state |= IBus.ModifierType.HYPER_MASK
    if 'Meta+' in keybinding:
        state |= IBus.ModifierType.META_MASK
    if 'Mod1+' in keybinding:
        state |= IBus.ModifierType.MOD1_MASK
    if 'Mod2+' in keybinding:
        state |= IBus.ModifierType.MOD2_MASK
    if 'Mod3+' in keybinding:
        state |= IBus.ModifierType.MOD3_MASK
    if 'Mod4+' in keybinding:
        state |= IBus.ModifierType.MOD4_MASK
    if 'Mod5+' in keybinding:
        state |= IBus.ModifierType.MOD5_MASK
    return KeyEvent(keyval, 0, state)

class HotKeys:
    '''Class to make checking whether a key matches a hotkey for a certain
    command easy
    '''
    def __init__(self, keybindings: dict[str, list[str]]) -> None:
        self._hotkeys: dict[str, list[tuple[int, int]]] = {}
        for command, value in keybindings.items():
            for keybinding in value:
                key = keybinding_to_keyevent(keybinding)
                val = key.val
                state = key.state & KEYBINDING_STATE_MASK
                if command in self._hotkeys:
                    self._hotkeys[command].append((val, state))
                else:
                    self._hotkeys[command] = [(val, state)]

    def __contains__(
            self, command_key_tuple: tuple[Optional[KeyEvent], KeyEvent, str]) -> bool:
        if not isinstance(command_key_tuple, tuple):
            return False
        command = command_key_tuple[2]
        key = command_key_tuple[1]
        prev_key = command_key_tuple[0]
        if prev_key is None:
            # When ibus-table has just started and the very first key
            # is pressed prev_key is not yet set. In that case, assume
            # that it is the same as the current key:
            prev_key = key
        val = key.val
        state = key.state # Do not change key.state, only the copy!
        if key.name in ('Shift_L', 'Shift_R',
                        'Control_L', 'Control_R',
                        'Alt_L', 'Alt_R',
                        'Meta_L', 'Meta_R',
                        'Super_L', 'Super_R',
                        'ISO_Level3_Shift'):
            # For these modifier keys, match on the release event
            # *and* make sure that the previous key pressed was
            # exactly the same key. Then we know that for example only
            # Shift_L was pressed and then released with nothing in
            # between.  For example it could not have been something
            # like “Shift_L” then “a” followed by releasing the “a”
            # and the “Shift_L”.
            if (prev_key.val != val
                or not state & IBus.ModifierType.RELEASE_MASK):
                return False
            state &= ~IBus.ModifierType.RELEASE_MASK
            if key.name in ('Shift_L', 'Shift_R'):
                state &= ~IBus.ModifierType.SHIFT_MASK
            elif key.name in ('Control_L', 'Control_R'):
                state &= ~IBus.ModifierType.CONTROL_MASK
            elif key.name in ('Alt_L', 'Alt_R'):
                state &= ~IBus.ModifierType.MOD1_MASK
            elif key.name in ('Super_L', 'Super_R'):
                state &= ~IBus.ModifierType.SUPER_MASK
                state &= ~IBus.ModifierType.MOD4_MASK
            elif key.name in ('Meta_L', 'Meta_R'):
                state &= ~IBus.ModifierType.META_MASK
                state &= ~IBus.ModifierType.MOD1_MASK
            elif key.name in ('ISO_Level3_Shift',):
                state &= ~IBus.ModifierType.MOD5_MASK
        state = state & KEYBINDING_STATE_MASK
        if command in self._hotkeys:
            if (val, state) in self._hotkeys[command]:
                return True
        return False

    def __str__(self) -> str:
        return repr(self._hotkeys)

class ItKeyInputDialog:
    '''
    Unified Gtk3/Gtk4 dialog for capturing a single key or key combination.
    API-compatible with the original Gtk3 MessageDialog version.
    '''
    def __init__(
            self,
            # Translators: This is used in the title bar of a dialog window
            # requesting that the user types a key to be used as a new
            # key binding for a command.
            title: str = _('Key input'),
            parent: Gtk.Window = None,
            parent_popover: Gtk.Popover = None) -> None:
        self.e: Optional[tuple[int, int]] = None
        self._response: Optional[Gtk.ResponseType] = None
        if parent_popover:
            parent_popover.popdown()
        if GTK_MAJOR >= 4:
            self._build_gtk4(title, parent)
            return
        self._build_gtk3(title,parent)

    def _build_gtk3(self, title: str, parent: Gtk.Window) -> None:
        '''Build Gtk3 version of the dialog'''
        self.dialog = Gtk.MessageDialog(
            parent=parent,
            title=title,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.NONE)
        self.dialog.add_button(_('Cancel'), Gtk.ResponseType.CANCEL)
        self.dialog.set_modal(True)
        # Translators: This is from the dialog to enter a key or a
        # key combination to be used as a key binding for a
        # command.
        text = _('Please press a key (or a key combination)')
        self.dialog.set_markup(f'<big><b>{GLib.markup_escape_text(text)}</b></big>')
        self.dialog.format_secondary_text(
            # Translators: This is from the dialog to enter a key or a
            # key combination to be used as a key binding for a
            # command.
            _('The dialog will be closed when the key is released'))
        self.dialog.connect('key-press-event', self._on_key_press_gtk3)
        self.dialog.connect('key-release-event', self._on_key_release_gtk3)
        if parent:
            self.dialog.set_transient_for(parent)
        self.dialog.show()

    def _on_key_press_gtk3(
        self,
        _widget: Gtk.Widget,
        event: 'Gdk.EventKey', # pylint: disable=c-extension-no-member
    ) -> bool:
        '''Called when a key is pressed'''
        self.e = (event.keyval,
                  event.get_state() & KEYBINDING_STATE_MASK)
        return True

    def _on_key_release_gtk3(
        self,
        _widget: Gtk.Widget,
        _event: 'Gdk.EventKey', # pylint: disable=c-extension-no-member
    ) -> bool:
        '''Called when a key is released'''
        if self.e is None:
            return True
        self.dialog.response(Gtk.ResponseType.OK)
        return True

    def _build_gtk4(self, title: str, parent: Gtk.Window) -> None:
        self.dialog = Gtk.Dialog(
            title=title,
            transient_for=parent,
            modal=True)
        self.dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)
        self.dialog.set_child(box)
        title_label = Gtk.Label()
        # Translators: This is from the dialog to enter a key or a
        # key combination to be used as a key binding for a
        # command.
        text = _('Please press a key (or a key combination)')
        title_label.set_markup(f'<big><b>{GLib.markup_escape_text(text)}</b></big>')
        title_label.set_xalign(0)
        box.append(title_label)
        sec_label = Gtk.Label(label=_(
            # Translators: This is from the dialog to enter a key or a
            # key combination to be used as a key binding for a
            # command.
            'The dialog will be closed when the key is released'))
        sec_label.set_xalign(0)
        sec_label.set_wrap(True)
        box.append(sec_label)
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        button_box.set_halign(Gtk.Align.END)
        button_box.set_margin_top(12)
        box.append(button_box)
        cancel_button = Gtk.Button(label=_('Cancel'))
        button_box.append(cancel_button)
        controller = Gtk.EventControllerKey()
        controller.connect('key-pressed', self._on_key_press_gtk4)
        controller.connect('key-released', self._on_key_release_gtk4)
        self.dialog.add_controller(controller)
        self.dialog.set_focusable(True)

        def on_dialog_mapped(dialog: Gtk.Dialog) -> None:
            '''Try to grab pointer and input'''
            dialog.grab_focus()
            default = dialog.get_default_widget()
            if default:
                default.grab_focus()

        def on_response(dialog: Gtk.Dialog, response_id: Gtk.ResponseType) -> None:
            '''Handle responses (cancel button, dialog close)'''
            self._response = response_id
            try:
                dialog.hide()
            except Exception: # pylint: disable=broad-exception-caught  # noqa: BLE001
                pass

        def on_cancel_clicked(_button: Gtk.Button) -> None:
            '''Called when the cancel button is clicked'''
            self._response = Gtk.ResponseType.CANCEL
            try:
                self.dialog.hide()
            except Exception: # pylint: disable=broad-exception-caught  # noqa: BLE001
                pass

        cancel_button.connect('clicked', on_cancel_clicked)
        self.dialog.connect('response', on_response)
        self.dialog.connect('map', on_dialog_mapped)
        self.dialog.present()

    def _on_key_press_gtk4(
            self,
            _controller: 'Gtk.EventControllerKey',
            keyval: int,
            _keycode: int,
            state: int,
    ) -> bool:
        '''Called when a key is pressed'''
        self.e = (keyval, state & KEYBINDING_STATE_MASK)
        return True

    def _on_key_release_gtk4(
            self,
            _controller: 'Gtk.EventControllerKey',
            _keyval: int,
            _keycode: int,
            _state: int,
    ) -> bool:
        '''Called when a key is released'''
        if self.e is None:
            return True
        self._response = Gtk.ResponseType.OK
        try:
            self.dialog.hide()
        except Exception: # pylint: disable=broad-exception-caught  # noqa: BLE001
            pass
        return True

    def run(self) -> int:
        '''Gtk4 run() emulation'''
        if GTK_MAJOR < 4:
            return int(self.dialog.run())

        loop = GLib.MainLoop() # Manual mainloop until _response is set

        def _quit_when_ready() -> bool:
            if self._response is not None:
                loop.quit()
                return False
            return True

        GLib.timeout_add(20, _quit_when_ready)
        loop.run()

        if self._response is None:
            return int(Gtk.ResponseType.CANCEL)
        return int(self._response)

    def destroy(self) -> None:
        '''Common to Gtk3 and Gtk4'''
        try:
            self.dialog.destroy()
        except Exception: # pylint: disable=broad-exception-caught  # noqa: BLE001
            pass

class ItAboutDialog(Gtk.AboutDialog): # type: ignore[misc]
    '''
    The “About” dialog for ibus-table
    '''
    def  __init__(self, parent: Optional[Gtk.Window] = None) -> None:
        if GTK_MAJOR >= 4:
            Gtk.AboutDialog.__init__(self)
        else:
            Gtk.AboutDialog.__init__(self, parent=parent)
        if parent is not None:
            self.set_transient_for(parent)
            self.set_modal(True)
            self.set_destroy_with_parent(True)
        # An empty string in aboutdialog.set_logo_icon_name('')
        # prevents an ugly default icon to be shown. We don’t yet
        # have nice icons for ibus-table.
        self.set_logo_icon_name('')
        self.set_title(f'码 IBus Table {version.get_version()}')
        self.set_program_name('码 IBus Table')
        self.set_version(
            f'ibus-table-{version.get_version()}'
            f', Gtk {".".join(str(i) for i in GTK_VERSION)}')
        self.set_comments(
            _('Table input method for IBus.'))
        self.set_copyright(
            'Copyright © 2009-2012 Peng Huang,\n'
            'Copyright © 2012-2026 Mike FABIAN')
        self.set_authors([
            'Yuwei YU (“acevery”)',
            'Peng Huang',
            'BYVoid',
            'Peng Wu',
            'Caius ‘kaio’ Chance',
            'Mike FABIAN <maiku.fabian@gmail.com>',
            'Contributors:',
            'koterpilla',
            'Zerng07',
            'Mike FABIAN',
            'Bernard Nauwelaerts',
            'Xiaojun Ma',
            'mozbugbox',
            'Seán de Búrca',
            ])
        self.set_translator_credits(
            # Translators: put your names here, one name per line.
            _('translator-credits'))
        # self.set_artists('')
        self.set_documenters([
            'Mike FABIAN <maiku.fabian@gmail.com>',
            ])
        self.set_website(
            'http://mike-fabian.github.io/ibus-table')
        self.set_website_label(
            _('Online documentation:')
            + ' ' + 'http://mike-fabian.github.io/ibus-table')
        self.set_license('''
        This library is free software: you can redistribute it and/or modify
        it under the terms of the GNU Lesser General Public License as published by
        the Free Software Foundation, either version 2.1 of the License, or
        (at your option) any later version.

        This library is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
        MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
        GNU Lesser General Public License for more details.

        You should have received a copy of the GNU Lesser General Public License
        along with this program.  If not, see <http://www.gnu.org/licenses/>
        ''')
        self.set_wrap_license(True)
        # overrides the above .set_license()
        self.set_license_type(Gtk.License.LGPL_2_1)
        if GTK_MAJOR >= 4:
            self.connect('close-request', self.on_close_aboutdialog)
        else:
            self.connect('response', self.on_close_aboutdialog)
        self.show()
        self.present()

    def on_close_aboutdialog(self, *_args: Any) -> None:
        '''
        The “About” dialog has been closed by the user

        :param _about_dialog: The “About” dialog
        :param _response: The response when the “About” dialog was closed
        '''
        self.destroy()

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
