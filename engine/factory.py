# vim:et sw=4 sts=4 sw=4
#
# ibus-table - The Tables engine for IBus
#
# Copyright (c) 2008-2009 Yu Yuwei <acevery@gmail.com>
# Copyright (c) 2009-2014 Caius "kaio" CHANCE <me@kaio.net>
# Copyright (c) 2012-2015, 2021-2022 Mike FABIAN <mfabian@redhat.com>
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
TabEngine Factory
'''
from typing import Dict
from typing import Optional
from typing import Callable
import os
import re
import logging
from gettext import dgettext
_: Callable[[str], str] = lambda a: dgettext("ibus-table", a)
N_: Callable[[str], str] = lambda a: a
from gi import require_version # type: ignore
# pylint: disable=wrong-import-position
require_version('IBus', '1.0')
from gi.repository import IBus # type: ignore
# pylint: enable=wrong-import-position
import table
import tabsqlitedb

LOGGER = logging.getLogger('ibus-table')

DEBUG_LEVEL = int(0)

class EngineFactory(IBus.Factory): # type: ignore
    """Table IM Engine Factory"""
    def __init__(self, bus: IBus.Bus, db: str = '') -> None:
        global DEBUG_LEVEL # pylint: disable=global-statement
        try:
            DEBUG_LEVEL = int(str(os.getenv('IBUS_TABLE_DEBUG_LEVEL')))
        except (TypeError, ValueError):
            DEBUG_LEVEL = int(0)
        if DEBUG_LEVEL > 1:
            LOGGER.debug('EngineFactory.__init__(bus=%s, db=%s)\n', bus, db)
        self.db: Optional[tabsqlitedb.TabSqliteDb] = None
        self.dbdict: Dict[str, tabsqlitedb.TabSqliteDb] = {}
        # db is the full path to the sql database
        if db:
            self.dbusname = os.path.basename(db).replace('.db', '')
            udb = os.path.basename(db).replace('.db', '-user.db')
            self.db = tabsqlitedb.TabSqliteDb(filename=db, user_db=udb)
            self.db.db.commit()
            self.dbdict = {self.dbusname:self.db}

        # init factory
        self.bus = bus
        super().__init__(connection=bus.get_connection(),
                         object_path=IBus.PATH_FACTORY)
        self.engine_id = 0
        self.engine_path = ''

    def do_create_engine( # pylint: disable=arguments-differ
            self, engine_name: str) -> table.TabEngine:
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'EngineFactory.do_create_engine(engine_name=%s)\n',
                engine_name)
        engine_name = re.sub(r'^table:', '', engine_name)
        engine_base_path = "/com/redhat/IBus/engines/table/%s/engine/"
        path_patt = re.compile(r'[^a-zA-Z0-9_/]')
        self.engine_path = engine_base_path % path_patt.sub('_', engine_name)
        try:
            if not self.db:
                # first check self.dbdict
                if engine_name not in self.dbdict:
                    db_dir = '/usr/share/ibus-table/tables'
                    if os.getenv('IBUS_TABLE_LOCATION'):
                        db_dir = os.path.join(
                            str(os.getenv('IBUS_TABLE_LOCATION')), 'tables')
                    db = os.path.join(db_dir, engine_name+'.db')
                    udb = engine_name+'-user.db'
                    if not os.path.exists(db):
                        byo_db_dir = os.path.expanduser('~/.ibus/byo-tables')
                        db = os.path.join(byo_db_dir, engine_name + '.db')
                    _sq_db = tabsqlitedb.TabSqliteDb(filename=db, user_db=udb)
                    _sq_db.db.commit()
                    self.dbdict[engine_name] = _sq_db

            engine = table.TabEngine(self.bus,
                                     self.engine_path + str(self.engine_id),
                                     self.dbdict[engine_name])
            self.engine_id += 1
            #return engine.get_dbus_object()
            return engine
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'Failed to create engine %s: %s: %s',
                engine_name, error.__class__.__name__, error)
            raise Exception from error # pylint: disable=broad-exception-raised

    def do_destroy(self) -> None: # pylint: disable=arguments-differ
        '''Destructor, which finish some task for IME'''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('EngineFactory.do_destroy()\n')
        #
        ## we need to sync the temp userdb in memory to the user_db on disk
        for key, database in self.dbdict.items():
            LOGGER.info('Syncing %s %s', key, database)
            database.sync_usrdb()
        ##print "Have synced user db\n"
        super().destroy()
