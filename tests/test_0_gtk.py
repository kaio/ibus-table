#!/usr/bin/python3
#
# ibus-table - The Tables engine for IBus
#
# Copyright (c) 2020 Takao Fujiwara <takao.fujiwara1@gmail.com>
# Copyright (c) 2020 Mike FABIAN <mfabian@redhat.com>
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
# License along with this library.  If not, see  <http://www.gnu.org/licenses/>
'''
This file implements the test cases using GTK GUI
'''
# pylint: disable=attribute-defined-outside-init
# pylint: disable=missing-function-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=global-statement
# pylint: disable=wrong-import-order
# pylint: disable=wrong-import-position
from types import ModuleType
from typing import Any
from typing import Optional
from typing import cast
import argparse
import os
import signal
import sys
import unittest

from gi import require_version as gi_require_version
gi_require_version('GLib', '2.0')
gi_require_version('Gio', '2.0')
gi_require_version('IBus', '1.0')
from gi.repository import GLib  # type: ignore[attr-defined]  # ty: ignore[unresolved-import]
from gi.repository import Gio  # type: ignore[attr-defined]  # ty: ignore[unresolved-import]
from gi.repository import IBus

# Get more verbose output in the test log:
os.environ['IBUS_TABLE_DEBUG_LEVEL'] = '255'

sys.path.insert(0, "../engine")
if os.environ.get('IT_GTK_VERSION', None) is None:
    os.environ['IT_GTK_VERSION'] = '3'
# pylint: disable=import-error
from it_gtk import Gdk, Gtk
# pylint: enable=import-error

table: Optional[ModuleType]
try:
    import table as _table
    table = _table
except ImportError:
    table = None
tabsqlitedb: Optional[ModuleType]
try:
    import tabsqlitedb as _tabsqlitedb
    tabsqlitedb = _tabsqlitedb
except ImportError:
    tabsqlitedb = None
sys.path.pop(0)

DONE_EXIT = True
ENGINE_NAME = 'wubi-jidian86'

from gtkcases import TEST_CASES # pylint: disable=import-error

# Need to flush the output against GLib.MainLoop()
def printflush(sentence: str) -> None:
    try:
        print(sentence, flush=True)
    except OSError:
        pass

def printerr(sentence: str) -> None:
    try:
        print(sentence, flush=True, file=sys.stderr)
    except OSError:
        pass

@unittest.skipUnless(
    os.path.isfile(
        os.path.join('/usr/share/ibus-table/tables', ENGINE_NAME + '.db')),
    f'{ENGINE_NAME}.db is not installed.')
@unittest.skipUnless(
    'XDG_SESSION_TYPE' in os.environ
    and os.environ['XDG_SESSION_TYPE'] in ('x11', 'wayland'),
    'XDG_SESSION_TYPE is neither "x11" nor "wayland".')
