# -*- coding: utf-8 -*-
# vim:et sts=4 sw=4
#
# ibus-table-setup - Setup UI for ibus-table
#
# Copyright (c) 2008-2010 Peng Huang <shawn.p.huang@gmail.com>
# Copyright (c) 2010 BYVoid <byvoid1@gmail.com>
# Copyright (c) 2012 Ma Xiaojun <damage3025@gmail.com>
# Copyright (c) 2012 mozbugbox <mozbugbox@yahoo.com.au>
# Copyright (c) 2014-2020 Mike FABIAN <mfabian@redhat.com>
#
# This library is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 2.1 of the License, or
# (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this library.  If not, see <http://www.gnu.org/licenses/>

'''
The setup tool for ibus-table.
'''

# “Wrong continued indentation”: pylint: disable=bad-continuation

import sys
import os
import re
import html
import signal
import argparse
import locale
import copy
import logging
import logging.handlers
import dbus
import dbus.service

from gi import require_version
require_version('Gio', '2.0')
from gi.repository import Gio
require_version('GLib', '2.0')
from gi.repository import GLib

# set_prgname before importing other modules to show the name in warning
# messages when import modules are failed. E.g. Gtk.
GLib.set_application_name('IBus Table Preferences')
# This makes gnome-shell load the .desktop file when running under Wayland:
GLib.set_prgname('ibus-setup-table')

require_version('Gdk', '3.0')
from gi.repository import Gdk
require_version('Gtk', '3.0')
from gi.repository import Gtk
require_version('Pango', '1.0')
from gi.repository import Pango
require_version('IBus', '1.0')
from gi.repository import IBus
from i18n import _, init as i18n_init

sys.path = [sys.path[0]+'/../engine'] + sys.path
import tabsqlitedb
import ibus_table_location
import it_util

LOGGER = logging.getLogger('ibus-table')

GTK_VERSION = (Gtk.get_major_version(),
               Gtk.get_minor_version(),
               Gtk.get_micro_version())

PARSER = argparse.ArgumentParser(
    description='ibus-table setup tool')
PARSER.add_argument(
    '-n', '--engine-name',
    action='store',
    type=str,
    dest='engine_name',
    default='',
    help=('Set the name of the engine, for example “table:cangjie3” '
          'or just “cangjie3”. Default: "%(default)s". '
          'If this option is not used, the value of the environment '
          'variable IBUS_ENGINE_NAME is tried instead. '
          'If the variable IBUS_ENGINE_NAME is also not set or empty, '
          'this help is printed.'))
PARSER.add_argument(
    '-q', '--no-debug',
    action='store_true',
    default=False,
    help=('Do not write log file '
          + '~/.cache/ibus-table/setup-debug.log, '
          + 'default: %(default)s'))

_ARGS = PARSER.parse_args()

