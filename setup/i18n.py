# -*- coding: utf-8 -*-
# vim:et sts=4 sw=4
#
# ibus-table - The Tables engine for IBus
#
# Copyright (c) 2020 Mike FABIAN <mfabian@redhat.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

from typing import Callable
import locale
import gettext
import os

DOMAINNAME = "ibus-table"

_: Callable[[str], str] = lambda a: gettext.dgettext(DOMAINNAME, a)
N_: Callable[[str], str] = lambda a: a

def init() -> None:
    localedir = os.getenv("IBUS_LOCALEDIR")
    # Python's locale module doesn't provide all methods on some
    # operating systems like FreeBSD
    try:
        # for non-standard localedir
        locale.bindtextdomain(DOMAINNAME, localedir) # type: ignore
    except AttributeError:
        pass
    gettext.bindtextdomain(DOMAINNAME, localedir)
