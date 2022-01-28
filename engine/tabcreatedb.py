#!/usr/bin/python3
# -*- coding: utf-8 -*-
# vim:et sts=4 sw=4
#
# ibus-table - The Tables engine for IBus
#
# Copyright (c) 2008-2009 Yu Yuwei <acevery@gmail.com>
# Copyright (c) 2009-2014 Caius "kaio" CHANCE <me@kaio.net>
# Copyright (c) 2012-2015, 2021-2022 Mike FABIAN <mfabian@redhat.com>
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
Program to create sqlite databases from the table sources
'''

from typing import Tuple
from typing import List
from typing import Iterable
from typing import Dict
from typing import Any
import os
import sys
import bz2
import re
import argparse
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import tabsqlitedb

_INVALID_KEYNAME_CHARS = " \t\r\n\"$&<>,+=#!()'|{}[]?~`;%\\"

def gconf_valid_keyname(keyname: str) -> bool:
    """
    Keynames must be ascii, and must not contain any invalid characters

    >>> gconf_valid_keyname('nyannyan')
    True

    >>> gconf_valid_keyname('nyan nyan')
    False

    >>> gconf_valid_keyname('nyannyan[')
    False

    >>> gconf_valid_keyname('nyan\tnyan')
    False
    """
    return not any(char in _INVALID_KEYNAME_CHARS or ord(char) > 127
                   for char in keyname)

class InvalidTableName(Exception):
    """
    Raised when an invalid table name is given
    """
    def __init__(self, name: str) -> None:
        super().__init__()
        self.table_name = name

    def __str__(self) -> str:
        return ('Value of NAME attribute (%s) ' % self.table_name
                + 'cannot contain any of %r ' % _INVALID_KEYNAME_CHARS
                + 'and must be all ascii')

def parse_args() -> Any:
    '''Parse the command line arguments'''
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-n', '--name',
        action='store',
        dest='name',
        default='',
        help=('Specifies the file name for the binary database for the IME. '
              'The default is “%(default)s”. If the file name of the database '
              'is not specified, the file name of the source file before '
              'the first “.” will be appended with “.db” and that will be '
              'used as the file name of the database.'))
    parser.add_argument(
        '-s', '--source',
        action='store',
        dest='source',
        default='',
        help=('Specifies the file which contains the source of the IME. '
              'The default is “%(default)s”.'))
    parser.add_argument(
        '-e', '--extra',
        action='store',
        dest='extra',
        default='',
        help=('Specifies the file name for the extra words for the IME. '
              'The default is “%(default)s”.'))
    parser.add_argument(
        '-p', '--pinyin',
        action='store',
        dest='pinyin',
        default='/usr/share/ibus-table/data/pinyin_table.txt.bz2',
        help=('Specifies the source file for the  pinyin. '
              'The default is “%(default)s”.'))
    parser.add_argument(
        '-g', '--suggestion',
        action='store',
        dest='suggestion',
        default='/usr/share/ibus-table/data/phrase.txt.bz2',
        help=('Specifies the source file for the suggestion candidate. '
              'The default is “%(default)s”.'))
    parser.add_argument(
        '-o', '--no-create-index',
        action='store_false',
        dest='index',
        default=True,
        help=('Do not create an index for a database '
              '(Only for distribution purposes, '
              'a normal user should not use this flag!). '
              'The default is “%(default)s”.'))
    parser.add_argument(
        '-i', '--create-index-only',
        action='store_true',
        dest='only_index',
        default=False,
        help=('Only create an index for an existing database. '
              'Specifying the file name of the binary database '
              'with the -n or --name option is required '
              'when this option is used.'
              'The default is “%(default)s”.'))
    parser.add_argument(
        '-d', '--debug',
        action='store_true',
        dest='debug',
        default=False,
        help=('Print extra debug messages. '
              'The default is “%(default)s”.'))
    return parser.parse_args()

_ARGS = parse_args()

if _ARGS.only_index:
    if not _ARGS.name:
        print('\nPlease specify the file name of the database '
              'you want to create an index on!')
        sys.exit(2)
    if not os.path.exists(_ARGS.name) or not os.path.isfile(_ARGS.name):
        print("\nThe database file '%s' does not exist." % _ARGS.name)
        sys.exit(2)

if not _ARGS.name and _ARGS.source:
    _ARGS.name = os.path.basename(_ARGS.source).split('.')[0] + '.db'

if not _ARGS.name:
    print('\nYou need to specify the file which '
          'contains the source of the IME!')
    sys.exit(2)


class Section:
    '''Helper class for parsing the sections of the tables marked
    with BEGIN_* and END_*.
    '''
    patt: re.Pattern[str]
    start: str
    end: str
    in_section: bool

    def __init__(self, patt: re.Pattern[str], start: str, end: str):
        self.patt = patt
        self.start = start.strip()
        self.end = end.strip()
        self.in_section = False

    def match(self, line: str) -> bool:
        '''
        Returns True if the line is inside the section and matches
        the pattern of the section.
        '''
        if self.in_section:
            if self.end == line.strip():
                self.in_section = False
            elif self.patt.match(line):
                return True
        elif self.start == line.strip():
            self.in_section = True

        return False


def main() -> None:
    '''Main program'''

    def debug_print(message: str) -> None:
        if _ARGS.debug:
            print(message)

    if not _ARGS.only_index:
        try:
            os.unlink(_ARGS.name)
        except Exception:
            pass

    debug_print('Processing Database')
    db = tabsqlitedb.TabSqliteDb(filename=_ARGS.name,
                                 user_db='',
                                 create_database=True)

    def parse_source(
            f: Iterable[str]) -> Tuple[List[str], List[str], List[str]]:
        _attri: List[str] = []
        _table: List[str] = []
        _table_extra: List[str] = []
        _gouci: List[str] = []
        patt_com = re.compile(r'^###.*')
        patt_blank = re.compile(r'^[ \t]*$')
        patt_conf = re.compile(r'[^\t]*=[^\t]*')
        patt_table = re.compile(r'([^\t]+)\t([^\t]+)\t([0-9]+)(\t.*)?$')
        patt_gouci = re.compile(r' *[^\s]+ *\t *[^\s]+ *$')

        sec_conf = Section(
            patt_conf, "BEGIN_DEFINITION", "END_DEFINITION")
        sec_table = Section(
            patt_table, "BEGIN_TABLE", "END_TABLE")
        sec_table_extra = Section(
            patt_table, "BEGIN_TABLE_EXTRA", "END_TABLE_EXTRA")
        sec_gouci = Section(
            patt_gouci, "BEGIN_GOUCI", "END_GOUCI")

        for line in f:
            if (not patt_com.match(line)) and (not patt_blank.match(line)):
                for _sec, _list in (
                        (sec_table, _table),
                        (sec_table_extra, _table_extra),
                        (sec_gouci, _gouci),
                        (sec_conf, _attri)):
                    if _sec.match(line):
                        _list.append(line)
                        break

        if not _gouci:
            # The user didn’t provide goucima (goucima = 構詞碼 =
            # “word formation keys”) in the table source, so we use
            # the longest encoding for a single character as the
            # goucima for that character.
            #
            # Example:
            #
            # wubi-jidian86.txt contains:
            #
            #     a         工      99454797
            #     aaa	工      551000000
            #     aaaa      工      551000000
            #     aaad      工期    5350000
            #     ... and more matches for compounds containing 工
            #
            # The longest key sequence to type 工 as a single
            # character is “aaaa”.  Therefore, the goucima of 工 is
            # “aaaa” (There is one other character with the same goucima
            # in  wubi-jidian86.txt, 㠭 also has the goucima “aaaa”).
            gouci_dict: Dict[str, str] = {}
            for line in _table:
                res = patt_table.match(line)
                if res and len(res.group(2)) == 1:
                    if res.group(2) in gouci_dict:
                        if len(res.group(1)) > len(gouci_dict[res.group(2)]):
                            gouci_dict[res.group(2)] = res.group(1)
                    else:
                        gouci_dict[res.group(2)] = res.group(1)
            for key in gouci_dict:
                _gouci.append('%s\t%s' %(key, gouci_dict[key]))
            _gouci.sort()

        _table += _table_extra
        return (_attri, _table, _gouci)

    def parse_pinyin(f: Iterable[str]) -> List[str]:
        _pinyins: List[str] = []
        patt_com = re.compile(r'^#.*')
        patt_blank = re.compile(r'^[ \t]*$')
        patt_py = re.compile(r'(.*)\t(.*)\t(.*)')
        patt_yin = re.compile(r'[a-z]+[1-5]')

        for line in f:
            if (not patt_com.match(line)) and (not patt_blank.match(line)):
                res = patt_py.match(line)
                if res:
                    yins = patt_yin.findall(res.group(2))
                    for yin in yins:
                        _pinyins.append("%s\t%s\t%s" \
                                % (res.group(1), yin, res.group(3)))
        return _pinyins[:]

    def parse_suggestion(f: Iterable[str]) -> List[str]:
        _suggestions: List[str] = []
        patt_com = re.compile(r'^#.*')
        patt_blank = re.compile(r'^[ \t]*$')
        patt_sg = re.compile(r'(.*)\s+(.*)')

        for line in f:
            if (not patt_com.match(line)) and (not patt_blank.match(line)):
                res = patt_sg.match(line)
                if res:
                    phrase = res.group(1)
                    freq = res.group(2)
                    _suggestions.append("%s %s" % (phrase, freq))
        return _suggestions[:]

    def parse_extra(f: Iterable[str]) -> List[str]:
        _extra: List[str] = []
        patt_com = re.compile(r'^###.*')
        patt_blank = re.compile(r'^[ \t]*$')
        patt_extra = re.compile(r'(.*)\t(.*)')

        for line in f:
            if (not patt_com.match(line)) and (not patt_blank.match(line)):
                if patt_extra.match(line):
                    _extra.append(line)

        return _extra

    def pinyin_parser(f: Iterable[str]) -> Iterable[Tuple[str, str, int]]:
        for pinyin_line in f:
            _zi, _pinyin, _freq = pinyin_line.strip().split()
            yield (_pinyin, _zi, int(_freq))

    def suggestion_parser(f: Iterable[str]) -> Iterable[Tuple[str, int]]:
        for suggestion_line in f:
            _phrase, _freq = suggestion_line.strip().split()
            yield (_phrase, int(_freq))

    def phrase_parser(f: Iterable[str]) -> List[Tuple[str, str, int, int]]:
        phrase_list: List[Tuple[str, str, int, int]] = []
        for line in f:
            xingma, phrase, freq = line.split('\t')[:3]
            if phrase == 'NOSYMBOL':
                phrase = u''
            phrase_list.append((xingma, phrase, int(freq), 0))
        return phrase_list

    def goucima_parser(f: Iterable[str]) -> Iterable[Tuple[str, str]]:
        for line in f:
            zi, gcm = line.strip().split()
            yield (zi, gcm)

    def attribute_parser(f: Iterable[str]) -> Iterable[Tuple[str, str]]:
        for line in f:
            try:
                attr, val = line.strip().split('=')
            except Exception:
                attr, val = line.strip().split('==')
            attr = attr.strip().lower()
            val = val.strip()
            yield (attr, val)

    def extra_parser(f: Iterable[str]) -> List[Tuple[str, str, int, int]]:
        extra_list: List[Tuple[str, str, int, int]] = []
        for line in f:
            phrase, freq = line.strip().split()
            _tabkey = db.parse_phrase(phrase)
            if _tabkey:
                extra_list.append((_tabkey, phrase, int(freq), 0))
            else:
                print('No tabkeys found for “%s”, not adding.\n' %phrase)
        return extra_list

    def get_char_prompts(f: Iterable[str]) -> Tuple[str, str]:
        '''
        Returns something like

        ("char_prompts", "{'a': '日', 'b': '日', 'c': '金', ...}")

        i.e. the attribute name "char_prompts" and as its value
        the string representation of a Python dictionary.
        '''
        char_prompts: Dict[str, str] = {}
        start = False
        for line in f:
            if re.match(r'^BEGIN_CHAR_PROMPTS_DEFINITION', line):
                start = True
                continue
            if not start:
                continue
            if re.match(r'^END_CHAR_PROMPTS_DEFINITION', line):
                break
            match = re.search(
                r'^(?P<char>[^\s]+)[\s]+(?P<prompt>[^\s]+)', line)
            if match:
                char_prompts[match.group('char')] = match.group('prompt')
        return ("char_prompts", repr(char_prompts))

    if _ARGS.only_index:
        debug_print('Only create Indexes')
        debug_print('Optimizing database ')
        db.optimize_database()

        debug_print('Create Indexes ')
        db.create_indexes('main')
        debug_print('Done! :D')
        return

    # now we parse the ime source file
    debug_print('\tLoad sources "%s"' % _ARGS.source)
    patt_s = re.compile(r'.*\.bz2')
    _bz2s = patt_s.match(_ARGS.source)
    if _bz2s:
        source_str = bz2.open(
            _ARGS.source, mode='rt', encoding='UTF-8').read()
    else:
        source_str = open(_ARGS.source, mode='r', encoding='UTF-8').read()
    source_str = source_str.replace('\r\n', '\n')
    source = source_str.split('\n')
    # first get config line and table line and goucima line respectively
    debug_print('\tParsing table source file ')
    attri, table, gouci = parse_source(source)

    debug_print('\t  get attribute of IME :)')
    attributes = list(attribute_parser(attri))
    attributes.append(get_char_prompts(source))
    debug_print('\t  add attributes into DB ')
    db.update_ime(attributes)
    db.create_tables('main')

    # second, we use generators for database generating:
    debug_print('\t  get phrases of IME :)')
    phrases = phrase_parser(table)

    # now we add things into db
    debug_print('\t  add phrases into DB ')
    db.add_phrases(phrases)

    if db.ime_properties.get('user_can_define_phrase').lower() == u'true':
        debug_print('\t  get goucima of IME :)')
        goucima = goucima_parser(gouci)
        debug_print('\t  add goucima into DB ')
        db.add_goucima(goucima)

    if db.ime_properties.get('pinyin_mode').lower() == u'true':
        debug_print('\tLoad pinyin source \"%s\"' % _ARGS.pinyin)
        _bz2p = patt_s.match(_ARGS.pinyin)
        if _bz2p:
            pinyin_s = bz2.open(_ARGS.pinyin, mode='rt', encoding='UTF-8')
        else:
            pinyin_s = open(_ARGS.pinyin, mode='r', encoding='UTF-8')
        debug_print('\tParsing pinyin source file ')
        pyline = parse_pinyin(pinyin_s)
        debug_print('\tPreapring pinyin entries')
        pinyin = pinyin_parser(pyline)
        debug_print('\t  add pinyin into DB ')
        db.add_pinyin(pinyin)

    if db.ime_properties.get('suggestion_mode').lower() == u'true':
        debug_print('\tLoad suggestion source \"%s\"' % _ARGS.suggestion)
        _bz2p = patt_s.match(_ARGS.suggestion)
        if _bz2p:
            suggestion_s = bz2.open(
                _ARGS.suggestion, mode="rt", encoding='UTF-8')
        else:
            suggestion_s = open(
                _ARGS.suggestion, mode='r', encoding='UTF-8')
        debug_print('\tParsing suggestion source file ')
        sgline = parse_suggestion(suggestion_s)
        debug_print('\tPreapring suggestion entries')
        suggestions = suggestion_parser(sgline)
        debug_print('\t  add suggestion candidates into DB ')
        db.add_suggestion(suggestions)

    debug_print('Optimizing database ')
    db.optimize_database()

    if (db.ime_properties.get('user_can_define_phrase').lower() == u'true'
            and _ARGS.extra):
        debug_print('\tPreparing for adding extra words')
        db.create_indexes('main')
        debug_print('\tLoad extra words source "%s"' % _ARGS.extra)
        _bz2p = patt_s.match(_ARGS.extra)
        if _bz2p:
            extra_s = bz2.open(_ARGS.extra, mode='rt', encoding='UTF-8')
        else:
            extra_s = open(_ARGS.extra, 'r')
        debug_print('\tParsing extra words source file ')
        extraline = parse_extra(extra_s)
        debug_print('\tPreparing extra words lines')
        extrawords = extra_parser(extraline)
        debug_print('\t  we have %d extra phrases from source'
                    % len(extrawords))
        # first get the entry of original phrases from
        # phrases-[(xingma, phrase, int(freq), 0)]
        orig_phrases = {}
        for phrase in phrases:
            orig_phrases.update({"%s\t%s" % (phrase[0], phrase[1]): phrase})
        debug_print('\t  the len of orig_phrases is: %d' % len(orig_phrases))
        extra_phrases = {}
        for extraword in extrawords:
            extra_phrases.update(
                {"%s\t%s" % (extraword[0], extraword[1]): extraword})
        debug_print('\t  the len of extra_phrases is: %d' % len(extra_phrases))
        # pop duplicated keys
        for extra_phrase in extra_phrases:
            if extra_phrase in orig_phrases:
                extra_phrases.pop(extra_phrase)
        debug_print('\t  %d extra phrases will be added' % len(extra_phrases))
        new_phrases = list(extra_phrases.values())
        debug_print('\tAdding extra words into DB ')
        db.add_phrases(new_phrases)
        debug_print('Optimizing database ')
        db.optimize_database()

    if _ARGS.index:
        debug_print('Create Indexes ')
        db.create_indexes('main')
    else:
        debug_print('We do not create an index on the database, '
                    'you should only activate this function '
                    'for distribution purposes.')
        db.drop_indexes('main')
    debug_print('Done! :D')

if __name__ == "__main__":
    main()