class SetupUI(Gtk.Window):
    '''
    User interface of the setup tool
    '''
    def __init__(self, engine_name=''):
        self._engine_name = engine_name
        Gtk.Window.__init__(
            self,
            title='码 IBus Table '
            + self._engine_name + ' '
            + _('Preferences'))
        Gtk.Window.set_default_icon_from_file(
            os.path.join(
                ibus_table_location.data(), 'icons', 'ibus-table.svg'))
        self.set_name('IBusTablePreferences')
        self.set_modal(True)
        style_provider = Gtk.CssProvider()
        style_provider.load_from_data(
            b'''
            #IBusTablePreferences {
            }
            row { /* This is for listbox rows */
                border-style: groove;
                border-width: 0.05px;
            }
            ''')
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            style_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        database_filename = os.path.join(
            os.path.join(ibus_table_location.data(), 'tables'),
            self._engine_name + '.db')
        if not os.path.exists(database_filename):
            LOGGER.error('Cannot open database %s', database_filename)
            sys.exit(1)
        self.tabsqlitedb = tabsqlitedb.TabSqliteDb(
            filename=database_filename,
            user_db=None,
            create_database=False)

        self.__is_chinese = False
        self.__is_cjk = False
        languages = self.tabsqlitedb.ime_properties.get('languages')
        if languages:
            languages = languages.split(',')
            for language in languages:
                if language.strip().startswith('zh'):
                    self.__is_chinese = True
                for lang in ['zh', 'ja', 'ko']:
                    if language.strip().startswith(lang):
                        self.__is_cjk = True
        self.__user_can_define_phrase = False
        user_can_define_phrase = self.tabsqlitedb.ime_properties.get(
            'user_can_define_phrase')
        if user_can_define_phrase:
            self.__user_can_define_phrase = (
                user_can_define_phrase.lower() == 'true')
        self.__rules = self.tabsqlitedb.ime_properties.get('rules')

        self._gsettings = Gio.Settings(
            schema='org.freedesktop.ibus.engine.table',
            path='/org/freedesktop/ibus/engine/table/%s/' % self._engine_name)
        self._fill_settings_dict()
        self.set_title(
            '码 IBus Table '
            + self._engine_name + ' '
            + _('Preferences'))
        # https://tronche.com/gui/x/icccm/sec-4.html#WM_CLASS
        # gnome-shell seems to use the first argument of set_wmclass()
        # to find the .desktop file. If the .desktop file can be
        # found, the name shown by gnome-shell in the top bar comes
        # from that .desktop file and the icon to show is also read
        # from that .desktop file. If the .desktop file cannot be
        # found, the second argument of set_wmclass() is shown by
        # gnome-shell in the top bar.
        #
        # It only works like this when gnome-shell runs under Xorg
        # though, under Wayland things are different.
        self.set_wmclass(
            'ibus-setup-table', 'IBus Table Preferences')

        self.connect('destroy-event', self.on_destroy_event)
        self.connect('delete-event', self.on_delete_event)

        self._main_container = Gtk.VBox()
        self.add(self._main_container)
        self._notebook = Gtk.Notebook()
        self._notebook.set_visible(True)
        self._notebook.set_can_focus(False)
        self._notebook.set_scrollable(True)
        self._notebook.set_hexpand(True)
        self._notebook.set_vexpand(True)
        self._main_container.pack_start(self._notebook, True, True, 0)
        self._dialog_action_area = Gtk.ButtonBox()
        self._dialog_action_area.set_visible(True)
        self._dialog_action_area.set_can_focus(False)
        self._dialog_action_area.set_hexpand(True)
        self._dialog_action_area.set_vexpand(False)
        self._dialog_action_area.set_layout(Gtk.ButtonBoxStyle.EDGE)
        self._main_container.pack_end(self._dialog_action_area, True, True, 0)
        self._about_button = Gtk.Button(label=_('About'))
        self._about_button.connect('clicked', self.on_about_button_clicked)
        self._dialog_action_area.add(self._about_button)
        self._restore_all_defaults_button = Gtk.Button()
        self._restore_all_defaults_button_label = Gtk.Label()
        self._restore_all_defaults_button_label.set_text(
            _('Restore all defaults'))
        self._restore_all_defaults_button.add(
            self._restore_all_defaults_button_label)
        self._restore_all_defaults_button.connect(
            'clicked', self.on_restore_all_defaults_button_clicked)
        self._dialog_action_area.add(self._restore_all_defaults_button)
        self._close_button = Gtk.Button()
        self._close_button_label = Gtk.Label()
        self._close_button_label.set_text_with_mnemonic(_('_Close'))
        self._close_button.add(self._close_button_label)
        self._close_button.connect('clicked', self.on_close_clicked)
        self._dialog_action_area.add(self._close_button)

        grid_border_width = 10
        grid_row_spacing = 10
        grid_column_spacing = 10

        self._options_grid = Gtk.Grid()
        self._options_grid.set_visible(True)
        self._options_grid.set_can_focus(False)
        self._options_grid.set_border_width(grid_border_width)
        self._options_grid.set_row_spacing(grid_row_spacing)
        self._options_grid.set_column_spacing(grid_column_spacing)
        self._options_grid.set_row_homogeneous(False)
        self._options_grid.set_column_homogeneous(True)
        self._options_grid.set_hexpand(True)
        self._options_grid.set_vexpand(False)
        self._options_label = Gtk.Label()
        # Translators: This is the label of a tab in the setup tool.
        # Here the user can set up some options which influence the
        # behaviour of ibus-table.
        self._options_label.set_text(_('Settings'))

        self._options_details_grid = Gtk.Grid()
        self._options_details_grid.set_visible(True)
        self._options_details_grid.set_can_focus(False)
        self._options_details_grid.set_border_width(grid_border_width)
        self._options_details_grid.set_row_spacing(grid_row_spacing)
        self._options_details_grid.set_column_spacing(grid_column_spacing)
        self._options_details_grid.set_row_homogeneous(False)
        self._options_details_grid.set_column_homogeneous(True)
        self._options_details_grid.set_hexpand(True)
        self._options_details_grid.set_vexpand(False)
        self._options_details_label = Gtk.Label()
        # Translators: This is the label of a tab in the setup tool.
        # Here the user can set up some options which influence how
        # ibus-typing-booster looks like, i.e. something like whether
        # extra info should be shown on top of the candidate list and
        # how many entries one page of the candidate list should have.
        # Also one can choose here which colours to use for different
        # types of candidates (candidates from the user database, from
        # dictionaries, or from spellchecking) and/or whether
        # diffent types of candidates should be marked with labels.
        self._options_details_label.set_text(_('Details'))

        self._keybindings_vbox = Gtk.VBox()
        margin = 10
        self._keybindings_vbox.set_margin_start(margin)
        self._keybindings_vbox.set_margin_end(margin)
        self._keybindings_vbox.set_margin_top(margin)
        self._keybindings_vbox.set_margin_bottom(margin)
        self._keybindings_label = Gtk.Label()
        # Translators: This is the label of a tab in the setup tool.
        # Here the user can customize the key bindings to execute
        # certain commands of ibus-table. For example which key to use
        # to commit, which key to use to move to the next candidate
        # etc...
        self._keybindings_label.set_text(_('Key bindings'))

        self._notebook.append_page(
            self._options_grid,
            self._options_label)
        self._notebook.append_page(
            self._options_details_grid,
            self._options_details_label)
        self._notebook.append_page(
            self._keybindings_vbox,
            self._keybindings_label)

        self._initial_state_section_heading_label = Gtk.Label()
        self._initial_state_section_heading_label.set_text(
            '<b>' + _('Initial state') + '</b>')
        self._initial_state_section_heading_label.set_use_markup(True)
        self._initial_state_section_heading_label.set_xalign(0)
        self._options_grid.attach(
            self._initial_state_section_heading_label, 0, 0, 2, 1)

        self._input_mode_label = Gtk.Label()
        self._input_mode_label.set_text(
            # Translators: A combobox to choose the input mode
            # (“Direct input” or “Table input”)
            _('Input mode'))
        self._input_mode_label.set_tooltip_text(
            # Translators: A tooltip for the label of the combobox to
            # choose the input mode (“Direct input” or “Table input”).
            _('“Direct input” is almost the same as if the\n'
              'input method were off, i.e. not used at all, most\n'
              'characters just get passed to the application.\n'
              'But some conversion between fullwidth and\n'
              'halfwidth may still happen in direct input mode.\n'
              '“Table input” means the input method is on.'))
        self._input_mode_label.set_xalign(0)
        self._options_grid.attach(
            self._input_mode_label, 0, 1, 1, 1)

        self._input_mode_combobox = Gtk.ComboBox()
        self._input_mode_store = Gtk.ListStore(str, int)
        self._input_mode_store.append(
            # Translators: This is the setting to use 'Direct input'
            # which means that almost all keys are passed directly
            # to the application, in other words the input method
            # is (mostly) switched off.
            [_('Direct input'), 0])
        self._input_mode_store.append(
            # Translators: This is the setting to use a 'Table input'
            # which means that the keys typed are transformed according
            # to the table used, in other words the input method is
            # switched on.
            [_('Table input'), 1])
        self._input_mode_combobox.set_model(
            self._input_mode_store)
        renderer_text = Gtk.CellRendererText()
        self._input_mode_combobox.pack_start(
            renderer_text, True)
        self._input_mode_combobox.add_attribute(
            renderer_text, "text", 0)
        for index, item in enumerate(self._input_mode_store):
            if self._settings_dict['inputmode']['user'] == item[1]:
                self._input_mode_combobox.set_active(index)
        self._options_grid.attach(
            self._input_mode_combobox, 1, 1, 1, 1)
        self._input_mode_combobox.connect(
            "changed",
            self.on_input_mode_combobox_changed)

        self._chinese_mode_label = Gtk.Label()
        self._chinese_mode_label.set_text(
            # Translators: A combobox to choose the variant of
            # Chinese which should be preferred.
            _('Chinese mode:'))
        self._chinese_mode_label.set_tooltip_text(
            # Translators: A tooltip for the label of the combobox to
            # choose which variant of Chinese should be preferred.
            _('“Simplified Chinese” shows only characters \n'
              'used in simplified Chinese. “Traditional Chinese”\n'
              'shows only characters used in traditional Chinese.\n'
              '“Simplified Chinese before traditional” shows all\n'
              'characters but puts the simplified characters higher\n'
              'up in the candidate list. “Traditional Chinese before\n'
              'simplified” puts the traditional characters higher up\n'
              'in the candidate list. “All characters” just shows all\n'
              'matches without any particular filtering on traditional\n'
              'versus simplified Chinese.'))
        self._chinese_mode_label.set_xalign(0)
        self._options_grid.attach(
            self._chinese_mode_label, 0, 2, 1, 1)

        self._chinese_mode_combobox = Gtk.ComboBox()
        if not self.__is_chinese:
            self._chinese_mode_combobox.set_button_sensitivity(
                Gtk.SensitivityType.OFF)
        self._chinese_mode_store = Gtk.ListStore(str, int)
        self._chinese_mode_store.append(
            # Translators: This is the setting to use only
            # simplified Chinese
            [_('Simplified Chinese'), 0])
        self._chinese_mode_store.append(
            # Translators: This is the setting to use only
            # traditional Chinese
            [_('Traditional Chinese'), 1])
        self._chinese_mode_store.append(
            # Translators: This is the setting to use both
            # simplified and traditional Chinese but prefer
            # simplified Chinese
            [_('Simplified Chinese before traditional'), 2])
        self._chinese_mode_store.append(
            # Translators: This is the setting to use both
            # simplified and traditional Chinese but prefer
            # traditional Chinese
            [_('Traditional Chinese before simplified'), 3])
        self._chinese_mode_store.append(
            # Translators: This is the setting to use both
            # simplified and traditional Chinese in no
            # particular order
            [_('All Chinese characters'), 4])
        self._chinese_mode_combobox.set_model(
            self._chinese_mode_store)
        renderer_text = Gtk.CellRendererText()
        self._chinese_mode_combobox.pack_start(
            renderer_text, True)
        self._chinese_mode_combobox.add_attribute(
            renderer_text, "text", 0)
        for index, item in enumerate(self._chinese_mode_store):
            if self._settings_dict['chinesemode']['user'] == item[1]:
                self._chinese_mode_combobox.set_active(index)
        self._options_grid.attach(
            self._chinese_mode_combobox, 1, 2, 1, 1)
        self._chinese_mode_combobox.connect(
            "changed",
            self.on_chinese_mode_combobox_changed)

        self._table_full_width_letter_mode_label = Gtk.Label()
        self._table_full_width_letter_mode_label.set_text(
            # Translators: A combobox to choose the letter width
            # while in “Table input” mode.
            _('Table input letter width:'))
        self._table_full_width_letter_mode_label.set_tooltip_text(
            # Translators: A tooltip for the label of the combobox to
            # choose the letter width while in “Table input” mode.
            _('Whether to use fullwidth or halfwidth\n'
              'letters in table input mode.'))
        self._table_full_width_letter_mode_label.set_xalign(0)
        self._options_grid.attach(
            self._table_full_width_letter_mode_label, 0, 3, 1, 1)

        self._table_full_width_letter_mode_combobox = Gtk.ComboBox()
        if not self.__is_cjk:
            self._table_full_width_letter_mode_combobox.set_button_sensitivity(
                Gtk.SensitivityType.OFF)
        self._table_full_width_letter_mode_store = Gtk.ListStore(str, bool)
        self._table_full_width_letter_mode_store.append(
            # Translators: This is the mode to use half width letters
            # while in “Table input” mode.
            [_('Half'), False])
        self._table_full_width_letter_mode_store.append(
            # Translators: This is the mode to use full width letters
            # while in “Table input” mode.
            [_('Full'), True])
        self._table_full_width_letter_mode_combobox.set_model(
            self._table_full_width_letter_mode_store)
        renderer_text = Gtk.CellRendererText()
        self._table_full_width_letter_mode_combobox.pack_start(
            renderer_text, True)
        self._table_full_width_letter_mode_combobox.add_attribute(
            renderer_text, "text", 0)
        for index, item in enumerate(self._table_full_width_letter_mode_store):
            if self._settings_dict['tabdeffullwidthletter']['user'] == item[1]:
                self._table_full_width_letter_mode_combobox.set_active(index)
        self._options_grid.attach(
            self._table_full_width_letter_mode_combobox, 1, 3, 1, 1)
        self._table_full_width_letter_mode_combobox.connect(
            "changed",
            self.on_table_full_width_letter_mode_combobox_changed)

        self._table_full_width_punctuation_mode_label = Gtk.Label()
        self._table_full_width_punctuation_mode_label.set_text(
            # Translators: A combobox to choose the punctuation width
            # while in “Table input” mode.
            _('Table input punctuation width:'))
        self._table_full_width_punctuation_mode_label.set_tooltip_text(
            # Translators: A tooltip for the label of the combobox to
            # choose the punctuation width while in “Table input” mode.
            _('Whether to use fullwidth or halfwidth\n'
              'punctuation in table input mode.'))
        self._table_full_width_punctuation_mode_label.set_xalign(0)
        self._options_grid.attach(
            self._table_full_width_punctuation_mode_label, 0, 4, 1, 1)

        self._table_full_width_punctuation_mode_combobox = Gtk.ComboBox()
        if not self.__is_cjk:
            self._table_full_width_punctuation_mode_combobox.set_button_sensitivity(
                Gtk.SensitivityType.OFF)
        self._table_full_width_punctuation_mode_store = Gtk.ListStore(
            str, bool)
        self._table_full_width_punctuation_mode_store.append(
            # Translators: This is the mode to use half width punctuation
            # while in “Table input” mode.
            [_('Half'), False])
        self._table_full_width_punctuation_mode_store.append(
            # Translators: This is the mode to use full width punctuation
            # while in “Table input” mode.
            [_('Full'), True])
        self._table_full_width_punctuation_mode_combobox.set_model(
            self._table_full_width_punctuation_mode_store)
        renderer_text = Gtk.CellRendererText()
        self._table_full_width_punctuation_mode_combobox.pack_start(
            renderer_text, True)
        self._table_full_width_punctuation_mode_combobox.add_attribute(
            renderer_text, "text", 0)
        for index, item in enumerate(
                self._table_full_width_punctuation_mode_store):
            if self._settings_dict['tabdeffullwidthpunct']['user'] == item[1]:
                self._table_full_width_punctuation_mode_combobox.set_active(
                    index)
        self._options_grid.attach(
            self._table_full_width_punctuation_mode_combobox, 1, 4, 1, 1)
        self._table_full_width_punctuation_mode_combobox.connect(
            "changed",
            self.on_table_full_width_punctuation_mode_combobox_changed)

        self._direct_full_width_letter_mode_label = Gtk.Label()
        self._direct_full_width_letter_mode_label.set_text(
            # Translators: A combobox to choose the letter width
            # while in “Direct input” mode.
            _('Direct input letter width:'))
        self._direct_full_width_letter_mode_label.set_tooltip_text(
            # Translators: A tooltip for the label of the combobox to
            # choose the letter width while in “Direct input” mode.
            _('Whether to use fullwidth or halfwidth\n'
              'letters in direct input mode.'))
        self._direct_full_width_letter_mode_label.set_xalign(0)
        self._options_grid.attach(
            self._direct_full_width_letter_mode_label, 0, 5, 1, 1)

        self._direct_full_width_letter_mode_combobox = Gtk.ComboBox()
        if not self.__is_cjk:
            self._direct_full_width_letter_mode_combobox.set_button_sensitivity(
                Gtk.SensitivityType.OFF)
        self._direct_full_width_letter_mode_store = Gtk.ListStore(str, bool)
        self._direct_full_width_letter_mode_store.append(
            # Translators: This is the mode to use half width letters
            # while in “Direct input” mode.
            [_('Half'), False])
        self._direct_full_width_letter_mode_store.append(
            # Translators: This is the mode to use full width letters
            # while in “Direct input” mode.
            [_('Full'), True])
        self._direct_full_width_letter_mode_combobox.set_model(
            self._direct_full_width_letter_mode_store)
        renderer_text = Gtk.CellRendererText()
        self._direct_full_width_letter_mode_combobox.pack_start(
            renderer_text, True)
        self._direct_full_width_letter_mode_combobox.add_attribute(
            renderer_text, "text", 0)
        for index, item in enumerate(
                self._direct_full_width_letter_mode_store):
            if self._settings_dict['endeffullwidthletter']['user'] == item[1]:
                self._direct_full_width_letter_mode_combobox.set_active(index)
        self._options_grid.attach(
            self._direct_full_width_letter_mode_combobox, 1, 5, 1, 1)
        self._direct_full_width_letter_mode_combobox.connect(
            "changed",
            self.on_direct_full_width_letter_mode_combobox_changed)

        self._direct_full_width_punctuation_mode_label = Gtk.Label()
        self._direct_full_width_punctuation_mode_label.set_text(
            # Translators: A combobox to choose the punctuation width
            # while in “Direct input” mode.
            _('Direct input punctuation width:'))
        self._direct_full_width_punctuation_mode_label.set_tooltip_text(
            # Translators: A tooltip for the label of the combobox to
            # choose the punctuation width while in “Direct input” mode.
            _('Whether to use fullwidth or halfwidth\n'
              'punctuation in direct input mode.'))
        self._direct_full_width_punctuation_mode_label.set_xalign(0)
        self._options_grid.attach(
            self._direct_full_width_punctuation_mode_label, 0, 6, 1, 1)

        self._direct_full_width_punctuation_mode_combobox = Gtk.ComboBox()
        if not self.__is_cjk:
            self._direct_full_width_punctuation_mode_combobox.set_button_sensitivity(
                Gtk.SensitivityType.OFF)
        self._direct_full_width_punctuation_mode_store = Gtk.ListStore(
            str, bool)
        self._direct_full_width_punctuation_mode_store.append(
            # Translators: This is the mode to use half width punctuation
            # while in “Direct input” mode.
            [_('Half'), False])
        self._direct_full_width_punctuation_mode_store.append(
            # Translators: This is the mode to use full width punctuation
            # while in “Direct input” mode.
            [_('Full'), True])
        self._direct_full_width_punctuation_mode_combobox.set_model(
            self._direct_full_width_punctuation_mode_store)
        renderer_text = Gtk.CellRendererText()
        self._direct_full_width_punctuation_mode_combobox.pack_start(
            renderer_text, True)
        self._direct_full_width_punctuation_mode_combobox.add_attribute(
            renderer_text, "text", 0)
        for index, item in enumerate(
                self._direct_full_width_punctuation_mode_store):
            if self._settings_dict['endeffullwidthpunct']['user'] == item[1]:
                self._direct_full_width_punctuation_mode_combobox.set_active(
                    index)
        self._options_grid.attach(
            self._direct_full_width_punctuation_mode_combobox, 1, 6, 1, 1)
        self._direct_full_width_punctuation_mode_combobox.connect(
            "changed",
            self.on_direct_full_width_punctuation_mode_combobox_changed)

        self._candidate_list_section_heading_label = Gtk.Label()
        self._candidate_list_section_heading_label.set_text(
            '<b>' + _('Candidate list') + '</b>')
        self._candidate_list_section_heading_label.set_use_markup(True)
        self._candidate_list_section_heading_label.set_xalign(0)
        self._options_grid.attach(
            self._candidate_list_section_heading_label, 0, 7, 2, 1)

        self._always_show_lookup_label = Gtk.Label()
        self._always_show_lookup_label.set_text(
            # Translators: A combobox to choose whether
            # a candidate list should be shown or hidden.
            # For Chinese input methods one usually wants the
            # candidate list to be shown. But for some non-Chinese
            # input methods like the Russian “translit”, hiding
            # the candidate lists is better.
            _('Show candidate list'))
        self._always_show_lookup_label.set_tooltip_text(
            # Translit: A tooltip for the label of the combobox to
            # choose whether a candidate list should be shown or
            # hidden.
            _('Whether candidate lists should be shown or hidden.\n'
              'For Chinese input methods one usually wants the\n'
              'candidate lists to be shown. But for some non-Chinese\n'
              'input methods like the Russian “translit”, hiding the\n'
              'candidate lists is better.'))
        self._always_show_lookup_label.set_xalign(0)
        self._options_grid.attach(
            self._always_show_lookup_label, 0, 8, 1, 1)

        self._always_show_lookup_combobox = Gtk.ComboBox()
        self._always_show_lookup_store = Gtk.ListStore(str, bool)
        self._always_show_lookup_store.append(
            # Translators: This is the setting to avoid showing
            # candidate lists.
            [_('No'), False])
        self._always_show_lookup_store.append(
            # Translators: This is the setting to show
            # candidate lists.
            [_('Yes'), True])
        self._always_show_lookup_combobox.set_model(
            self._always_show_lookup_store)
        renderer_text = Gtk.CellRendererText()
        self._always_show_lookup_combobox.pack_start(
            renderer_text, True)
        self._always_show_lookup_combobox.add_attribute(
            renderer_text, "text", 0)
        for index, item in enumerate(self._always_show_lookup_store):
            if self._settings_dict['alwaysshowlookup']['user'] == item[1]:
                self._always_show_lookup_combobox.set_active(index)
        self._options_grid.attach(
            self._always_show_lookup_combobox, 1, 8, 1, 1)
        self._always_show_lookup_combobox.connect(
            "changed",
            self.on_always_show_lookup_combobox_changed)

        self._lookup_table_orientation_label = Gtk.Label()
        self._lookup_table_orientation_label.set_text(
            # Translators: A combobox to choose whether the candidate
            # window should be drawn horizontally or vertically.
            _('Orientation:'))
        self._lookup_table_orientation_label.set_tooltip_text(
            # Translators: A tooltip for the label of the combobox to
            # choose whether the candidate window should be drawn
            # horizontally or vertically.
            _('Whether the lookup table showing the candidates\n'
              'should be vertical or horizontal.'))
        self._lookup_table_orientation_label.set_xalign(0)
        self._options_grid.attach(
            self._lookup_table_orientation_label, 0, 9, 1, 1)

        self._lookup_table_orientation_combobox = Gtk.ComboBox()
        self._lookup_table_orientation_store = Gtk.ListStore(str, int)
        self._lookup_table_orientation_store.append(
            [_('Horizontal'), int(IBus.Orientation.HORIZONTAL)])
        self._lookup_table_orientation_store.append(
            [_('Vertical'), int(IBus.Orientation.VERTICAL)])
        self._lookup_table_orientation_store.append(
            [_('System default'), int(IBus.Orientation.SYSTEM)])
        self._lookup_table_orientation_combobox.set_model(
            self._lookup_table_orientation_store)
        renderer_text = Gtk.CellRendererText()
        self._lookup_table_orientation_combobox.pack_start(
            renderer_text, True)
        self._lookup_table_orientation_combobox.add_attribute(
            renderer_text, "text", 0)
        for index, item in enumerate(self._lookup_table_orientation_store):
            if (self._settings_dict['lookuptableorientation']['user']
                == item[1]):
                self._lookup_table_orientation_combobox.set_active(index)
        self._options_grid.attach(
            self._lookup_table_orientation_combobox, 1, 9, 1, 1)
        self._lookup_table_orientation_combobox.connect(
            "changed",
            self.on_lookup_table_orientation_combobox_changed)

        self._page_size_label = Gtk.Label()
        # Translators: Here one can choose how many suggestion
        # candidates to show in one page of the candidate list.
        self._page_size_label.set_text(_('Page size:'))
        self._page_size_label.set_tooltip_text(
            # Translators: A tooltip for the label of the adjustment
            # for the number of candidates to show in one page of the
            # candidate list.
            _('The maximum number of candidates in\n'
              'one page of the lookup table. You can switch\n'
              'pages in the lookup table using the page up/down\n'
              'keys or the arrow up/down keys.'))
        self._page_size_label.set_xalign(0)
        self._options_grid.attach(
            self._page_size_label, 0, 10, 1, 1)

        self._page_size_adjustment = Gtk.SpinButton()
        self._page_size_adjustment.set_visible(True)
        self._page_size_adjustment.set_can_focus(True)
        self._page_size_adjustment.set_increments(1.0, 1.0)
        self._page_size_adjustment.set_range(1.0, 10.0)
        self._options_grid.attach(
            self._page_size_adjustment, 1, 10, 1, 1)
        self._page_size_adjustment.set_value(
            self._settings_dict['lookuptablepagesize']['user'])
        self._page_size_adjustment.connect(
            'value-changed', self.on_page_size_adjustment_value_changed)

        self._keybindings_label = Gtk.Label()
        self._keybindings_label.set_text(
            '<b>' + _('Current key bindings:') + '</b>')
        self._keybindings_label.set_use_markup(True)
        self._keybindings_label.set_margin_start(margin)
        self._keybindings_label.set_margin_end(margin)
        self._keybindings_label.set_margin_top(margin)
        self._keybindings_label.set_margin_bottom(margin)
        self._keybindings_label.set_hexpand(False)
        self._keybindings_label.set_vexpand(False)
        self._keybindings_label.set_xalign(0)
        self._keybindings_treeview_scroll = Gtk.ScrolledWindow()
        self._keybindings_treeview_scroll.set_can_focus(False)
        self._keybindings_treeview_scroll.set_hexpand(False)
        self._keybindings_treeview_scroll.set_vexpand(True)
        #self._keybindings_treeview_scroll.set_shadow_type(in)
        self._keybindings_treeview = Gtk.TreeView()
        self._keybindings_treeview_model = Gtk.ListStore(str, str)
        self._keybindings_treeview.set_model(self._keybindings_treeview_model)

        user_keybindings = self._settings_dict['keybindings']['user']
        for command in sorted(user_keybindings):
            self._keybindings_treeview_model.append(
                (command, repr(user_keybindings[command])))
        self._keybindings_treeview.append_column(
            Gtk.TreeViewColumn(
                # Translators: Column heading of the table listing the
                # existing key bindings
                _('Command'),
                Gtk.CellRendererText(),
                text=0))
        self._keybindings_treeview.append_column(
            Gtk.TreeViewColumn(
                # Translators: Column heading of the table listing the
                # existing key bindings
                _('Key bindings'),
                Gtk.CellRendererText(),
                text=1))
        self._keybindings_treeview.get_selection().connect(
            'changed', self.on_keybindings_treeview_row_selected)
        self._keybindings_treeview.connect(
            'row-activated', self.on_keybindings_treeview_row_activated)
        self._keybindings_treeview_scroll.add(self._keybindings_treeview)
        self._keybindings_vbox.pack_start(
            self._keybindings_label, False, False, 0)
        self._keybindings_vbox.pack_start(
            self._keybindings_treeview_scroll, True, True, 0)
        self._keybindings_action_area = Gtk.ButtonBox()
        self._keybindings_action_area.set_can_focus(False)
        self._keybindings_action_area.set_layout(Gtk.ButtonBoxStyle.START)
        self._keybindings_vbox.pack_start(
            self._keybindings_action_area, False, False, 0)
        self._keybindings_edit_button = Gtk.Button()
        self._keybindings_edit_button_label = Gtk.Label()
        self._keybindings_edit_button_label.set_text(
            _('Edit'))
        self._keybindings_edit_button.add(
            self._keybindings_edit_button_label)
        self._keybindings_edit_button.set_tooltip_text(
            # Translators: A tooltip for the button to edit
            # the keybindings for the selected command.
            _('Edit the key bindings for the selected command'))
        self._keybindings_edit_button.set_sensitive(False)
        self._keybindings_edit_button.connect(
            'clicked', self.on_keybindings_edit_button_clicked)
        self._keybindings_default_button = Gtk.Button()
        self._keybindings_default_button_label = Gtk.Label()
        self._keybindings_default_button_label.set_text(
            _('Set to default'))
        self._keybindings_default_button.add(
            self._keybindings_default_button_label)
        self._keybindings_default_button.set_tooltip_text(
            # Translators: A tooltip for the button to set
            # the default key bindings for the selected command.
            _('Set default key bindings for the selected command'))
        self._keybindings_default_button.set_sensitive(False)
        self._keybindings_default_button.connect(
            'clicked', self.on_keybindings_default_button_clicked)
        self._keybindings_all_default_button = Gtk.Button()
        self._keybindings_all_default_button_label = Gtk.Label()
        self._keybindings_all_default_button_label.set_text(
            _('Set all to default'))
        self._keybindings_all_default_button.add(
            self._keybindings_all_default_button_label)
        self._keybindings_all_default_button.set_tooltip_text(
            # Translators: A tooltip for the button to set the
            # key bindings to default for all commands.
            _('Set default key bindings for all commands'))
        self._keybindings_all_default_button.set_sensitive(True)
        self._keybindings_all_default_button.connect(
            'clicked', self.on_keybindings_all_default_button_clicked)
        self._keybindings_action_area.add(self._keybindings_edit_button)
        self._keybindings_action_area.add(self._keybindings_default_button)
        self._keybindings_action_area.add(self._keybindings_all_default_button)
        self._keybindings_selected_command = ''
        self._keybindings_edit_popover_selected_keybinding = ''
        self._keybindings_edit_popover_selected_keybinding_index = -1
        self._keybindings_edit_popover_listbox = None
        self._keybindings_edit_popover = None
        self._keybindings_edit_popover_scroll = None
        self._keybindings_edit_popover_add_button = None
        self._keybindings_edit_popover_remove_button = None
        self._keybindings_edit_popover_default_button = None

        self._onechar_mode_label = Gtk.Label()
        self._onechar_mode_label.set_text(
            # Translators: A combobox to choose whether only single
            # character candidates should be shown.
            _('Compose:'))
        self._onechar_mode_label.set_tooltip_text(
            # Translators: A tooltip for label of the combobox to
            # choose whether only single character candidates should
            # be shown.
            _('If this is set to “single char”, only single\n'
              'character candidates will be shown. If it is\n'
              'set to “Phrase” candidates consisting of\n'
              'several characters may be shown.'))
        self._onechar_mode_label.set_xalign(0)
        self._options_details_grid.attach(
            self._onechar_mode_label, 0, 0, 1, 1)

        self._onechar_mode_combobox = Gtk.ComboBox()
        if not self.__is_cjk:
            self._onechar_mode_combobox.set_button_sensitivity(
                Gtk.SensitivityType.OFF)
        self._onechar_mode_store = Gtk.ListStore(str, int)
        self._onechar_mode_store.append(
            [_('Phrase'), False])
        self._onechar_mode_store.append(
            [_('Single Char'), True])
        self._onechar_mode_combobox.set_model(
            self._onechar_mode_store)
        renderer_text = Gtk.CellRendererText()
        self._onechar_mode_combobox.pack_start(
            renderer_text, True)
        self._onechar_mode_combobox.add_attribute(
            renderer_text, "text", 0)
        for index, item in enumerate(self._onechar_mode_store):
            if self._settings_dict['onechar']['user'] == item[1]:
                self._onechar_mode_combobox.set_active(index)
        self._options_details_grid.attach(
            self._onechar_mode_combobox, 1, 0, 1, 1)
        self._onechar_mode_combobox.connect(
            "changed", self.on_onechar_mode_combobox_changed)

        self._autoselect_mode_label = Gtk.Label()
        self._autoselect_mode_label.set_text(
            # Translators: A combobox to choose whether the first
            # candidate will be automatically selected during typing.
            _('Auto select:'))
        self._autoselect_mode_label.set_tooltip_text(
            # Translators: A tooltip for the label of the combobox to
            # choose whether the first candidate will be automatically
            # select during typing.
            _('If set to “Yes”, this does the following 4 things:\n'
              '1) When typing “Return”, commit the \n'
              '   candidate + line-feed\n'
              '2) When typing Tab, commit the candidate\n'
              '3) When committing using a commit key, commit\n'
              '   the candidate + " "\n'
              '4) If typing the next character matches no candidates,\n'
              '   commit the first candidate of the previous match.\n'
              '   (Mostly needed for non-Chinese input methods like\n'
              '   the Russian “translit”)'))
        self._autoselect_mode_label.set_xalign(0)
        self._options_details_grid.attach(
            self._autoselect_mode_label, 0, 1, 1, 1)

        self._autoselect_mode_combobox = Gtk.ComboBox()
        self._autoselect_mode_store = Gtk.ListStore(str, int)
        self._autoselect_mode_store.append(
            [_('No'), False])
        self._autoselect_mode_store.append(
            [_('Yes'), True])
        self._autoselect_mode_combobox.set_model(
            self._autoselect_mode_store)
        renderer_text = Gtk.CellRendererText()
        self._autoselect_mode_combobox.pack_start(
            renderer_text, True)
        self._autoselect_mode_combobox.add_attribute(
            renderer_text, "text", 0)
        for index, item in enumerate(self._autoselect_mode_store):
            if self._settings_dict['autoselect']['user'] == item[1]:
                self._autoselect_mode_combobox.set_active(index)
        self._options_details_grid.attach(
            self._autoselect_mode_combobox, 1, 1, 1, 1)
        self._autoselect_mode_combobox.connect(
            "changed", self.on_autoselect_mode_combobox_changed)

        self._autocommit_mode_label = Gtk.Label()
        self._autocommit_mode_label.set_text(
            # Translators: A combobox to choose whether automatic
            # commits go into the preëdit or into the application
            _('Auto commit mode:'))
        self._autocommit_mode_label.set_tooltip_text(
            # Translators; A tooltip for the label of the combobox to
            # choose whether automatic commits go into the preëdit or
            # into the application.
            _('Committing with the commit keys or with the mouse\n'
              'always commits to the application. This option is about\n'
              '“automatic” commits which may happen when\n'
              'one just continues typing input without committing\n'
              'manually. From time to time, “automatic” commits will\n'
              'happen then.\n'
              '“Direct” means such “automatic” commits go directly\n'
              'into the application, “Normal” means they get committed\n'
              'to preedit.'))
        self._autocommit_mode_label.set_xalign(0)
        self._options_details_grid.attach(
            self._autocommit_mode_label, 0, 2, 1, 1)

        self._autocommit_mode_combobox = Gtk.ComboBox()
        if not self.__user_can_define_phrase or not self.__rules:
            self._autocommit_mode_combobox.set_button_sensitivity(
                Gtk.SensitivityType.OFF)
        self._autocommit_mode_store = Gtk.ListStore(str, int)
        self._autocommit_mode_store.append(
            [_('Normal'), False])
        self._autocommit_mode_store.append(
            [_('Direct'), True])
        self._autocommit_mode_combobox.set_model(
            self._autocommit_mode_store)
        renderer_text = Gtk.CellRendererText()
        self._autocommit_mode_combobox.pack_start(
            renderer_text, True)
        self._autocommit_mode_combobox.add_attribute(
            renderer_text, "text", 0)
        for index, item in enumerate(self._autocommit_mode_store):
            if self._settings_dict['autocommit']['user'] == item[1]:
                self._autocommit_mode_combobox.set_active(index)
        self._options_details_grid.attach(
            self._autocommit_mode_combobox, 1, 2, 1, 1)
        self._autocommit_mode_combobox.connect(
            "changed", self.on_autocommit_mode_combobox_changed)

        self._autowildcard_mode_label = Gtk.Label()
        self._autowildcard_mode_label.set_text(
            # Translators: A combobox to choose whether a wildcard
            # should be automatically appended to the input.
            _('Auto wildcard:'))
        self._autowildcard_mode_label.set_tooltip_text(
            # Translators: A tooltip for the label of the combobox to
            # choose whether a wildcard should be automatically
            # appended to the input.
            _('If yes, a multi wildcard will be automatically\n'
              'appended to the end of the input string.'))
        self._autowildcard_mode_label.set_xalign(0)
        self._options_details_grid.attach(
            self._autowildcard_mode_label, 0, 4, 1, 1)

        self._autowildcard_mode_combobox = Gtk.ComboBox()
        self._autowildcard_mode_store = Gtk.ListStore(str, int)
        self._autowildcard_mode_store.append(
            [_('No'), False])
        self._autowildcard_mode_store.append(
            [_('Yes'), True])
        self._autowildcard_mode_combobox.set_model(
            self._autowildcard_mode_store)
        renderer_text = Gtk.CellRendererText()
        self._autowildcard_mode_combobox.pack_start(
            renderer_text, True)
        self._autowildcard_mode_combobox.add_attribute(
            renderer_text, "text", 0)
        for index, item in enumerate(self._autowildcard_mode_store):
            if self._settings_dict['autowildcard']['user'] == item[1]:
                self._autowildcard_mode_combobox.set_active(index)
        self._options_details_grid.attach(
            self._autowildcard_mode_combobox, 1, 4, 1, 1)
        self._autowildcard_mode_combobox.connect(
            "changed", self.on_autowildcard_mode_combobox_changed)

        self._single_wildcard_char_label = Gtk.Label()
        self._single_wildcard_char_label.set_text(
            # Translators: This single character is a placeholder
            # to match a any single character
            _('Single wildcard character:'))
        self._single_wildcard_char_label.set_tooltip_text(
            # Translators: This is a tooltip for the label of the
            # entry where one can choose the wildcard to match a
            # single character.
            _('The wildcard to match any single character.\n'
              'Type RETURN or ENTER to confirm after changing the wildcard.'))
        self._single_wildcard_char_label.set_xalign(0)
        self._options_details_grid.attach(
            self._single_wildcard_char_label, 0, 5, 1, 1)

        self._single_wildcard_char_entry = Gtk.Entry()
        self._single_wildcard_char_entry.set_max_length(1)
        self._options_details_grid.attach(
            self._single_wildcard_char_entry, 1, 5, 1, 1)
        self._single_wildcard_char_entry.set_text(
            self._settings_dict['singlewildcardchar']['user'])
        self._single_wildcard_char_entry.connect(
            'notify::text', self.on_single_wildcard_char_entry)

        self._multi_wildcard_char_label = Gtk.Label()
        self._multi_wildcard_char_label.set_text(
            # Translators: This single character is a placeholder
            # to match a any number of characters
            _('Multi wildcard character:'))
        self._multi_wildcard_char_label.set_tooltip_text(
            # Translators: This is a tooltip for the label of the
            # entry where one can choose the wildcard to match any
            # number of candidates.
            _('The wildcard used to match any number of characters.\n'
              'Type RETURN or ENTER to confirm after changing the wildcard.'))
        self._multi_wildcard_char_label.set_xalign(0)
        self._options_details_grid.attach(
            self._multi_wildcard_char_label, 0, 6, 1, 1)

        self._multi_wildcard_char_entry = Gtk.Entry()
        self._multi_wildcard_char_entry.set_max_length(1)
        self._options_details_grid.attach(
            self._multi_wildcard_char_entry, 1, 6, 1, 1)
        self._multi_wildcard_char_entry.set_text(
            self._settings_dict['multiwildcardchar']['user'])
        self._multi_wildcard_char_entry.connect(
            'notify::text', self.on_multi_wildcard_char_entry)

        self._use_dark_theme_label = Gtk.Label()
        self._use_dark_theme_label.set_text(
            # Translators: A combobox to choose whether
            # the color scheme for a dark theme should be used.
            _('Use dark theme:'))
        self._use_dark_theme_label.set_tooltip_text(
            # Translators: A tooltip for the label of the combobox to
            # choose whether the color scheme for a dark theme should
            # be used.
            _('If yes, the color scheme for a dark theme will be used.'))
        self._use_dark_theme_label.set_xalign(0)
        self._options_details_grid.attach(
            self._use_dark_theme_label, 0, 10, 1, 1)

        self._use_dark_theme_combobox = Gtk.ComboBoxText()
        self._use_dark_theme_combobox.append("no", _('No'))
        self._use_dark_theme_combobox.append("yes", _('Yes'))
        self.set_dark_theme(self._settings_dict['darktheme']['user'], False)
        self._options_details_grid.attach(
            self._use_dark_theme_combobox, 1, 10, 1, 1)
        self._use_dark_theme_combobox.connect(
            "changed", self.on_use_dark_theme_combobox_changed)

        self._debug_level_label = Gtk.Label()
        self._debug_level_label.set_text(
            # Translators: When the debug level is greater than 0,
            # debug information may be printed to the log file and
            # debug information may also be shown graphically.
            _('Debug level:'))
        self._debug_level_label.set_tooltip_text(
            # Translators: This is a tooltip for the label for the
            # adjustment of the debug level.
            _('When greater than 0, debug information may be '
              'printed to the log file and debug information '
              'may also be shown graphically.'))
        self._debug_level_label.set_xalign(0)
        self._options_details_grid.attach(
            self._debug_level_label, 0, 11, 1, 1)

        self._debug_level_adjustment = Gtk.SpinButton()
        self._debug_level_adjustment.set_visible(True)
        self._debug_level_adjustment.set_can_focus(True)
        self._debug_level_adjustment.set_increments(1.0, 1.0)
        self._debug_level_adjustment.set_range(0.0, 255.0)
        self._options_details_grid.attach(
            self._debug_level_adjustment, 1, 11, 1, 1)
        self._debug_level_adjustment.set_value(
            self._settings_dict['debuglevel']['user'])
        self._debug_level_adjustment.connect(
            'value-changed',
            self.on_debug_level_adjustment_value_changed)

        self.show_all()

        self._notebook.set_current_page(0) # Has to be after show_all()

        self._gsettings.connect('changed', self.on_gsettings_value_changed)

    def _fill_settings_dict(self):
        '''Fill a dictionary with the default and user settings for all
        settings keys.

        The default settings start with the defaults from the
        gsettings schema. Some of these generic default values may be
        overridden by more specific default settings coming from the
        specific database of this table input method. After this
        possible modification from the database we have the final default
        settings for this specific table input method.

        The user settings start with a copy of these final default settings,
        then they are possibly modified by user gsettings.

        Keeping a copy of the default settings in the settings dictionary
        makes it easy to revert some or all settings to the defaults.
        '''
        self._settings_dict = {}

        default_single_wildcard_char = it_util.variant_to_value(
            self._gsettings.get_default_value('singlewildcardchar'))
        if self.tabsqlitedb.ime_properties.get('single_wildcard_char'):
            default_single_wildcard_char = self.tabsqlitedb.ime_properties.get(
                'single_wildcard_char')
        user_single_wildcard_char = it_util.variant_to_value(
            self._gsettings.get_user_value('singlewildcardchar'))
        if user_single_wildcard_char is None:
            user_single_wildcard_char = default_single_wildcard_char

        self._settings_dict['singlewildcardchar'] = {
            'default': default_single_wildcard_char,
            'user': user_single_wildcard_char,
            'set_function': self.set_single_wildcard_char}

        default_multi_wildcard_char = it_util.variant_to_value(
            self._gsettings.get_default_value('multiwildcardchar'))
        if self.tabsqlitedb.ime_properties.get('multi_wildcard_char'):
            default_multi_wildcard_char = self.tabsqlitedb.ime_properties.get(
                'multi_wildcard_char')
        user_multi_wildcard_char = it_util.variant_to_value(
            self._gsettings.get_user_value('multiwildcardchar'))
        if user_multi_wildcard_char is None:
            user_multi_wildcard_char = default_multi_wildcard_char

        self._settings_dict['multiwildcardchar'] = {
            'default': default_multi_wildcard_char,
            'user': user_multi_wildcard_char,
            'set_function': self.set_multi_wildcard_char}

        default_keybindings = it_util.get_default_keybindings(
            self._gsettings, self.tabsqlitedb)
        # copy the updated default keybindings, i.e. the default
        # keybindings for this table, into the user keybindings:
        user_keybindings = copy.deepcopy(default_keybindings)
        user_keybindings_gsettings = it_util.variant_to_value(
            self._gsettings.get_user_value('keybindings'))
        if not user_keybindings_gsettings:
            user_keybindings_gsettings = {}
        it_util.dict_update_existing_keys(
            user_keybindings, user_keybindings_gsettings)

        self._settings_dict['keybindings'] = {
            'default': default_keybindings,
            'user': user_keybindings,
            'set_function': self.set_keybindings}

        default_always_show_lookup = it_util.variant_to_value(
            self._gsettings.get_default_value('alwaysshowlookup'))
        if self.tabsqlitedb.ime_properties.get('always_show_lookup'):
            default_always_show_lookup = (
                self.tabsqlitedb.ime_properties.get(
                    'always_show_lookup').lower() == 'true')
        user_always_show_lookup = it_util.variant_to_value(
            self._gsettings.get_user_value('alwaysshowlookup'))
        if user_always_show_lookup is None:
            user_always_show_lookup = default_always_show_lookup

        self._settings_dict['alwaysshowlookup'] = {
            'default': default_always_show_lookup,
            'user': user_always_show_lookup,
            'set_function': self.set_always_show_lookup}

        default_page_size = it_util.variant_to_value(
            self._gsettings.get_default_value('lookuptablepagesize'))
        for index in range(1, 10):
            if not default_keybindings['commit_candidate_%s' % (index + 1)]:
                default_page_size = min(index, default_page_size)
                break
        user_page_size = it_util.variant_to_value(
            self._gsettings.get_user_value('lookuptablepagesize'))
        if user_page_size is None:
            user_page_size = default_page_size

        self._settings_dict['lookuptablepagesize'] = {
            'default': int(default_page_size),
            'user': int(user_page_size),
            'set_function': self.set_page_size}

        default_lookup_table_orientation = it_util.variant_to_value(
            self._gsettings.get_default_value('lookuptableorientation'))
        default_lookup_table_orientation = self.tabsqlitedb.get_orientation()
        user_lookup_table_orientation = it_util.variant_to_value(
            self._gsettings.get_user_value('lookuptableorientation'))
        if user_lookup_table_orientation is None:
            user_lookup_table_orientation = default_lookup_table_orientation

        self._settings_dict['lookuptableorientation'] = {
            'default': default_lookup_table_orientation,
            'user': user_lookup_table_orientation,
            'set_function': self.set_lookup_table_orientation}

        default_chinese_mode = it_util.variant_to_value(
            self._gsettings.get_default_value('chinesemode'))
        default_chinese_mode = it_util.get_default_chinese_mode(
            self.tabsqlitedb)
        user_chinese_mode = it_util.variant_to_value(
            self._gsettings.get_user_value('chinesemode'))
        if user_chinese_mode is None:
            user_chinese_mode = default_chinese_mode

        self._settings_dict['chinesemode'] = {
            'default': default_chinese_mode,
            'user': user_chinese_mode,
            'set_function': self.set_chinese_mode}

        default_input_mode = it_util.variant_to_value(
            self._gsettings.get_default_value('inputmode'))
        user_input_mode = it_util.variant_to_value(
            self._gsettings.get_value('inputmode'))

        self._settings_dict['inputmode'] = {
            'default': default_input_mode,
            'user': user_input_mode,
            'set_function': self.set_input_mode}

        default_dark_theme = it_util.variant_to_value(
            self._gsettings.get_default_value('darktheme'))
        user_dark_theme = it_util.variant_to_value(
            self._gsettings.get_value('darktheme'))

        self._settings_dict['darktheme'] = {
            'default': default_dark_theme,
            'user': user_dark_theme,
            'set_function': self.set_dark_theme}

        default_debug_level = it_util.variant_to_value(
            self._gsettings.get_default_value('debuglevel'))
        user_debug_level = it_util.variant_to_value(
            self._gsettings.get_value('debuglevel'))

        self._settings_dict['debuglevel'] = {
            'default': default_debug_level,
            'user': user_debug_level,
            'set_function': self.set_debug_level}

        default_table_full_width_letter_mode = it_util.variant_to_value(
            self._gsettings.get_default_value('tabdeffullwidthletter'))
        if self.tabsqlitedb.ime_properties.get('def_full_width_letter'):
            default_table_full_width_letter_mode = (
                self.tabsqlitedb.ime_properties.get(
                    'def_full_width_letter').lower() == 'true')
        user_table_full_width_letter_mode = it_util.variant_to_value(
            self._gsettings.get_user_value('tabdeffullwidthletter'))
        if user_table_full_width_letter_mode is None:
            user_table_full_width_letter_mode = (
                default_table_full_width_letter_mode)

        self._settings_dict['tabdeffullwidthletter'] = {
            'default': default_table_full_width_letter_mode,
            'user': user_table_full_width_letter_mode,
            'set_function': self.set_table_full_width_letter_mode}

        default_table_full_width_punctuation_mode = (
            it_util.variant_to_value(
                self._gsettings.get_default_value('tabdeffullwidthpunct')))
        if self.tabsqlitedb.ime_properties.get('def_full_width_punct'):
            default_table_full_width_punctuation_mode = (
                self.tabsqlitedb.ime_properties.get(
                    'def_full_width_punct').lower() == 'true')
        user_table_full_width_punctuation_mode = it_util.variant_to_value(
            self._gsettings.get_user_value('tabdeffullwidthpunct'))
        if user_table_full_width_punctuation_mode is None:
            user_table_full_width_punctuation_mode = (
                default_table_full_width_punctuation_mode)

        self._settings_dict['tabdeffullwidthpunct'] = {
            'default': default_table_full_width_punctuation_mode,
            'user': user_table_full_width_punctuation_mode,
            'set_function': self.set_table_full_width_punctuation_mode}

        default_direct_full_width_letter_mode = it_util.variant_to_value(
            self._gsettings.get_default_value('endeffullwidthletter'))
        user_direct_full_width_letter_mode = it_util.variant_to_value(
            self._gsettings.get_value('endeffullwidthletter'))

        self._settings_dict['endeffullwidthletter'] = {
            'default': default_direct_full_width_letter_mode,
            'user': user_direct_full_width_letter_mode,
            'set_function': self.set_direct_full_width_letter_mode}

        default_direct_full_width_punctuation_mode = it_util.variant_to_value(
            self._gsettings.get_default_value('endeffullwidthpunct'))
        user_direct_full_width_punctuation_mode = it_util.variant_to_value(
            self._gsettings.get_value('endeffullwidthpunct'))

        self._settings_dict['endeffullwidthpunct'] = {
            'default': default_direct_full_width_punctuation_mode,
            'user': user_direct_full_width_punctuation_mode,
            'set_function': self.set_direct_full_width_punctuation_mode}

        default_onechar_mode = it_util.variant_to_value(
            self._gsettings.get_default_value('onechar'))
        user_onechar_mode = it_util.variant_to_value(
            self._gsettings.get_value('onechar'))

        self._settings_dict['onechar'] = {
            'default': default_onechar_mode,
            'user': user_onechar_mode,
            'set_function': self.set_onechar_mode}

        default_autoselect_mode = it_util.variant_to_value(
            self._gsettings.get_default_value('autoselect'))
        if self.tabsqlitedb.ime_properties.get('auto_select'):
            default_autoselect_mode = (
                self.tabsqlitedb.ime_properties.get(
                    'auto_select').lower() == 'true')
        user_autoselect_mode = it_util.variant_to_value(
            self._gsettings.get_user_value('autoselect'))
        if user_autoselect_mode is None:
            user_autoselect_mode = default_autoselect_mode

        self._settings_dict['autoselect'] = {
            'default': default_autoselect_mode,
            'user': user_autoselect_mode,
            'set_function': self.set_autoselect_mode}

        default_autocommit_mode = it_util.variant_to_value(
            self._gsettings.get_default_value('autocommit'))
        if self.tabsqlitedb.ime_properties.get('auto_commit'):
            default_autocommit_mode = (
                self.tabsqlitedb.ime_properties.get(
                    'auto_commit').lower() == 'true')
        user_autocommit_mode = it_util.variant_to_value(
            self._gsettings.get_user_value('autocommit'))
        if user_autocommit_mode is None:
            user_autocommit_mode = default_autocommit_mode

        self._settings_dict['autocommit'] = {
            'default': default_autocommit_mode,
            'user': user_autocommit_mode,
            'set_function': self.set_autocommit_mode}

        default_autowildcard_mode = it_util.variant_to_value(
            self._gsettings.get_default_value('autowildcard'))
        if self.tabsqlitedb.ime_properties.get('auto_wildcard'):
            default_autowildcard_mode = (
                self.tabsqlitedb.ime_properties.get(
                    'auto_wildcard').lower() == 'true')
        user_autowildcard_mode = it_util.variant_to_value(
            self._gsettings.get_user_value('autowildcard'))
        if user_autowildcard_mode is None:
            user_autowildcard_mode = default_autowildcard_mode

        self._settings_dict['autowildcard'] = {
            'default': default_autowildcard_mode,
            'user': user_autowildcard_mode,
            'set_function': self.set_autowildcard_mode}

    def __run_message_dialog(self, message, message_type=Gtk.MessageType.INFO):
        '''Run a dialog to show an error or warning message'''
        dialog = Gtk.MessageDialog(
            flags=Gtk.DialogFlags.MODAL,
            message_type=message_type,
            buttons=Gtk.ButtonsType.OK,
            message_format=message)
        dialog.run()
        dialog.destroy()

    def _run_are_you_sure_dialog(self, message):
        '''
        Run a dialog to show a “Are you sure?” message.

        Returns Gtk.ResponseType.OK or Gtk.ResponseType.CANCEL
        :rtype: Gtk.ResponseType (enum)
        '''
        confirm_question = Gtk.Dialog(
            title=_('Are you sure?'),
            parent=self)
        confirm_question.add_button(_('_Cancel'), Gtk.ResponseType.CANCEL)
        confirm_question.add_button(_('_OK'), Gtk.ResponseType.OK)
        box = confirm_question.get_content_area()
        label = Gtk.Label()
        label.set_text(
            '<span size="large" color="#ff0000"><b>'
            + html.escape(message)
            + '</b></span>')
        label.set_use_markup(True)
        label.set_max_width_chars(40)
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        label.set_xalign(0)
        margin = 10
        label.set_margin_start(margin)
        label.set_margin_end(margin)
        label.set_margin_top(margin)
        label.set_margin_bottom(margin)
        box.add(label)
        confirm_question.show_all()
        response = confirm_question.run()
        confirm_question.destroy()
        while Gtk.events_pending():
            Gtk.main_iteration()
        return response

    def check_instance(self):
        '''
        Check whether another instance of the setup tool is running already
        '''
        if (dbus.SessionBus().request_name("org.ibus.table")
                != dbus.bus.REQUEST_NAME_REPLY_PRIMARY_OWNER):
            self.__run_message_dialog(
                _("Another instance of this app is already running."),
                Gtk.MessageType.ERROR)
            sys.exit(1)
        else:
            return False

    def on_delete_event(self, *_args):
        '''
        The window has been deleted, probably by the window manager.
        '''
        Gtk.main_quit()

    def on_destroy_event(self, *_args):
        '''
        The window has been destroyed.
        '''
        Gtk.main_quit()

    def on_close_clicked(self, *_args):
        '''
        The button to close the dialog has been clicked.
        '''
        Gtk.main_quit()

    def on_gsettings_value_changed(self, _settings, key):
        '''
        Called when a value in the settings has been changed.

        :param settings: The settings object
        :type settings: Gio.Settings object
        :param key: The key of the setting which has changed
        :type key: String
        '''
        value = it_util.variant_to_value(self._gsettings.get_value(key))
        LOGGER.info('Settings changed: key=%s value=%s\n', key, value)

        if key in self._settings_dict:
            self._settings_dict[key]['set_function'](value,
                                                     update_gsettings=False)
            return
        LOGGER.error('Unknown key\n')
        return

    def on_about_button_clicked(self, _button):
        '''
        The “About” button has been clicked

        :param _button: The “About” button
        :type _button: Gtk.Button object
        '''
        it_util.ItAboutDialog()

    def on_restore_all_defaults_button_clicked(self, _widget):
        '''
        Restore all default settings
        '''
        self._restore_all_defaults_button.set_sensitive(False)
        response = self._run_are_you_sure_dialog(
            # Translators: This is the text in the centre of a small
            # dialog window, trying to confirm whether the user is
            # really sure to restore all default settings.
            _('Do you really want to restore all default settings?'))
        if response == Gtk.ResponseType.OK:
            LOGGER.info('Restoring all defaults.')
            for key in self._settings_dict:
                self._settings_dict[key]['set_function'](
                    self._settings_dict[key]['default'],
                    update_gsettings=True)
                self._settings_dict[key]['set_function'](
                    self._settings_dict[key]['default'],
                    update_gsettings=False)
        else:
            LOGGER.info('Restore all defaults cancelled.')
        self._restore_all_defaults_button.set_sensitive(True)

    def on_single_wildcard_char_entry(self, widget, _property_spec):
        '''
        The character to be used as a single wildcard has been changed.
        '''
        self.set_single_wildcard_char(
            widget.get_text(), update_gsettings=True)

    def on_multi_wildcard_char_entry(self, widget, _property_spec):
        '''
        The character to be used as a multi wildcard has been changed.
        '''
        self.set_multi_wildcard_char(
            widget.get_text(), update_gsettings=True)

    def on_page_size_adjustment_value_changed(self, _widget):
        '''
        The page size of the lookup table has been changed.
        '''
        self.set_page_size(
            self._page_size_adjustment.get_value(), update_gsettings=True)

    def on_lookup_table_orientation_combobox_changed(self, widget):
        '''
        A change of the lookup table orientation has been requested
        with the combobox
        '''
        tree_iter = widget.get_active_iter()
        if tree_iter is not None:
            model = widget.get_model()
            orientation = model[tree_iter][1]
            self.set_lookup_table_orientation(
                orientation, update_gsettings=True)

    def on_input_mode_combobox_changed(self, widget):
        '''
        A change of the input mode has been requested
        with the combobox
        '''
        tree_iter = widget.get_active_iter()
        if tree_iter is not None:
            model = widget.get_model()
            input_mode = model[tree_iter][1]
            self.set_input_mode(
                input_mode, update_gsettings=True)

    def on_chinese_mode_combobox_changed(self, widget):
        '''
        A change of the Chinese mode has been requested
        with the combobox
        '''
        tree_iter = widget.get_active_iter()
        if tree_iter is not None:
            model = widget.get_model()
            input_mode = model[tree_iter][1]
            self.set_chinese_mode(
                input_mode, update_gsettings=True)

    def on_onechar_mode_combobox_changed(self, widget):
        '''
        A change of the onechar mode has been requested
        with the combobox
        '''
        tree_iter = widget.get_active_iter()
        if tree_iter is not None:
            model = widget.get_model()
            mode = model[tree_iter][1]
            self.set_onechar_mode(
                mode, update_gsettings=True)

    def on_autoselect_mode_combobox_changed(self, widget):
        '''
        A change of the autoselect mode has been requested
        with the combobox
        '''
        tree_iter = widget.get_active_iter()
        if tree_iter is not None:
            model = widget.get_model()
            mode = model[tree_iter][1]
            self.set_autoselect_mode(
                mode, update_gsettings=True)

    def on_autocommit_mode_combobox_changed(self, widget):
        '''
        A change of the autocommit mode has been requested
        with the combobox
        '''
        tree_iter = widget.get_active_iter()
        if tree_iter is not None:
            model = widget.get_model()
            mode = model[tree_iter][1]
            self.set_autocommit_mode(
                mode, update_gsettings=True)

    def on_autowildcard_mode_combobox_changed(self, widget):
        '''
        A change of the autocommit mode has been requested
        with the combobox
        '''
        tree_iter = widget.get_active_iter()
        if tree_iter is not None:
            model = widget.get_model()
            mode = model[tree_iter][1]
            self.set_autowildcard_mode(
                mode, update_gsettings=True)

    def on_table_full_width_letter_mode_combobox_changed(self, widget):
        '''
        A change of the letter width when in “Table input” mode has been
        requested with the combobox
        '''
        tree_iter = widget.get_active_iter()
        if tree_iter is not None:
            model = widget.get_model()
            mode = model[tree_iter][1]
            self.set_table_full_width_letter_mode(
                mode, update_gsettings=True)

    def on_table_full_width_punctuation_mode_combobox_changed(self, widget):
        '''
        A change of the letter width when in “Table input” mode has been
        requested with the combobox
        '''
        tree_iter = widget.get_active_iter()
        if tree_iter is not None:
            model = widget.get_model()
            mode = model[tree_iter][1]
            self.set_table_full_width_punctuation_mode(
                mode, update_gsettings=True)

    def on_direct_full_width_letter_mode_combobox_changed(self, widget):
        '''
        A change of the letter width when in “Direct input” mode has been
        requested with the combobox
        '''
        tree_iter = widget.get_active_iter()
        if tree_iter is not None:
            model = widget.get_model()
            mode = model[tree_iter][1]
            self.set_direct_full_width_letter_mode(
                mode, update_gsettings=True)

    def on_direct_full_width_punctuation_mode_combobox_changed(self, widget):
        '''
        A change of the letter width when in “Direct input” mode has been
        requested with the combobox
        '''
        tree_iter = widget.get_active_iter()
        if tree_iter is not None:
            model = widget.get_model()
            mode = model[tree_iter][1]
            self.set_direct_full_width_punctuation_mode(
                mode, update_gsettings=True)

    def on_always_show_lookup_combobox_changed(self, widget):
        '''
        A change of the display preference of the lookup table has been
        requested with the combobox
        '''
        tree_iter = widget.get_active_iter()
        if tree_iter is not None:
            model = widget.get_model()
            mode = model[tree_iter][1]
            self.set_always_show_lookup(
                mode, update_gsettings=True)

    def on_use_dark_theme_combobox_changed(self, widget):
        '''
        A change of the use color scheme for dark theme.
        '''
        active_id = widget.get_active_id()
        if active_id == "yes":
            use_dark_theme = True
        else:
            use_dark_theme = False
        self.set_dark_theme(use_dark_theme, update_gsettings=True)

    def on_debug_level_adjustment_value_changed(self, _widget):
        '''
        The value for the debug level has been changed.
        '''
        self.set_debug_level(
            self._debug_level_adjustment.get_value(),
            update_gsettings=True)

    def on_keybindings_treeview_row_activated(
            self, _treeview, treepath, _treeviewcolumn):
        '''
        A row in the treeview listing the key bindings has been activated.

        :param treeview: The treeview listing the key bindings
        :type treeview: Gtk.TreeView object
        :param treepath: The path to the activated row
        :type treepath: Gtk.TreePath object
        :param treeviewcolumn: A column in the treeview listing the
                               key bindings
        :type treeviewcolumn: Gtk.TreeViewColumn object
        '''
        model = self._keybindings_treeview_model
        iterator = model.get_iter(treepath)
        command = model[iterator][0]
        if command != self._keybindings_selected_command:
            # This should not happen, if a row is activated it should
            # already be selected,
            # i.e. on_keybindings_treeview_row_selected() should have
            # been called already and this should have set
            # self._keybindings_selected_command
            LOGGER.error(
                'Unexpected error, command = "%s" ' % command
                + 'self._keybindings_selected_command = "%s"\n'
                % self._keybindings_selected_command)
            return
        self._create_and_show_keybindings_edit_popover()

    def on_keybindings_treeview_row_selected(self, selection):
        '''
        A row in the treeview listing the key bindings has been selected.
        '''
        (model, iterator) = selection.get_selected()
        if iterator:
            self._keybindings_selected_command = model[iterator][0]
            self._keybindings_default_button.set_sensitive(True)
            self._keybindings_edit_button.set_sensitive(True)
        else:
            # all rows have been unselected
            self._keybindings_selected_command = ''
            self._keybindings_default_button.set_sensitive(False)
            self._keybindings_edit_button.set_sensitive(False)

    def on_keybindings_edit_listbox_row_selected(self, _listbox, listbox_row):
        '''
        Signal handler for selecting one of the key bindings
        for a certain command

        :param _listbox: The list box used to select a key binding
        :type _listbox: Gtk.ListBox object
        :param listbox_row: A row containing a key binding
        :type listbox_row: Gtk.ListBoxRow object
        '''
        if  listbox_row:
            keybinding = listbox_row.get_child().get_text()
            index = listbox_row.get_index()
            user_keybindings = self._settings_dict['keybindings']['user']
            command = self._keybindings_selected_command
            if (keybinding and command
                and keybinding in user_keybindings[command]):
                self._keybindings_edit_popover_selected_keybinding = keybinding
                self._keybindings_edit_popover_selected_keybinding_index = index
                self._keybindings_edit_popover_remove_button.set_sensitive(
                    True)
                self._keybindings_edit_popover_up_button.set_sensitive(index > 0)
                self._keybindings_edit_popover_down_button.set_sensitive(
                    index < len(user_keybindings[command]) - 1)
                return
        # all rows have been unselected
        self._keybindings_edit_popover_selected_keybinding = ''
        self._keybindings_edit_popover_selected_keybinding_index = -1
        self._keybindings_edit_popover_remove_button.set_sensitive(False)
        self._keybindings_edit_popover_up_button.set_sensitive(False)
        self._keybindings_edit_popover_down_button.set_sensitive(False)

    def on_keybindings_edit_popover_add_button_clicked(self, *_args):
        '''
        Signal handler called when the “Add” button to add
        a key binding has been clicked.
        '''
        key_input_dialog = it_util.ItKeyInputDialog(parent=self)
        response = key_input_dialog.run()
        key_input_dialog.destroy()
        if response == Gtk.ResponseType.OK:
            keyval, state = key_input_dialog.e
            key = it_util.KeyEvent(keyval, 0, state)
            keybinding = it_util.keyevent_to_keybinding(key)
            command = self._keybindings_selected_command
            user_keybindings = self._settings_dict['keybindings']['user']
            if keybinding not in user_keybindings[command]:
                user_keybindings[command].append(keybinding)
                self._fill_keybindings_edit_popover_listbox()
                self.set_keybindings(user_keybindings)

    def on_keybindings_edit_popover_remove_button_clicked(self, *_args):
        '''
        Signal handler called when the “Remove” button to remove
        a key binding has been clicked.
        '''
        keybinding = self._keybindings_edit_popover_selected_keybinding
        command = self._keybindings_selected_command
        user_keybindings = self._settings_dict['keybindings']['user']
        if (keybinding and command
                and keybinding in user_keybindings[command]):
            user_keybindings[command].remove(keybinding)
            self._fill_keybindings_edit_popover_listbox()
            self.set_keybindings(user_keybindings)

    def on_keybindings_edit_popover_up_button_clicked(self, *_args):
        '''
        Signal handler called when the “up” button to move
        a key binding up has been clicked.
        '''
        index = self._keybindings_edit_popover_selected_keybinding_index
        command = self._keybindings_selected_command
        keybinding = self._keybindings_edit_popover_selected_keybinding
        user_keybindings = self._settings_dict['keybindings']['user']
        if not 0 < index < len(user_keybindings[command]):
            # This should not happen, one should not be able
            # to click the up button in this case, just return
            return
        user_keybindings[command] = (
            user_keybindings[command][:index - 1]
            + [user_keybindings[command][index]]
            + [user_keybindings[command][index - 1]]
            + user_keybindings[command][index + 1:])
        self.set_keybindings(user_keybindings, update_gsettings=True)
        self._fill_keybindings_edit_popover_listbox()
        self._keybindings_edit_popover_selected_keybinding_index = index - 1
        self._keybindings_edit_popover_selected_keybinding = keybinding
        self._keybindings_edit_popover_listbox.select_row(
            self._keybindings_edit_popover_listbox.get_row_at_index(index - 1))

    def on_keybindings_edit_popover_down_button_clicked(self, *_args):
        '''
        Signal handler called when the “down” button to move
        a key binding down has been clicked.
        '''
        index = self._keybindings_edit_popover_selected_keybinding_index
        command = self._keybindings_selected_command
        keybinding = self._keybindings_edit_popover_selected_keybinding
        user_keybindings = self._settings_dict['keybindings']['user']
        if not 0 <= index < len(user_keybindings[command]) - 1:
            # This should not happen, one should not be able
            # to click the up button in this case, just return
            return
        user_keybindings[command] = (
            user_keybindings[command][:index]
            + [user_keybindings[command][index + 1]]
            + [user_keybindings[command][index]]
            + user_keybindings[command][index + 2:])
        self.set_keybindings(user_keybindings, update_gsettings=True)
        self._fill_keybindings_edit_popover_listbox()
        self._keybindings_edit_popover_selected_keybinding_index = index + 1
        self._keybindings_edit_popover_selected_keybinding = keybinding
        self._keybindings_edit_popover_listbox.select_row(
            self._keybindings_edit_popover_listbox.get_row_at_index(index + 1))

    def on_keybindings_edit_popover_default_button_clicked(self, *_args):
        '''
        Signal handler called when the “Default” button to set
        the keybindings to the default has been clicked.
        '''
        default_keybindings = self._settings_dict['keybindings']['default']
        user_keybindings = self._settings_dict['keybindings']['user']
        command = self._keybindings_selected_command
        if command and command in default_keybindings:
            user_keybindings[command] = default_keybindings[command].copy()
            self._fill_keybindings_edit_popover_listbox()
            self.set_keybindings(user_keybindings)

    def _fill_keybindings_edit_popover_listbox(self):
        '''
        Fill the edit listbox to with the key bindings of the currently
        selected command
        '''
        for child in self._keybindings_edit_popover_scroll.get_children():
            self._keybindings_edit_popover_scroll.remove(child)
        self._keybindings_edit_popover_listbox = Gtk.ListBox()
        self._keybindings_edit_popover_scroll.add(
            self._keybindings_edit_popover_listbox)
        self._keybindings_edit_popover_selected_keybinding = ''
        self._keybindings_edit_popover_selected_keybinding_index = -1
        self._keybindings_edit_popover_listbox.set_visible(True)
        self._keybindings_edit_popover_listbox.set_vexpand(True)
        self._keybindings_edit_popover_listbox.set_selection_mode(
            Gtk.SelectionMode.SINGLE)
        self._keybindings_edit_popover_listbox.set_activate_on_single_click(
            True)
        self._keybindings_edit_popover_listbox.connect(
            'row-selected', self.on_keybindings_edit_listbox_row_selected)
        user_keybindings = self._settings_dict['keybindings']['user']
        for keybinding in user_keybindings[self._keybindings_selected_command]:
            label = Gtk.Label()
            label.set_text(html.escape(keybinding))
            label.set_use_markup(True)
            label.set_xalign(0)
            margin = 1
            label.set_margin_start(margin)
            label.set_margin_end(margin)
            label.set_margin_top(margin)
            label.set_margin_bottom(margin)
            self._keybindings_edit_popover_listbox.insert(label, -1)
        self._keybindings_edit_popover_remove_button.set_sensitive(False)
        self._keybindings_edit_popover_up_button.set_sensitive(False)
        self._keybindings_edit_popover_down_button.set_sensitive(False)
        self._keybindings_edit_popover_listbox.show_all()

    def _create_and_show_keybindings_edit_popover(self):
        '''
        Create and show the popover to edit the key bindings for a command
        '''
        self._keybindings_edit_popover = Gtk.Popover()
        self._keybindings_edit_popover.set_relative_to(
            self._keybindings_edit_button)
        self._keybindings_edit_popover.set_position(Gtk.PositionType.RIGHT)
        self._keybindings_edit_popover.set_vexpand(True)
        self._keybindings_edit_popover.set_hexpand(True)
        keybindings_edit_popover_vbox = Gtk.VBox()
        margin = 12
        keybindings_edit_popover_vbox.set_margin_start(margin)
        keybindings_edit_popover_vbox.set_margin_end(margin)
        keybindings_edit_popover_vbox.set_margin_top(margin)
        keybindings_edit_popover_vbox.set_margin_bottom(margin)
        keybindings_edit_popover_vbox.set_spacing(margin)
        keybindings_edit_popover_label = Gtk.Label()
        keybindings_edit_popover_label.set_text(
            _('Edit key bindings for command “%s”')
            %self._keybindings_selected_command)
        keybindings_edit_popover_label.set_use_markup(True)
        keybindings_edit_popover_label.set_visible(True)
        keybindings_edit_popover_label.set_halign(Gtk.Align.FILL)
        keybindings_edit_popover_vbox.pack_start(
            keybindings_edit_popover_label, False, False, 0)
        self._keybindings_edit_popover_scroll = Gtk.ScrolledWindow()
        self._keybindings_edit_popover_scroll.set_hexpand(True)
        self._keybindings_edit_popover_scroll.set_vexpand(True)
        self._keybindings_edit_popover_scroll.set_kinetic_scrolling(False)
        self._keybindings_edit_popover_scroll.set_overlay_scrolling(True)
        keybindings_edit_popover_vbox.pack_start(
            self._keybindings_edit_popover_scroll, True, True, 0)
        keybindings_edit_popover_button_box = Gtk.ButtonBox()
        keybindings_edit_popover_button_box.set_can_focus(False)
        keybindings_edit_popover_button_box.set_layout(
            Gtk.ButtonBoxStyle.START)
        keybindings_edit_popover_vbox.pack_start(
            keybindings_edit_popover_button_box, False, False, 0)
        self._keybindings_edit_popover_add_button = Gtk.Button()
        keybindings_edit_popover_add_button_label = Gtk.Label()
        keybindings_edit_popover_add_button_label.set_text(
            '<span size="xx-large"><b>+</b></span>')
        keybindings_edit_popover_add_button_label.set_use_markup(True)
        self._keybindings_edit_popover_add_button.add(
            keybindings_edit_popover_add_button_label)
        self._keybindings_edit_popover_add_button.set_tooltip_text(
            # Translators: This is a tooltip for the button to add a
            # key binding.
            _('Add a key binding'))
        self._keybindings_edit_popover_add_button.connect(
            'clicked', self.on_keybindings_edit_popover_add_button_clicked)
        self._keybindings_edit_popover_add_button.set_sensitive(True)
        self._keybindings_edit_popover_remove_button = Gtk.Button()
        keybindings_edit_popover_remove_button_label = Gtk.Label()
        keybindings_edit_popover_remove_button_label.set_text(
            '<span size="xx-large"><b>-</b></span>')
        keybindings_edit_popover_remove_button_label.set_use_markup(True)
        self._keybindings_edit_popover_remove_button.add(
            keybindings_edit_popover_remove_button_label)
        self._keybindings_edit_popover_remove_button.set_tooltip_text(
            # Translators: This is a tooltip for the button to remove
            # the selected key binding.
            _('Remove selected key binding'))
        self._keybindings_edit_popover_remove_button.connect(
            'clicked', self.on_keybindings_edit_popover_remove_button_clicked)
        self._keybindings_edit_popover_remove_button.set_sensitive(False)
        self._keybindings_edit_popover_default_button = Gtk.Button()
        self._keybindings_edit_popover_up_button = Gtk.Button()
        keybindings_edit_popover_up_button_label = Gtk.Label()
        keybindings_edit_popover_up_button_label.set_text(
            '<span size="xx-large"><b>↑</b></span>')
        keybindings_edit_popover_up_button_label.set_use_markup(True)
        self._keybindings_edit_popover_up_button.add(
            keybindings_edit_popover_up_button_label)
        self._keybindings_edit_popover_up_button.set_tooltip_text(
            # Translators: This is a tooltip for the button to move
            # the selected key binding up (higher in priority).
            _('Move key binding up'))
        self._keybindings_edit_popover_up_button.connect(
            'clicked', self.on_keybindings_edit_popover_up_button_clicked)
        self._keybindings_edit_popover_down_button = Gtk.Button()
        keybindings_edit_popover_down_button_label = Gtk.Label()
        keybindings_edit_popover_down_button_label.set_text(
            '<span size="xx-large"><b>↓</b></span>')
        keybindings_edit_popover_down_button_label.set_use_markup(True)
        self._keybindings_edit_popover_down_button.add(
            keybindings_edit_popover_down_button_label)
        self._keybindings_edit_popover_down_button.set_tooltip_text(
            # Translators: This is a tooltip for the button to move
            # the selected key binding down (lower in priority).
            _('Move key binding down'))
        self._keybindings_edit_popover_down_button.connect(
            'clicked', self.on_keybindings_edit_popover_down_button_clicked)
        keybindings_edit_popover_default_button_label = Gtk.Label()
        keybindings_edit_popover_default_button_label.set_text(
            _('Set to default'))
        keybindings_edit_popover_default_button_label.set_use_markup(True)
        self._keybindings_edit_popover_default_button.add(
            keybindings_edit_popover_default_button_label)
        self._keybindings_edit_popover_default_button.set_tooltip_text(
            # Translators: This is a tooltip for the button to set
            # the key bindings for the selected command to the default.
            _('Set default key bindings for the selected command'))
        self._keybindings_edit_popover_default_button.connect(
            'clicked', self.on_keybindings_edit_popover_default_button_clicked)
        self._keybindings_edit_popover_default_button.set_sensitive(True)
        keybindings_edit_popover_button_box.add(
            self._keybindings_edit_popover_add_button)
        keybindings_edit_popover_button_box.add(
            self._keybindings_edit_popover_remove_button)
        keybindings_edit_popover_button_box.add(
            self._keybindings_edit_popover_up_button)
        keybindings_edit_popover_button_box.add(
            self._keybindings_edit_popover_down_button)
        keybindings_edit_popover_button_box.add(
            self._keybindings_edit_popover_default_button)
        self._keybindings_edit_popover.add(keybindings_edit_popover_vbox)
        self._fill_keybindings_edit_popover_listbox()
        if GTK_VERSION >= (3, 22, 0):
            self._keybindings_edit_popover.popup()
        self._keybindings_edit_popover.show_all()

    def on_keybindings_edit_button_clicked(self, *_args):
        '''
        Signal handler called when the “edit” button to edit the
        key bindings for a command has been clicked.
        '''
        self._create_and_show_keybindings_edit_popover()

    def on_keybindings_default_button_clicked(self, *_args):
        '''
        Signal handler called when the “Set to default” button to reset the
        key bindings for a command to the default has been clicked.
        '''
        default_keybindings = self._settings_dict['keybindings']['default']
        user_keybindings = self._settings_dict['keybindings']['user']
        command = self._keybindings_selected_command
        if command and command in default_keybindings:
            user_keybindings[command] = default_keybindings[command].copy()
            self.set_keybindings(user_keybindings)

    def on_keybindings_all_default_button_clicked(self, *_args):
        '''
        Signal handler called when the “Set all to default” button to reset the
        all key bindings top their defaults has been clicked.
        '''
        self._keybindings_all_default_button.set_sensitive(False)
        response = self._run_are_you_sure_dialog(
            # Translators: This is the text in the centre of a small
            # dialog window, trying to confirm whether the user is
            # really sure to reset the key bindings for *all* commands
            # to their defaults. This cannot be reversed so the user
            # should be really sure he wants to do that.
            _('Do you really want to set the key bindings for '
              + 'all commands to their defaults?'))
        if response == Gtk.ResponseType.OK:
            self.set_keybindings(self._settings_dict['keybindings']['default'])
        self._keybindings_all_default_button.set_sensitive(True)

    def set_single_wildcard_char(self, single_wildcard_char,
                                   update_gsettings=True):
        '''Sets the single wildchard character.

        :param single_wildcard_char: The character to use as a single wildcard
        :type single_wildcard_char: string
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        :type update_gsettings: boolean
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)',
            single_wildcard_char, update_gsettings)
        self._settings_dict['singlewildcardchar']['user'] = (
            single_wildcard_char)
        if update_gsettings:
            self._gsettings.set_value(
                'singlewildcardchar',
                GLib.Variant.new_string(single_wildcard_char))
        else:
            self._single_wildcard_char_entry.set_text(single_wildcard_char)

    def set_multi_wildcard_char(self, multi_wildcard_char,
                                   update_gsettings=True):
        '''Sets the single wildchard character.

        :param multi_wildcard_char: The character to use as a single wildcard
        :type multi_wildcard_char: string
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        :type update_gsettings: boolean
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)',
            multi_wildcard_char, update_gsettings)
        self._settings_dict['multiwildcardchar']['user'] = multi_wildcard_char
        if update_gsettings:
            self._gsettings.set_value(
                'multiwildcardchar',
                GLib.Variant.new_string(multi_wildcard_char))
        else:
            self._multi_wildcard_char_entry.set_text(multi_wildcard_char)

    def set_page_size(self, page_size, update_gsettings=True):
        '''Sets the page size of the lookup table

        :param page_size: The page size of the lookup table
        :type mode: integer >= 1 and <= 10
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        :type update_gsettings: boolean
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', page_size, update_gsettings)
        page_size = int(page_size)
        if 1 <= page_size <= 10:
            self._settings_dict['lookuptablepagesize']['user'] = page_size
            if update_gsettings:
                self._gsettings.set_value(
                    'lookuptablepagesize',
                    GLib.Variant.new_int32(page_size))
            else:
                self._page_size_adjustment.set_value(page_size)

    def set_lookup_table_orientation(self, orientation, update_gsettings=True):
        '''Sets the page size of the lookup table

        :param orientation: The orientation of the lookup table
        :type orientation: integer >= 0 and <= 2
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        :type update_gsettings: boolean
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', orientation, update_gsettings)
        orientation = int(orientation)
        if 0 <= orientation <= 2:
            self._settings_dict['lookuptableorientation']['user'] = orientation
            if update_gsettings:
                self._gsettings.set_value(
                    'lookuptableorientation',
                    GLib.Variant.new_int32(orientation))
            else:
                for index, item in enumerate(
                        self._lookup_table_orientation_store):
                    if orientation == item[1]:
                        self._lookup_table_orientation_combobox.set_active(
                            index)

    def set_input_mode(self, input_mode=1, update_gsettings=True):
        '''Sets whether direct input or the current table is used.

        :param input_mode: Whether to use direct input.
                           0: Use direct input.
                           1: Use the current table.
        :type input_mode: Integer, 0 or 1.
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        :type update_gsettings: boolean
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', input_mode, update_gsettings)
        input_mode = int(input_mode)
        if 0 <= input_mode <= 1:
            self._settings_dict['inputmode']['user'] = input_mode
            if update_gsettings:
                self._gsettings.set_value(
                    'inputmode',
                    GLib.Variant.new_int32(input_mode))
            else:
                for index, item in enumerate(self._input_mode_store):
                    if input_mode == item[1]:
                        self._input_mode_combobox.set_active(index)

    def set_chinese_mode(self, chinese_mode=0, update_gsettings=True):
        '''Sets the candidate filter mode used for Chinese

        0 means to show simplified Chinese only
        1 means to show traditional Chinese only
        2 means to show all characters but show simplified Chinese first
        3 means to show all characters but show traditional Chinese first
        4 means to show all characters

        :param mode: The Chinese filter mode
        :type mode: integer >= 0 and <= 4
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the dconf key changed
                                 to avoid endless loops when the dconf
                                 key is changed twice in a short time.
        :type update_gsettings: boolean
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', chinese_mode, update_gsettings)
        chinese_mode = int(chinese_mode)
        if 0 <= chinese_mode <= 4:
            self._settings_dict['chinesemode']['user'] = chinese_mode
            if update_gsettings:
                self._gsettings.set_value(
                    'chinesemode',
                    GLib.Variant.new_int32(chinese_mode))
            else:
                for index, item in enumerate(self._chinese_mode_store):
                    if chinese_mode == item[1]:
                        self._chinese_mode_combobox.set_active(index)

    def set_onechar_mode(
            self, mode=False, update_gsettings=True):
        '''Sets whether only single characters should be matched in
        the database.

        :param mode: Whether only single characters should be matched.
                     True: Match only single characters.
                     False: Possibly match multiple characters at once.
        :type mode: Boolean
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        :type update_gsettings: boolean
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', mode, update_gsettings)
        mode = bool(mode)
        self._settings_dict['onechar']['user'] = mode
        if update_gsettings:
            self._gsettings.set_value(
                'onechar',
                GLib.Variant.new_boolean(mode))
        else:
            for index, item in enumerate(self._onechar_mode_store):
                if mode == item[1]:
                    self._onechar_mode_combobox.set_active(index)

    def set_autoselect_mode(
            self, mode=False, update_gsettings=True):
        '''Sets whether the first candidate will be selected
        automatically during typing.

        :param mode: Whether to select the first candidate automatically.
        :type mode: Boolean
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        :type update_gsettings: boolean
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', mode, update_gsettings)
        mode = bool(mode)
        self._settings_dict['autoselect']['user'] = mode
        if update_gsettings:
            self._gsettings.set_value(
                'autoselect',
                GLib.Variant.new_boolean(mode))
        else:
            for index, item in enumerate(self._autoselect_mode_store):
                if mode == item[1]:
                    self._autoselect_mode_combobox.set_active(index)

    def set_autocommit_mode(
            self, mode=False, update_gsettings=True):
        '''Sets whether automatic commits go into the preëdit or into the
        application.

        :param mode: Whether automatic commits  go into the  preëdit
                     or into the application.
                     True: Into the application.
                     False: Into the preedit.
        :type mode: Boolean
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        :type update_gsettings: boolean
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', mode, update_gsettings)
        mode = bool(mode)
        self._settings_dict['autocommit']['user'] = mode
        if update_gsettings:
            self._gsettings.set_value(
                'autocommit',
                GLib.Variant.new_boolean(mode))
        else:
            for index, item in enumerate(self._autocommit_mode_store):
                if mode == item[1]:
                    self._autocommit_mode_combobox.set_active(index)

    def set_autowildcard_mode(
            self, mode=False, update_gsettings=True):
        '''Sets whether a wildcard should be automatically appended
        to the input.

        :param mode: Whether to append a wildcard automatically.
        :type mode: Boolean
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        :type update_gsettings: boolean
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', mode, update_gsettings)
        mode = bool(mode)
        self._settings_dict['autowildcard']['user'] = mode
        if update_gsettings:
            self._gsettings.set_value(
                'autowildcard',
                GLib.Variant.new_boolean(mode))
        else:
            for index, item in enumerate(self._autowildcard_mode_store):
                if mode == item[1]:
                    self._autowildcard_mode_combobox.set_active(index)

    def set_table_full_width_letter_mode(
            self, mode=False, update_gsettings=True):
        '''Sets whether full width letters should be used
        while in “Table input” mode

        :param mode: Whether to use full width letters
        :type mode: Boolean
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        :type update_gsettings: boolean
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', mode, update_gsettings)
        mode = bool(mode)
        self._settings_dict['tabdeffullwidthletter']['user'] = mode
        if update_gsettings:
            self._gsettings.set_value(
                'tabdeffullwidthletter',
                GLib.Variant.new_boolean(mode))
        else:
            for index, item in enumerate(
                    self._table_full_width_letter_mode_store):
                if mode == item[1]:
                    self._table_full_width_letter_mode_combobox.set_active(
                        index)

    def set_table_full_width_punctuation_mode(
            self, mode=False, update_gsettings=True):
        '''Sets whether full width punctuation should be used
        while in “Table input” mode

        :param mode: Whether to use full width punctuation
        :type mode: Boolean
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        :type update_gsettings: boolean
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', mode, update_gsettings)
        mode = bool(mode)
        self._settings_dict['tabdeffullwidthpunct']['user'] = mode
        if update_gsettings:
            self._gsettings.set_value(
                'tabdeffullwidthpunct',
                GLib.Variant.new_boolean(mode))
        else:
            for index, item in enumerate(
                    self._table_full_width_punctuation_mode_store):
                if mode == item[1]:
                    self._table_full_width_punctuation_mode_combobox.set_active(
                        index)

    def set_direct_full_width_letter_mode(
            self, mode=False, update_gsettings=True):
        '''Sets whether full width letters should be used
        while in “Direct input” mode

        :param mode: Whether to use full width letters
        :type mode: Boolean
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        :type update_gsettings: boolean
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', mode, update_gsettings)
        mode = bool(mode)
        self._settings_dict['endeffullwidthletter']['user'] = mode
        if update_gsettings:
            self._gsettings.set_value(
                'endeffullwidthletter',
                GLib.Variant.new_boolean(mode))
        else:
            for index, item in enumerate(
                    self._direct_full_width_letter_mode_store):
                if mode == item[1]:
                    self._direct_full_width_letter_mode_combobox.set_active(
                        index)

    def set_direct_full_width_punctuation_mode(
            self, mode=False, update_gsettings=True):
        '''Sets whether full width punctuation should be used
        while in “Direct input” mode

        :param mode: Whether to use full width punctuation
        :type mode: Boolean
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        :type update_gsettings: boolean
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', mode, update_gsettings)
        mode = bool(mode)
        self._settings_dict['endeffullwidthpunct']['user'] = mode
        if update_gsettings:
            self._gsettings.set_value(
                'endeffullwidthpunct',
                GLib.Variant.new_boolean(mode))
        else:
            for index, item in enumerate(
                    self._direct_full_width_punctuation_mode_store):
                if mode == item[1]:
                    self._direct_full_width_punctuation_mode_combobox.set_active(
                        index)

    def set_always_show_lookup(
            self, mode=False, update_gsettings=True):
        '''Sets the whether the lookup table is shown.

        :param mode: Whether to show the lookup table
        :type mode: Boolean
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        :type update_gsettings: boolean
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', mode, update_gsettings)
        self._settings_dict['alwaysshowlookup']['user'] = mode
        if update_gsettings:
            self._gsettings.set_value(
                'alwaysshowlookup',
                GLib.Variant.new_boolean(mode))
        else:
            for index, item in enumerate(self._input_mode_store):
                if self._settings_dict['alwaysshowlookup']['user'] == item[1]:
                    self._always_show_lookup_combobox.set_active(index)

    def set_dark_theme(
            self, use_dark_theme=False, update_gsettings=True):
        '''Sets the whether to use the color scheme for dark theme.

        :param use_dark_theme: Whether to use the color scheme for dark theme
        :type use_dark_theme: Boolean
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        :type update_gsettings: boolean
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', use_dark_theme, update_gsettings)
        self._settings_dict['darktheme']['user'] = use_dark_theme
        if update_gsettings:
            self._gsettings.set_value(
                'darktheme',
                GLib.Variant.new_boolean(use_dark_theme))
        else:
            if use_dark_theme:
                active_id = "yes"
            else:
                active_id = "no"
            self._use_dark_theme_combobox.set_active_id(active_id)

    def set_debug_level(self, debug_level, update_gsettings=True):
        '''Sets the debug level

        :param debug level: The debug level
        :type debug_level: Integer >= 0 and <= 255
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        :type update_gsettings: boolean
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', debug_level, update_gsettings)
        debug_level = int(debug_level)
        if 0 <= debug_level <= 255:
            self._settings_dict['debuglevel']['user'] = debug_level
            if update_gsettings:
                self._gsettings.set_value(
                    'debuglevel',
                    GLib.Variant.new_int32(debug_level))
            else:
                self._debug_level_adjustment.set_value(debug_level)

    def set_keybindings(self, keybindings, update_gsettings=True):
        '''Set current key bindings

        :param keybindings: The key bindings to use
        :type keybindings: Dictionary of key bindings for commands.
                           Commands which do not already
                           exist in the current key bindings dictionary
                           will be ignored.
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        :type update_gsettings: boolean
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', keybindings, update_gsettings)
        if not isinstance(keybindings, dict):
            return
        keybindings = copy.deepcopy(keybindings)
        user_keybindings = self._settings_dict['keybindings']['user']
        # Update the default settings with the possibly changed settings:
        it_util.dict_update_existing_keys(user_keybindings, keybindings)
        # update the tree model
        model = self._keybindings_treeview_model
        iterator = model.get_iter_first()
        while iterator:
            for command in user_keybindings:
                if model.get_value(iterator, 0) == command:
                    model.set_value(iterator, 1,
                                    repr(user_keybindings[command]))
            iterator = model.iter_next(iterator)
        if update_gsettings:
            variant_dict = GLib.VariantDict(GLib.Variant('a{sv}', {}))
            for command in sorted(user_keybindings):
                variant_array = GLib.Variant.new_array(
                    GLib.VariantType('s'),
                    [GLib.Variant.new_string(x)
                     for x in user_keybindings[command]])
                variant_dict.insert_value(command, variant_array)
            self._gsettings.set_value(
                'keybindings',
                variant_dict.end())