@unittest.skipIf(Gdk.Display.open('') is None, 'Display cannot be opened.')
class SimpleGtk3TestCase(unittest.TestCase):
    glib_main_loop: Optional[GLib.MainLoop] = None
    ENGINE_PATH = '/com/redhat/IBus/engines/table/Test/Engine'
    _flag: bool = False
    _gsettings: Optional[Gio.Settings] = None
    _orig_chinesemode: int = 4

    @classmethod
    def setUpClass(cls) -> None:
        cls._flag = False
        cls._gsettings = Gio.Settings(
            schema='org.freedesktop.ibus.engine.table',
            path=f'/org/freedesktop/ibus/engine/table/{ENGINE_NAME}/')
        cls._orig_chinesemode = cls._gsettings.get_int('chinesemode')
        signums: list[Optional[signal.Signals]] = [
            getattr(signal, s, None) for s in ['SIGINT', 'SIGTERM', 'SIGHUP']]
        for signum in filter(None, signums):
            original_handler = signal.getsignal(signum)
            GLib.unix_signal_add(GLib.PRIORITY_HIGH,
                                 signum,
                                 cls.signal_handler,
                                 (signum, original_handler))
    @classmethod
    def tearDownClass(cls) -> None:
        if cls._gsettings is not None:
            cls._gsettings.set_int('chinesemode', cls._orig_chinesemode)

    @classmethod
    def signal_handler(cls, user_data: Any) -> None:
        (signum, original_handler) = user_data
        cls.tearDownClass()
        if cls.glib_main_loop is not None:
            cls.glib_main_loop.quit()
        signal.signal(signum, original_handler)
        cls._flag = True
        assert False, 'signal received: ' + str(signum)

    def setUp(self) -> None:
        self.__id = 0
        self.__rerun = False
        self.__test_index = 0
        self.__preedit_index = 0
        self.__lookup_index = 0
        self.__inserted_text = ''
        self.__commit_done = False # pylint: disable=unused-private-member
        self.__reset_coming = False
        if self._gsettings is not None:
            self._gsettings.set_int('chinesemode', 4)
        self.__class__.glib_main_loop = GLib.MainLoop()
        Gtk.init() # pylint: disable=no-value-for-parameter

    def tearDown(self) -> None:
        if self.__class__.glib_main_loop is not None:
            self.__class__.glib_main_loop.quit()

    def register_ibus_engine(self) -> bool:
        self.__bus = IBus.Bus()
        if not self.__bus.is_connected():
            self.fail('ibus-daemon is not running')
        self.__bus.get_connection().signal_subscribe(
            'org.freedesktop.DBus',
            'org.freedesktop.DBus',
            'NameOwnerChanged',
            '/org/freedesktop/DBus',
            None,
            0,
            self.__bus_signal_cb,
            self.__bus)
        self.__factory = IBus.Factory(
            object_path=IBus.PATH_FACTORY,
            connection=self.__bus.get_connection())
        self.__factory.connect('create-engine', self.__create_engine_cb)
        self.__component = IBus.Component(
            name='org.freedesktop.IBus.Table.Test',
            description='Test Table Component',
            version='1.0',
            license='GPL',
            author=('Mike FABIAN <mfabian@redhat.com>, '
                    + 'Caius "kaio" CHANCE <caius.chance@gmail.com>'),
            homepage='http://mike-fabian.github.io/ibus-table/',
            command_line='',
            textdomain='ibus-table')
        desc = IBus.EngineDesc(
            name=ENGINE_NAME,
            longname=f'Test Table {ENGINE_NAME}',
            description='Test Table Component',
            language='t',
            license='GPL',
            author=('Mike FABIAN <mfabian@redonat.com>, '
                    + 'Caius "kaio" CHANCE <caius.chance@gmail.com>'),
            icon='',
            symbol='T')
        self.__component.add_engine(desc)
        self.__bus.register_component(self.__component)
        self.__bus.request_name('org.freedesktop.IBus.Table.Test', 0)
        return True

    def __bus_signal_cb(
            self,
            connection: Gio.DBusConnection,
            sender_name: str,
            object_path: str,
            interface_name: str,
            signal_name: str,
            parameters: GLib.Variant,
            user_data: IBus.Bus) -> None:
        if signal_name == 'NameOwnerChanged':
            pass
        if signal_name == 'UpdateLookupTable':
            lookup_table = self.__engine.get_lookup_table()
            if lookup_table.get_number_of_candidates() == 0:
                return
            self.__lookup_test()

    def __create_engine_cb(
            self, factory: IBus.Factory, engine_name: str) -> Optional[Any]:
        if engine_name != ENGINE_NAME:
            return None
        if not table or not tabsqlitedb:
            with self.subTest(i='create-engine'):
                self.fail('NG: ibus-table not installed?')
            self.__class__.glib_main_loop.quit()
            return None
        self.__id += 1
        object_path = f'{self.ENGINE_PATH}/{self.__id:d}'
        db_dir = '/usr/share/ibus-table/tables'
        db_file = os.path.join(db_dir, engine_name + '.db')
        database = tabsqlitedb.TabSqliteDb(
            filename=db_file, user_db=':memory:')
        self.__engine = table.TabEngine(
            self.__bus,
            object_path,
            database)
        self.__engine.connect('focus-in', self.__engine_focus_in)
        self.__engine.connect('focus-out', self.__engine_focus_out)
        self.__engine.connect_after('reset', self.__engine_reset)
        self.__bus.get_connection().signal_subscribe(
            None,
            IBus.INTERFACE_ENGINE,
            'UpdateLookupTable',
            object_path,
            None,
            0,
            self.__bus_signal_cb,
            self.__bus)
        return self.__engine

    def __engine_focus_in(self, _engine: IBus.Engine) -> None:
        if self.__test_index >= len(TEST_CASES['tests']):
            if DONE_EXIT and self.__class__.glib_main_loop is not None:
                self.__class__.glib_main_loop.quit()
            return
        # Workaround because focus-out resets the preedit text
        # ibus_bus_set_global_engine() calls bus_input_context_set_engine()
        # twice and it causes bus_engine_proxy_focus_out()
        if self.__rerun:
            self.__rerun = False
            self.__main_test()

    def __engine_focus_out(self, _engine: IBus.Engine) -> None:
        self.__rerun = True
        self.__test_index = 0
        self.__entry.set_text('')

    def __engine_reset(self, _engine: IBus.Engine) -> None:
        if self.__reset_coming:
            self.__reset_coming = False
            self.__main_test()

    def __entry_focus_in_event_cb(
            self,
            entry: Gtk.Entry,
            event: 'Gdk.EventFocus',  # pylint: disable=c-extension-no-member
    ) -> bool:
        if self.__test_index >= len(TEST_CASES['tests']):
            if DONE_EXIT and self.__class__.glib_main_loop is not None:
                self.__class__.glib_main_loop.quit()
            return False
        self.__bus.set_global_engine_async(ENGINE_NAME,
                                           -1, None, self.__set_engine_cb)
        return False

    def __set_engine_cb(self, _object: IBus.Bus, res: Gio.Task) -> None:
        with self.subTest(i=self.__test_index):
            if not self.__bus.set_global_engine_async_finish(res):
                self.fail('set engine failed.')
            return
        # rerun always happen?
        #self.__main_test()

    def __get_test_condition_length(self, tag: str) -> int:
        tests: dict[str, Any] = TEST_CASES['tests'][self.__test_index]
        try:
            cases = tests[tag]
        except KeyError:
            return -1
        case_type = next(iter(cases.keys()))
        return len(cases[case_type])

    def __entry_preedit_changed_cb(
            self, entry: Gtk.Entry, preedit_str: str) -> None:
        if len(preedit_str) == 0:
            return
        if self.__test_index >= len(TEST_CASES['tests']):
            if DONE_EXIT and self.__class__.glib_main_loop is not None:
                self.__class__.glib_main_loop.quit()
            return
        self.__preedit_index += 1
        if self.__preedit_index != self.__get_test_condition_length('preedit'):
            return
        if self.__get_test_condition_length('lookup') > 0:
            return
        self.__run_cases('commit')

    def __main_test(self) -> None:
        self.__preedit_index = 0
        self.__lookup_index = 0
        self.__commit_done = False # pylint: disable=unused-private-member
        self.__run_cases('preedit')

    def __lookup_test(self) -> None:
        lookup_length = self.__get_test_condition_length('lookup')
        # Need to return again even if all the lookup is finished
        # until the final Engine.update_preedit() is called.
        if self.__lookup_index > lookup_length:
            return
        self.__run_cases('lookup',
                         self.__lookup_index,
                         self.__lookup_index + 1)
        if self.__lookup_index < lookup_length:
            self.__lookup_index += 1
            return
        self.__lookup_index += 1
        self.__run_cases('commit')

    def __run_cases(self, tag: str, start: int = -1, end: int = -1) -> None:
        tests: dict[str, Any] = TEST_CASES['tests'][self.__test_index]
        if tests is None:
            return
        try:
            cases = tests[tag]
        except KeyError:
            return
        case_type = next(iter(cases.keys()))
        i = 0
        if case_type == 'string':
            printflush(
                f'test step: {tag} sequences: "{cases["string"]!s}"')
            for character in cast(str, cases['string']):
                if start >= 0 and i < start:
                    i += 1
                    continue
                if 0 <= end <= i:
                    break
                self.__typing(ord(character), 0, 0)
                i += 1
        if case_type == 'keys':
            if start == -1 and end == -1:
                printflush(f'test step: {tag} sequences: {cases["keys"]!s}')
            for key in cast(list[list[int]], cases['keys']):
                if start >= 0 and i < start:
                    i += 1
                    continue
                if 0 <= end <= i:
                    break
                if start != -1 or end != -1:
                    printflush(
                        f'test step: {tag}s sequences: '
                        f'[0x{key[0]:X}, 0x{key[1]:X}, 0x{key[2]:X}]')
                self.__typing(key[0], key[1], key[2])
                i += 1

    def __typing(self, keyval: int, keycode: int, modifiers: int) -> None:
        self.__engine.emit('process-key-event', keyval, keycode, modifiers)
        modifiers |= IBus.ModifierType.RELEASE_MASK
        self.__engine.emit('process-key-event', keyval, keycode, modifiers)

    def __buffer_inserted_text_cb(
            self, buffer: Gtk.EntryBuffer, position: int, chars: str, nchars: int) -> None:
        tests: dict[str, Any] = TEST_CASES['tests'][self.__test_index]
        cases = tests['commit']
        case_type = next(iter(cases.keys()))
        if case_type == 'keys':
            # space key is sent separatedly later
            if cases['keys'][0] == [IBus.KEY_space, 0, 0]:
                self.__inserted_text += chars
            elif cases['keys'][0] == [IBus.KEY_Return, 0, 0] or \
                 cases['keys'][0] == [IBus.KEY_KP_Enter, 0, 0] or \
                 cases['keys'][0] == [IBus.KEY_ISO_Enter, 0, 0] or \
                 cases['keys'][0] == [IBus.KEY_Escape, 0, 0]:
                self.__inserted_text = chars
                self.__reset_coming = True
        else:
            self.__inserted_text = chars
        cases = tests['result']
        if cases['string'] == self.__inserted_text:
            printflush(f'OK: {self.__test_index} "{self.__inserted_text}"')
        else:
            if DONE_EXIT and self.__class__.glib_main_loop is not None:
                self.__class__.glib_main_loop.quit()
            with self.subTest(i=self.__test_index):
                self.fail(f'NG: {self.__test_index:d} '
                           f'"{cases["string"]!s}" "{self.__inserted_text}"')
        self.__inserted_text = ''
        self.__test_index += 1
        if self.__test_index >= len(TEST_CASES['tests']):
            if DONE_EXIT and self.__class__.glib_main_loop is not None:
                self.__class__.glib_main_loop.quit()
            return
        self.__commit_done = True # pylint: disable=unused-private-member
        self.__entry.set_text('')
        if not self.__reset_coming:
            self.__main_test()

    def create_window(self) -> None:
        window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)  # pylint: disable=c-extension-no-member
        self.__entry = entry = Gtk.Entry()
        if self.__class__.glib_main_loop is not None:
            window.connect('destroy', self.__class__.glib_main_loop.quit)
        entry.connect('focus-in-event', self.__entry_focus_in_event_cb)
        entry.connect('preedit-changed', self.__entry_preedit_changed_cb)
        buffer = entry.get_buffer()
        buffer.connect('inserted-text', self.__buffer_inserted_text_cb)
        window.add(entry)
        window.show_all()

    def main(self) -> None: # pylint: disable=no-self-use
        # Some ATK relative warnings are called during launching GtkWindow.
        flags = GLib.log_set_always_fatal(GLib.LogLevelFlags.LEVEL_CRITICAL)
        if self.__class__.glib_main_loop is not None:
            self.__class__.glib_main_loop.run()
        GLib.log_set_always_fatal(flags)

    def test_typing(self) -> None:
        if not self.register_ibus_engine():
            sys.exit(-1)
        self.create_window()
        self.main()
        if self._flag:
            self.fail('NG: signal failure')

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('-k', '--keep', action='store_true',
                        help='keep this GtkWindow after test is done')
    parser.add_argument('-F', '--unittest-failfast', action='store_true',
                        help='stop on first fail or error in unittest')
    parser.add_argument('-H', '--unittest-help', action='store_true',
                        help='show unittest help message and exit')
    args, unittest_args = parser.parse_known_args()
    sys.argv[1:] = unittest_args
    if args.keep:
        global DONE_EXIT
        DONE_EXIT = False
    if args.unittest_failfast:
        sys.argv.append('-f')
    if args.unittest_help:
        sys.argv.append('-h')
        unittest.main()

    unittest.main()

if __name__ == '__main__':
    main()
