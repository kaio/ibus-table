# Process this file with autoconf to produce a configure script.
# vim:set et ts=4:
#
# ibus-table - The Tables engine for IBus
#
# Copyright (c) 2008-2009 Yu Yuwei <acevery@gmail.com>
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

m4_define([package_name], [ibus-table])
# if not 1, append datestamp to the version number.
m4_define([ibus_released], [1])
m4_define([ibus_major_version], [1])
m4_define([ibus_minor_version], [19])
m4_define([ibus_micro_version], [0])
m4_define(ibus_maybe_datestamp,
    m4_esyscmd([if test ]ibus_released[ != 1; then date +.%Y%m%d | tr -d '\n\r'; fi]))

m4_define([ibus_version],
    ibus_major_version.ibus_minor_version.ibus_micro_version[]ibus_maybe_datestamp)

AC_INIT([package_name],[ibus_version],[https://github.com/mike-fabian/ibus-table/issues],[package_name])
AM_INIT_AUTOMAKE([1.10])
AM_MAINTAINER_MODE
# AC_USE_SYSTEM_EXTENSIONS

# AC_CONFIG_HEADERS([config.h])
AC_CONFIG_MACRO_DIR([m4])

#check python
AM_PATH_PYTHON([3.9])

# check for ibus
PKG_CHECK_MODULES([IBUS],[ibus-1.0 >= 1.1.0])

# define GETTEXT_* variables
GETTEXT_PACKAGE=ibus-table
AC_SUBST(GETTEXT_PACKAGE)
AC_DEFINE_UNQUOTED(GETTEXT_PACKAGE,"$GETTEXT_PACKAGE", [Define to the read-only architecture-independent data directory.])

AM_GNU_GETTEXT([external])
AM_GNU_GETTEXT_VERSION(0.16.1)

AC_ARG_ENABLE([installed-tests],
    [AS_HELP_STRING([--enable-installed-tests],
                   [Enable to install tests])],
    [enable_installed_tests=$enableval],
    [enable_installed_tests=no]
)

AM_CONDITIONAL([ENABLE_INSTALLED_TESTS], [test x"$enable_installed_tests" = x"yes"])

# OUTPUT files
AC_CONFIG_FILES([po/Makefile.in
    Makefile
    engine/Makefile
    engine/ibus-engine-table
    engine/ibus-table-createdb
    engine/table.xml.in
    engine/version.py
    data/Makefile
    icons/Makefile
    tables/Makefile
    m4/Makefile
    setup/Makefile
    setup/ibus-setup-table
    setup/version.py
    tests/Makefile
    ibus-table.spec
    ibus-table.pc]
)

AC_OUTPUT

AC_MSG_RESULT([
Build options:
  Version                   $VERSION
  Install prefix            $prefix
])