class HelpWindow(Gtk.Window):
    '''
    A window to show help

    :param parent: The parent object
    :type parent: Gtk.Window object
    :param title: Title of the help window
    :type title: String
    :param contents: Contents of the help window
    :type contents: String
    '''
    def __init__(self,
                 parent=None,
                 title='',
                 contents=''):
        Gtk.Window.__init__(self, title=title)
        if parent:
            self.set_parent(parent)
            self.set_transient_for(parent)
            # to receive mouse events for scrolling and for the close
            # button
            self.set_modal(True)
        self.set_destroy_with_parent(False)
        self.set_default_size(600, 500)
        self.vbox = Gtk.VBox(spacing=0)
        self.add(self.vbox)
        self.text_buffer = Gtk.TextBuffer()
        self.text_buffer.insert_at_cursor(contents)
        self.text_view = Gtk.TextView()
        self.text_view.set_buffer(self.text_buffer)
        self.text_view.set_editable(False)
        self.text_view.set_cursor_visible(False)
        self.text_view.set_justification(Gtk.Justification.LEFT)
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.scrolledwindow = Gtk.ScrolledWindow()
        self.scrolledwindow.set_hexpand(True)
        self.scrolledwindow.set_vexpand(True)
        self.scrolledwindow.add(self.text_view)
        self.vbox.pack_start(self.scrolledwindow, True, True, 0)
        self.close_button = Gtk.Button()
        self.close_button_label = Gtk.Label()
        self.close_button_label.set_text_with_mnemonic(_('_Close'))
        self.close_button.add(self.close_button_label)
        self.close_button.connect("clicked", self.on_close_button_clicked)
        self.hbox = Gtk.HBox(spacing=0)
        self.hbox.pack_end(self.close_button, False, False, 0)
        self.vbox.pack_start(self.hbox, False, False, 5)
        self.show_all()

    def on_close_button_clicked(self, _widget):
        '''
        Close the input method help window when the close button is clicked
        '''
        self.destroy()

