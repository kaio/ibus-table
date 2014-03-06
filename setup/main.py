# vim:fileencoding=utf-8:sw=4:et
#
# ibus-table-setup - Setup UI for ibus-table
#
# Copyright (c) 2008-2010 Peng Huang <shawn.p.huang@gmail.com>
# Copyright (c) 2010 BYVoid <byvoid1@gmail.com>
# Copyright (c) 2012 Ma Xiaojun <damage3025@gmail.com>
# Copyright (c) 2012 mozbugbox <mozbugbox@yahoo.com.au>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301, USA.

import gettext
import locale
import os
import sys
import logging as log

from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import IBus

import version

_ = lambda a : gettext.dgettext("ibus-table", a)

OPTION_DEFAULTS = {
    "language": False,
    "chinesemode": 0,
    "tabdeffullwidthletter": False,
    "tabdeffullwidthpunct": False,
    "lookuptableorientation": True,
    "lookuptablepagesize": 6,
    "onechar": False,
    "autocommit": False,
    "spacekeybehavior": False,
}

SCALE_WIDGETS = {
    "lookuptablepagesize",
}

ibus_dir = os.getenv('IBUS_TABLE_LOCATION')
ibus_lib_dir = os.getenv('IBUS_TABLE_LIB_LOCATION')

if not ibus_dir or not os.path.exists(ibus_dir):
    ibus_dir = "/usr/share/ibus-table/"
if not ibus_lib_dir or not os.path.exists(ibus_lib_dir):
    ibus_lib_dir = "/usr/libexec"

db_dir = os.path.join (ibus_dir, 'tables')
icon_dir = os.path.join (ibus_dir, 'icons')
setup_cmd = os.path.join(ibus_lib_dir, "ibus-setup-table")