if __name__ == '__main__':
    if _ARGS.no_debug:
        LOG_HANDLER = logging.NullHandler()
    else:
        LOGFILE = os.path.join(
            ibus_table_location.cache_home(), 'setup-debug.log')
        LOG_HANDLER = logging.handlers.TimedRotatingFileHandler(
            LOGFILE,
            when='H',
            interval=6,
            backupCount=7,
            encoding='UTF-8',
            delay=False,
            utc=False,
            atTime=None)
        LOG_FORMATTER = logging.Formatter(
            '%(asctime)s %(filename)s '
            'line %(lineno)d %(funcName)s %(levelname)s: '
            '%(message)s')
        LOG_HANDLER.setFormatter(LOG_FORMATTER)
        LOGGER.setLevel(logging.DEBUG)
        LOGGER.addHandler(LOG_HANDLER)
        LOGGER.info('********** STARTING **********')

    # Workaround for
    # https://bugzilla.gnome.org/show_bug.cgi?id=622084
    # Bug 622084 - Ctrl+C does not exit gtk app
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    try:
        locale.setlocale(locale.LC_ALL, '')
    except locale.Error:
        LOGGER.exception("IBUS-WARNING **: Using the fallback 'C' locale")
        locale.setlocale(locale.LC_ALL, 'C')
    i18n_init()
    if IBus.get_address() is None:
        DIALOG = Gtk.MessageDialog(
            flags=Gtk.DialogFlags.MODAL,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            message_format=_('ibus is not running.'))
        DIALOG.run()
        DIALOG.destroy()
        sys.exit(1)
    ENGINE_NAME = _ARGS.engine_name
    if not ENGINE_NAME and 'IBUS_ENGINE_NAME' in os.environ:
        ENGINE_NAME = os.environ['IBUS_ENGINE_NAME']
    ENGINE_NAME = re.sub(r'^table:', '', ENGINE_NAME).replace(' ', '_')
    if not ENGINE_NAME:
        PARSER.print_help()
    SETUP_UI = SetupUI(engine_name=ENGINE_NAME)
    Gtk.main()