class PreferencesDialog:
    def __init__(self, table_name):
        locale.setlocale(locale.LC_ALL, "")
        localedir = os.getenv("IBUS_LOCALEDIR")
        gettext.bindtextdomain("ibus-table", localedir)
        gettext.bind_textdomain_codeset("ibus-table", "UTF-8")

        self.__table_name = table_name
        self.__bus = IBus.Bus()

    def check_table_available(self):
        """Check if the current table_name is avalible.
        Return bool"""
        names = self.__bus.list_engines()
        names = [x.get_name() for x in names]
        ret = True

        if self.__table_name not in names:
            ret = False
            msg = _("IBus Table {} is not available").format(self.__table_name)
            mdialog = Gtk.MessageDialog(None, 0, Gtk.MessageType.ERROR,
                    Gtk.ButtonsType.OK, msg)
            mdialog.props.title = "IBus Table Setup Error"
            mdialog.run()
        return ret

    def _build_combobox_renderer(self, name):
        """setup cell renderer for combobox"""
        __combobox = self.__builder.get_object("combobox%s" % name)
        __cell = Gtk.CellRendererText()
        __combobox.pack_start(__cell, True)
        __combobox.add_attribute(__cell, 'text', 0)

    def load_builder(self):
        """Load builder and __dialog attribute"""
        self.__builder = Gtk.Builder()
        self.__builder.set_translation_domain("ibus-table")
        self.__builder.add_from_file("ibus-table-preferences.ui")
        self.__dialog = self.__builder.get_object("dialog")

        for name in list(OPTION_DEFAULTS.keys()):
            if name not in SCALE_WIDGETS:
                self._build_combobox_renderer(name)

    def do_init(self):
        self.__config = self.__bus.get_config()
        self.__config_section = ("engine/Table/%s" %
                self.__table_name.replace(" ", "_"))

        self.__init_general()
        self.__init_about()

    def __init_general(self):
        """Initialize the general notebook page"""
        self.__dialog.set_title("IBus %s Preferences" % self.__table_name)
        self.__values = self.__config.get_values(self.__config_section).unpack()
        self.__config.connect ("value-changed", self.__config_value_changed_cb)

        for name in list(OPTION_DEFAULTS.keys()):
            #self.__config.unset(self.__config_section, name); continue
            if name in SCALE_WIDGETS:
                self._init_hscale(name)
            else:
                self._init_combobox(name)
        return

    def __init_about(self):
        """Initialize the About notebook page"""
        # page About
        self.__name_version = self.__builder.get_object("NameVersion")
        self.__name_version.set_markup(
                _("<big><b>IBus Table %s</b></big>") % version.get_version())

        img_fname = os.path.join(icon_dir, "ibus-table.svg")
        if os.path.exists(img_fname):
            img = self.__builder.get_object("image_about")
            img.set_from_file(img_fname)

        # setup table info
        engines = self.__bus.list_engines()
        engine = None
        for e in engines:
            if e.get_name() == self.__table_name:
                engine = e
                break
        if engine:
            longname = engine.get_longname()
            if not longname:
                longname = engine.get_name()
            w = self.__builder.get_object("TableNameVersion")
            w.set_markup(_("<b>%s</b>") %
                    (longname))
            icon_path = engine.get_icon()
            if icon_path and os.path.exists(icon_path):
                from gi.repository import GdkPixbuf
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(icon_path,
                        -1, 32)
                w = self.__builder.get_object("TableNameImage")
                w.set_from_pixbuf(pixbuf)

    def _init_combobox(self, name):
        """Set combobox from the __config engine"""
        __combobox = self.__builder.get_object("combobox%s" % name)
        val = 0
        if name in self.__values:
            init_val = self.__values[name]
        else:
            init_val = OPTION_DEFAULTS[name]
        if isinstance(init_val, bool):
            val = 1 if init_val else 0
        elif isinstance(init_val, int):
            val = init_val
        elif isinstance(init_val, str):
            model = __combobox.get_model()
            for i, row in enumerate(model):
                if row[0] == init_val:
                    val = i
                    break
        __combobox.set_active(val)
        __combobox.connect("changed", self.__changed_cb, name)

    def _init_hscale(self, name):
        """Set scale widget from the __config engine"""
        __hscale = self.__builder.get_object("hscale%s" % name)
        if name in self.__values:
            val = self.__values[name]
        else:
            val = OPTION_DEFAULTS[name]
        __hscale.set_value(val)
        __hscale.connect("value-changed", self.__value_changed_cb, name)

    def __changed_cb(self, widget, name):
        """Combobox changed handler"""
        val = widget.get_active()
        vtype = type(OPTION_DEFAULTS[name])
        if vtype == bool:
            val = False if val == 0 else True
        self.__set_value(name, val)

    def __value_changed_cb(self, widget, name):
        """scale widget value changed handler"""
        val = widget.get_value()
        vtype = type(OPTION_DEFAULTS[name])
        if vtype == int:
            val = int(val)
        self.__set_value(name, val)

    def __config_value_changed_cb(self, config, section, name, val):
        """__config engine value changed handler"""
        val = val.unpack()
        if name in SCALE_WIDGETS:
            __hscale = self.__builder.get_object("hscale%s" % name)
            __hscale.set_value(val)
        else:
            __combobox = self.__builder.get_object("combobox%s" % name)
            if isinstance(val, bool):
                val = 1 if val else 0
            elif isinstance(val, str):
                val = val.get_string()
                model = __combobox.get_model()
                for i, row in enumerate(model):
                    if row[0] == val:
                        val = i
                        break
            __combobox.set_active(val)
        self.__values[name] = val

    def __toggled_cb(self, widget, name):
        """toggle button toggled signal handler"""
        self.__set_value(name, widget.get_active ())

    def __get_value(self, name, defval):
        """Get the __config value if available"""
        if name in self.__values:
            var = self.__values[name]
            if isinstance(defval, type(var)):
                return var
        self.__set_value(name, defval)
        return defval

    def __set_value(self, name, val):
        """Set the config value to __config"""
        var = None
        if isinstance(val, bool):
            var = GLib.Variant.new_boolean(val)
        elif isinstance(val, int):
            var = GLib.Variant.new_int32(val)
        elif isinstance(val, str):
            var = GLib.Variant.new_string(val)
        else:
            sys.stderr.write("val(%s) is not in support type." %repr(val))
            return

        self.__values[name] = val
        self.__config.set_value(self.__config_section, name, var)

    def run(self):
        ret = self.check_table_available()
        if not ret:
            return 0
        GLib.idle_add(self.do_init)
        self.load_builder()
        return self.__dialog.run()


def main():
    log_level = log.INFO
    log.basicConfig(format="%(levelname)s>> %(message)s", level=log_level)
    if len(sys.argv) == 2:
        name = sys.argv[1]
    else:
        log.error(_("Please supply a table name to setup."))
        sys.exit(2)
    PreferencesDialog(name).run()

if __name__ == "__main__":
    main()
