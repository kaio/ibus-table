#!/usr/bin/python3

# generate-chinese-variants
#
# Copyright (c) 2013-2018 Mike FABIAN <mfabian@redhat.com>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3.0 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from typing import Any
import re
import logging
import sys

# Unihan_Variants.txt contains the following 2 lines:
#
# U+50DE  kSimplifiedVariant      U+4F2A
# U+50DE  kTraditionalVariant     U+507D U+50DE
#
# This seems to be currently the only case in Unihan_Variants.txt where
# a character which has entries for kTraditionalVariant and
# the same character is listed again among the traditional variants
# is *not* simplified Chinese.
#
# U+50DE 僞 is traditional Chinese.
# U+507D 偽 is also traditional Chinese.
# U+4F2A 伪 is simplified Chinese
#
# This does not cause a problem with the current parsing code
# of Unihan_Variants.txt because the line
#
# U+50DE  kSimplifiedVariant      U+4F2A
#
# is read first and thus the character is already inserted in the
# “VARIANTS_TABLE_ORIG” dictionary as traditional Chinese, which is correct.
# If a character is already in the dictionary and more lines for the
# same character are read from Unihan_Variants.txt, these extra lines
# are ignored.
#
# But maybe for some corner cases more tweaking of the code is
# necessary. One can also add overrides manually to the
# initial content of “VARIANTS_TABLE_ORIG”.

VARIANTS_TABLE_ORIG = {
    # Meaning of the bits in the values:
    # 1 = 1 << 0       simplified Chinese
    # 2 = 1 << 1       traditional Chinese
    # 3 = (1 | 1 << 1) used both in simplified *and* traditional Chinese
    # 4 = 1 << 2       mixture of simplified and traditional Chinese
    #
    # overrides can be added manually here. For example the following
    # line marks the 〇 character as used in both
    # simplified and traditional Chinese:
    '〇': 3 # simplified *and* traditional Chinese
    }

# keep the lines from Unihan_Variants.txt which were used for debugging
VARIANTS_TABLE_ORIG_UNIHAN_VARIANTS_ENTRY_USED = {}

def read_unihan_variants(unihan_variants_file) -> None:
    '''
    Read the Unihan_Variants.txt file downloaded  from Unicode.org.
    '''
    for line in unihan_variants_file:
        line = line.strip()
        if not re.match('^#', line):
            if re.search('(kTraditionalVariant|kSimplifiedVariant)', line):
                match = re.match(r'^U\+([0-9A-F]{4,5})', line)
                if match:
                    char = chr(int(match.group(1), 16))
                    category = 0 # should never  stay at this value
                    if re.match(re.escape(match.group(0))
                                + r'.*'
                                + re.escape(match.group(0)), line):
                        # is both simplified and traditional
                        category = 1 | 1 << 1
                    elif re.search('kTraditionalVariant', line):
                        category = 1 # simplified only
                    elif re.search('kSimplifiedVariant', line):
                        category = 1 << 1 # traditional only
                    logging.debug(
                        'char=%s category=%d line=%s',
                        char, category, line)
                    if char not in VARIANTS_TABLE_ORIG:
                        VARIANTS_TABLE_ORIG[char] = category
                    if (char not in VARIANTS_TABLE_ORIG_UNIHAN_VARIANTS_ENTRY_USED):
                        VARIANTS_TABLE_ORIG_UNIHAN_VARIANTS_ENTRY_USED[
                            char] = line

def detect_chinese_category_old(phrase: str) -> int:
    '''
    Old function using encoding conversion to guess whether
    a text is simplified Chinese, traditional Chinese, both,
    or unknown. Does not work well, is included here for reference
    and for comparing with the results of the new, improved function
    using the data from the Unihan database.
    '''
    # this is the bitmask we will use,
    # from low to high, 1st bit is simplified Chinese,
    # 2nd bit is traditional Chinese,
    # 3rd bit means out of gbk
    category = 0
    # make sure that we got a unicode string
    tmp_phrase = ''.join(re.findall('['
                                    + '\u4E00-\u9FCB'
                                    + '\u3400-\u4DB5'
                                    + '\uF900-\uFaFF'
                                    + '\U00020000-\U0002A6D6'
                                    + '\U0002A700-\U0002B734'
                                    + '\U0002B740-\U0002B81D'
                                    + '\U0002F800-\U0002FA1D'
                                    + ']+',
                                    phrase))
    # first whether in gb2312
    try:
        tmp_phrase.encode('gb2312')
        category |= 1
    except:
        if '〇' in tmp_phrase:
            # we add '〇' into SC as well
            category |= 1
    # second check big5-hkscs
    try:
        tmp_phrase.encode('big5hkscs')
        category |= 1 << 1
    except:
        # then check whether in gbk,
        if category & 1:
            # already know in SC
            pass
        else:
            # need to check
            try:
                tmp_phrase.encode('gbk')
                category |= 1
            except:
                # not in gbk
                pass
    # then set for 3rd bit, if not in SC and TC
    if not category & (1 | 1 << 1):
        category |= (1 << 2)
    return category

def write_variants_script(script_file) -> None:
    '''
    Write the generated Python script.
    '''
    script_file.write('''# auto-generated by “generate-chinese-variants.py”, do not edit here!
#
# Copyright (c) 2013 Mike FABIAN <mfabian@redhat.com>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3.0 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
''')

    script_file.write('''
import sys
''')

    script_file.write('''
VARIANTS_TABLE = {
    # Meaning of the bits in the values:
    # 1 = 1 << 0       simplified Chinese
    # 2 = 1 << 1       traditional Chinese
    # 3 = (1 | 1 << 1) used both in simplified *and* traditional Chinese
    # 4 = 1 << 2       mixture of simplified and traditional Chinese
''')

    for phrase in sorted(VARIANTS_TABLE_ORIG):
        script_file.write(
            "    '" + phrase + "': "
            + "%s" %VARIANTS_TABLE_ORIG[phrase] + ",\n")

    script_file.write('''    }
''')

    script_file.write('''
def detect_chinese_category(phrase: str) -> int:
    \'\'\'
    New function using Unihan data to guess whether a text is
    simplified Chinese, traditional Chinese, both, or something rare
    like a mixture of exclusively simplified with exclusively traditional
    characters.

    Meaning of the bits in the category value returned by this function:
    1 = 1 << 0       simplified Chinese
    2 = 1 << 1       traditional Chinese
    3 = (1 | 1 << 1) used both in simplified *and* traditional Chinese
    4 = 1 << 2       mixture of simplified and traditional Chinese
    \'\'\'
    # make sure that we got a unicode string
    if phrase in VARIANTS_TABLE:
        # the complete phrase is in VARIANTS_TABLE, just return the
        # value found:
        return VARIANTS_TABLE[phrase]
    category = 0xFF
    for char in phrase:
        if char in VARIANTS_TABLE:
            category &= VARIANTS_TABLE[char]
        else:
            # If it is not listed in VARIANTS_TABLE, assume it is
            # both simplified and traditional Chinese.
            # It could be something non-Chinese as well then, but
            # if it is non-Chinese, it should also be allowed to
            # occur in any Chinese text and thus classified as
            # both simplified *and* traditional Chinese (the emoji
            # table for example uses many non-Chinese characters)
            category &= (1 | 1 << 1)
    if category == 0:
        # If category is 0 after binary & of the categories of all the
        # characters in the phrase, it means that the phrase contained
        # exclusively simplified *and* exclusively traditional
        # characters at the same time.  For example if the phrase is
        # “乌烏” then “乌” gets category 1 (simplified Chinese)
        # and “烏” gets category 2 (traditional Chinese), the result
        # of the binary & is thus 0. In that case, classify it as
        # category 4 which is for weird, excentric, rare stuff. If the
        # user selects one of the modes “all characters but
        # simplified Chinese first” or “all characters but
        # traditional Chinese first”, phrases with category 4 will be
        # shown but filtered to be shown only at the end of the
        # candidate list.
        category = 1 << 2
    return category
''')

TEST_DATA = {
    # Meaning of the bits in the values:
    # 1 = 1 << 0       simplified Chinese
    # 2 = 1 << 1       traditional Chinese
    # 3 = (1 | 1 << 1) used both in simplified *and* traditional Chinese
    # 4 = 1 << 2       mixture of simplified and traditional Chinese
    '乌': 1,
    '烏': 2,
    '晞': 3,
    '䖷': 3,
    '乌烏': 4,
    'a☺α乌': 1,
    'a☺α烏': 2,
    '台': 3,
    '同': 3,
    '表': 3, # U+8868
    '面': 3, # U+9762
    # Characters below this comments probably have buggy entries
    # in Unihan_Variants.txt:
    '覆': 3, # U+8986
    '杰': 3, # U+6770
    '系': 3, # U+7CFB
    '乾': 3, # U+4E7E
    '著': 3, # U+8457 Patch by Heiher <r@hev.cc>
    '只': 3, # U+53EA, see: https://github.com/kaio/ibus-table/issues/74
    # Problems reported in https://github.com/ibus/ibus/issues/2323
    '着': 3, # U+7740, used in HK
    '枱': 3, # U+67B1, used in HK (correct already, no SC variant entry in Unihan_Variants.txt)
    '云': 3, # U+4E91, used in HK and TW
    '裡': 3, # U+88E1, (Untypable in S) used in all places same meaning as 裏
    '復': 3, # U+5FA9, (Untypable in S) used in all places same meaning in S, diff in T
    '采': 3, # U+91C7, (Untypable in T) used in Hong Kong, not sure about TW
    # http://dict.revised.moe.edu.tw/cgi-bin/cbdic/gsweb.cgi has 采, i.e. probably
    # it is used in TW
    '吓': 3, # U+5413, (Untypable in T) used in Cantonese.
    '尸': 3, # U+5C38, (Untypable in T) idk where it is used, but Cangjie has that as a radical.
    '揾': 3, # U+63FE, used in HK
    # (TW seems to use only 搵, see http://dict.revised.moe.edu.tw/cgi-bin/cbdic/gsweb.cgi)
    '栗': 3, # U+6817 https://github.com/mike-fabian/ibus-table/issues/95
    '了': 3, # U+4E86 https://github.com/mike-fabian/ibus-table/issues/96
    '伙': 3, # U+4F19 https://github.com/mike-fabian/ibus-table/issues/96
    '借': 3, # U+501F https://github.com/mike-fabian/ibus-table/issues/96
    '冬': 3, # U+51AC https://github.com/mike-fabian/ibus-table/issues/96
    '千': 3, # U+5343 https://github.com/mike-fabian/ibus-table/issues/96
    '卜': 3, # U+535C https://github.com/mike-fabian/ibus-table/issues/96
    '卷': 3, # U+5377 https://github.com/mike-fabian/ibus-table/issues/96
    '吁': 3, # U+5401 https://github.com/mike-fabian/ibus-table/issues/96
    '合': 3, # U+5408 https://github.com/mike-fabian/ibus-table/issues/96
    '回': 3, # U+56DE https://github.com/mike-fabian/ibus-table/issues/96
    '夥': 3, # U+5925 https://github.com/mike-fabian/ibus-table/issues/96
    '姜': 3, # U+59DC https://github.com/mike-fabian/ibus-table/issues/96
    '家': 3, # U+5BB6 https://github.com/mike-fabian/ibus-table/issues/96
    '才': 3, # U+624D https://github.com/mike-fabian/ibus-table/issues/96
    '折': 3, # U+6298 https://github.com/mike-fabian/ibus-table/issues/96
    '摺': 3, # U+647A https://github.com/mike-fabian/ibus-table/issues/96
    '旋': 3, # U+65CB https://github.com/mike-fabian/ibus-table/issues/96
    '朱': 3, # U+6731 https://github.com/mike-fabian/ibus-table/issues/96
    '灶': 3, # U+7076 https://github.com/mike-fabian/ibus-table/issues/96
    '秋': 3, # U+79CB https://github.com/mike-fabian/ibus-table/issues/96
    '蒙': 3, # U+8499 https://github.com/mike-fabian/ibus-table/issues/96
    '蔑': 3, # U+8511 https://github.com/mike-fabian/ibus-table/issues/96
    '霉': 3, # U+9709 https://github.com/mike-fabian/ibus-table/issues/96
    '沄': 3, # U+6C84 https://github.com/mike-fabian/ibus-table/issues/97
    # https://dict.revised.moe.edu.tw/search.jsp?md=1&word=%E6%B2%84&qMd=0&qCol=1
    '干': 3, # U+5E72 https://github.com/mike-fabian/ibus-table/issues/97
    # See https://github.com/mike-fabian/ibus-table/issues/100 especially:
    # https://github.com/mike-fabian/ibus-table/issues/100#issuecomment-1020358521
    # These characters were classified as “Simplified only” but they are in
    # this dictionary: https://dict.revised.moe.edu.tw/
    '时': 3, # U+65F6 https://github.com/mike-fabian/ibus-table/issues/100
    '旷': 3, # U+65F7 ...
    '晒': 3, # U+6652 ...
    '幂': 3, # U+5E42 ...
    '胆': 3, # U+80C6 ...
    '册': 3, # U+518C ...
    '脚': 3, # U+811A ...
    '胜': 3, # U+80DC ...
    '脉': 3, # U+8109 ...
    '膑': 3, # U+8191 ...
    '网': 3, # U+7F51 ...
    '删': 3, # U+5220 ...
    '腼': 3, # U+817C ...
    '脍': 3, # U+810D ...
    '腭': 3, # U+816D ...
    '腊': 3, # U+814A ...
    '眦': 3, # U+7726 ...
    '肮': 3, # U+80AE ...
    '谷': 3, # U+8C37 ...
    '兑': 3, # U+5151 ...
    '单': 3, # U+5355 ...
    '栅': 3, # U+6805 ...
    '松': 3, # U+677E ...
    '梦': 3, # U+68A6 ...
    '权': 3, # U+6743 ...
    '楼': 3, # U+697C ...
    '栀': 3, # U+6800 ...
    '机': 3, # U+673A ...
    '栖': 3, # U+6816 ...
    '杆': 3, # U+6746 ...
    '标': 3, # U+6807 ...
    '构': 3, # U+6784 ...
    '柜': 3, # U+67DC ...
    '朴': 3, # U+6734 ...
    '温': 3, # U+6E29 ...
    '泪': 3, # U+6CEA ...
    '对': 3, # U+5BF9 ...
    '双': 3, # U+53CC ...
    '叠': 3, # U+53E0 ...
    '滩': 3, # U+6EE9 ...
    '洼': 3, # U+6D3C ...
    '没': 3, # U+6CA1 ...
    '沪': 3, # U+6CAA ...
    '戏': 3, # U+620F ...
    '浅': 3, # U+6D45 ...
    '沪': 3, # U+6CAA ...
    '滨': 3, # U+6EE8 ...
    '劝': 3, # U+529D ...
    '沈': 3, # U+6C88 ...
    '渊': 3, # U+6E0A ...
    '洒': 3, # U+6D12 ...
    '㳽': 3, # U+3CFD ...
    '欢': 3, # U+6B22 ...
    '难': 3, # U+96BE ...
    '涂': 3, # U+6D82 ...
    '涛': 3, # U+6D9B ...
    '汹': 3, # U+6C79 ...
    '滦': 3, # U+6EE6 ...
    '湾': 3, # U+6E7E ...
    '滚': 3, # U+6EDA ...
    '漓': 3, # U+6F13 ...
    '尝': 3, # U+5C1D ...
    '党': 3, # U+515A ...
    '誉': 3, # U+8A89 ...
    '粮': 3, # U+7CAE ...
    '糇': 3, # U+7CC7 ...
    '娄': 3, # U+5A04 ...
    '炉': 3, # U+7089 ...
    '烛': 3, # U+70DB ...
    '灯': 3, # U+706F ...
    '烩': 3, # U+70E9 ...
    '当': 3, # U+5F53 ...
    '烬': 3, # U+70EC ...
    '数': 3, # U+6570 ...
    '烟': 3, # U+70DF ...
    '声': 3, # U+58F0 ...
    '壳': 3, # U+58F3 ...
    '块': 3, # U+5757 ...
    '坂': 3, # U+5742 ...
    '却': 3, # U+5374 ...
    '坏': 3, # U+574F ...
    '坛': 3, # U+575B ...
    '赶': 3, # U+8D76 ...
    '趋': 3, # U+8D8B ...
    '制': 3, # U+5236 ...
    '秃': 3, # U+79C3 ...
    '种': 3, # U+79CD ...
    '秆': 3, # U+79C6 ...
    '称': 3, # U+79F0 ...
    '稳': 3, # U+7A33 ...
    '篓': 3, # U+7BD3 ...
    '丢': 3, # U+4E22 ...
    '笔': 3, # U+7B14 ...
    '躯': 3, # U+8EAF ...
    '么': 3, # U+4E48 ...
    '乔': 3, # U+4E54 ...
    '筑': 3, # U+7B51 ...
    '惩': 3, # U+60E9 ...
    '几': 3, # U+51E0 ...
    '凤': 3, # U+51E4 ...
    '风': 3, # U+98CE ...
    '御': 3, # U+5FA1 ...
    '刮': 3, # U+522E ...
    '乱': 3, # U+4E71 ...
    '辞': 3, # U+8F9E ...
    '笋': 3, # U+7B0B ...
    '衅': 3, # U+8845 ...
    '毡': 3, # U+6BE1 ...
    '鼹': 3, # U+9F39 ...
    '乐': 3, # U+4E50 ...
    '箩': 3, # U+7BA9 ...
    '篱': 3, # U+7BF1 ...
    '术': 3, # U+672F ...
    '应': 3, # U+5E94 ...
    '祢': 3, # U+7962 ...
    '祷': 3, # U+7977 ...
    '礼': 3, # U+793C ...
    '庄': 3, # U+5E84 ...
    '咸': 3, # U+54B8 ...
    '庐': 3, # U+5E90 ...
    '义': 3, # U+4E49 ...
    '参': 3, # U+53C2 ...
    '划': 3, # U+5212 ...
    '庙': 3, # U+5E99 ...
    '减': 3, # U+51CF ...
    '冲': 3, # U+51B2 ...
    '准': 3, # U+51C6 ...
    '凑': 3, # U+51D1 ...
    '况': 3, # U+51B5 ...
    '凉': 3, # U+51C9 ...
    '户': 3, # U+6237 ...
    '献': 3, # U+732E ...
    '穷': 3, # U+7A77 ...
    '帘': 3, # U+5E18 ...
    '窃': 3, # U+7A83 ...
    '灾': 3, # U+707E ...
    '宝': 3, # U+5B9D ...
    '宁': 3, # U+5B81 ...
    '宾': 3, # U+5BBE ...
    '胡': 3, # U+80E1 ...
    '克': 3, # U+514B ...
    '实': 3, # U+5B9E ...
    '郁': 3, # U+90C1 ...
    '刹': 3, # U+5239 ...
    '瘘': 3, # U+7618 ...
    '犹': 3, # U+72B9 ...
    '猪': 3, # U+732A ...
    '独': 3, # U+72EC ...
    '猕': 3, # U+7315 ...
    '狯': 3, # U+72EF ...
    '猫': 3, # U+732B ...
    '猬': 3, # U+732C ...
    '夸': 3, # U+5938 ...
    '疴': 3, # U+75B4 ...
    '症': 3, # U+75C7 ...
    '疱': 3, # U+75B1 ...
    '办': 3, # U+529E ...
    '刾': 3, # U+523E ...
    '痒': 3, # U+75D2 ...
    '袜': 3, # U+889C ...
    '隶': 3, # U+96B6 ...
    '袄': 3, # U+8884 ...
    '蝼': 3, # U+877C ...
    '蚁': 3, # U+8681 ...
    '虾': 3, # U+867E ...
    '虬': 3, # U+866C ...
    '师': 3, # U+5E08 ...
    '归': 3, # U+5F52 ...
    '壮': 3, # U+58EE ...
    '虫': 3, # U+866B ...
    '鼗': 3, # U+9F17 ...
    '儿': 3, # U+513F ...
    '电': 3, # U+7535 ...
    '补': 3, # U+8865 ...
    '厩': 3, # U+53A9 ...
    '霡': 3, # U+9721 ...
    '晋': 3, # U+664B ...
    '于': 3, # U+4E8E ...
    '珐': 3, # U+73D0 ...
    '压': 3, # U+538B ...
    '环': 3, # U+73AF ...
    '琼': 3, # U+743C ...
    '厂': 3, # U+5382 ...
    '动': 3, # U+52A8 ...
    '蚕': 3, # U+8695 ...
    '历': 3, # U+5386 ...
    '无': 3, # U+65E0 ...
    '厉': 3, # U+5389 ...
    '厨': 3, # U+53A8 ...
    '厦': 3, # U+53A6 ...
    '亏': 3, # U+4E8F ...
    '殡': 3, # U+6BA1 ...
    '两': 3, # U+4E24 ...
    '碍': 3, # U+788D ...
    '确': 3, # U+786E ...
    '万': 3, # U+4E07 ...
    '励': 3, # U+52B1 ...
    '开': 3, # U+5F00 ...
    '厮': 3, # U+53AE ...
    '画': 3, # U+753B ...
    '厘': 3, # U+5398 ...
    '堕': 3, # U+5815 ...
    '弹': 3, # U+5F39 ...
    '孙': 3, # U+5B59 ...
    '尔': 3, # U+5C14 ...
    '丑': 3, # U+4E11 ...
    '际': 3, # U+9645 ...
    '隐': 3, # U+9690 ...
    '随': 3, # U+968F ...
    '强': 3, # U+5F3A ...
    '争': 3, # U+4E89 ...
    '皱': 3, # U+76B1 ...
    '龟': 3, # U+9F9F ...
    '复': 3, # U+590D ...
    '内': 3, # U+5185 ...
    '佣': 3, # U+4F63 ...
    '叙': 3, # U+53D9 ...
    '体': 3, # U+4F53 ...
    '仅': 3, # U+4EC5 ...
    '籴': 3, # U+7C74 ...
    '偻': 3, # U+507B ...
    '凭': 3, # U+51ED ...
    '隽': 3, # U+96BD ...
    '仪': 3, # U+4EEA ...
    '优': 3, # U+4F18 ...
    '矫': 3, # U+77EB ...
    '侠': 3, # U+4FA0 ...
    '个': 3, # U+4E2A ...
    '舍': 3, # U+820D ...
    '会': 3, # U+4F1A ...
    '气': 3, # U+6C14 ...
    '从': 3, # U+4ECE ...
    '伤': 3, # U+4F24 ...
    '价': 3, # U+4EF7 ...
    '侩': 3, # U+4FA9 ...
    '众': 3, # U+4F17 ...
    '偬': 3, # U+506C ...
    '俦': 3, # U+4FE6 ...
    '仆': 3, # U+4EC6 ...
    '愠': 3, # U+6120 ...
    '惧': 3, # U+60E7 ...
    '匀': 3, # U+5300 ...
    '恒': 3, # U+6052 ...
    '怀': 3, # U+6000 ...
    '怜': 3, # U+601C ...
    '够': 3, # U+591F ...
    '恼': 3, # U+607C ...
    '担': 3, # U+62C5 ...
    '静': 3, # U+9759 ...
    '摊': 3, # U+644A ...
    '撑': 3, # U+6491 ...
    '挡': 3, # U+6321 ...
    '挂': 3, # U+6302 ...
    '热': 3, # U+70ED ...
    '势': 3, # U+52BF ...
    '蛰': 3, # U+86F0 ...
    '丰': 3, # U+4E30 ...
    '艳': 3, # U+8273 ...
    '摈': 3, # U+6448 ...
    '寿': 3, # U+5BFF ...
    '执': 3, # U+6267 ...
    '抛': 3, # U+629B ...
    '挟': 3, # U+631F ...
    '帮': 3, # U+5E2E ...
    '麦': 3, # U+9EA6 ...
    '挽': 3, # U+633D ...
    '携': 3, # U+643A ...
    '据': 3, # U+636E ...
    '报': 3, # U+62A5 ...
    '掷': 3, # U+63B7 ...
    '摆': 3, # U+6446 ...
    '扑': 3, # U+6251 ...
    '喽': 3, # U+55BD ...
    '响': 3, # U+54CD ...
    '听': 3, # U+542C ...
    '咏': 3, # U+548F ...
    '叶': 3, # U+53F6 ...
    '咤': 3, # U+54A4 ...
    '黾': 3, # U+9EFE ...
    '踪': 3, # U+8E2A ...
    '吴': 3, # U+5434 ...
    '蹰': 3, # U+8E70 ...
    '踊': 3, # U+8E0A ...
    '号': 3, # U+53F7 ...
    '嘱': 3, # U+5631 ...
    '别': 3, # U+522B ...
    '啰': 3, # U+5570 ...
    '屡': 3, # U+5C61 ...
    '属': 3, # U+5C5E ...
    '职': 3, # U+804C ...
    '联': 3, # U+8054 ...
    '耻': 3, # U+803B ...
    '区': 3, # U+533A ...
    '届': 3, # U+5C4A ...
    '昼': 3, # U+663C ...
    '医': 3, # U+533B ...
    '尽': 3, # U+5C3D ...
    '剧': 3, # U+5267 ...
    '荣': 3, # U+8363 ...
    '劳': 3, # U+52B3 ...
    '范': 3, # U+8303 ...
    '盖': 3, # U+76D6 ...
    '芦': 3, # U+82A6 ...
    '蘖': 3, # U+8616 ...
    '荆': 3, # U+8346 ...
    '荐': 3, # U+8350 ...
    '郑': 3, # U+90D1 ...
    '苏': 3, # U+82CF ...
    '黄': 3, # U+9EC4 ...
    '苹': 3, # U+82F9 ...
    '芸': 3, # U+82B8 ...
    '莅': 3, # U+8385 ...
    '葱': 3, # U+8471 ...
    '并': 3, # U+5E76 ...
    '荆': 3, # U+8346 ...
    '萝': 3, # U+841D ...
    '蔂': 3, # U+8502 ...
    '岁': 3, # U+5C81 ...
    '粜': 3, # U+7C9C ...
    '姗': 3, # U+59D7 ...
    '断': 3, # U+65AD ...
    '娇': 3, # U+5A07 ...
    '姹': 3, # U+59F9 ...
    '奸': 3, # U+5978 ...
    '娱': 3, # U+5A31 ...
    '困': 3, # U+56F0 ...
    '里': 3, # U+91CC ...
    '图': 3, # U+56FE ...
    '罢': 3, # U+7F62 ...
    '罗': 3, # U+7F57 ...
    '园': 3, # U+56ED ...
    '累': 3, # U+7D2F ...
    '兑': 3, # U+5151 ...
    '栀': 3, # U+6800 ...
    '构': 3, # U+6784 ...
    '双': 3, # U+53CC ...
    '洒': 3, # U+6D12 ...
    '滚': 3, # U+6EDA ...
    '娄': 3, # U+5A04 ...
    '壳': 3, # U+58F3 ...
    '术': 3, # U+672F ...
    '庐': 3, # U+5E90 ...
    '义': 3, # U+4E49 ...
    '郁': 3, # U+90C1 ...
    '刹': 3, # U+5239 ...
    '疴': 3, # U+75B4 ...
    '压': 3, # U+538B ...
    '历': 3, # U+5386 ...
    '亏': 3, # U+4E8F ...
    '随': 3, # U+968F ...
    '内': 3, # U+5185 ...
    '仪': 3, # U+4EEA ...
    '气': 3, # U+6C14 ...
    '掷': 3, # U+63B7 ...
    '别': 3, # U+522B ...
    '荣': 3, # U+8363 ...
    '郑': 3, # U+90D1 ...
    '并': 3, # U+5E76 ...
    '萝': 3, # U+841D ...
    '困': 3, # U+56F0 ...
    '堕': 3, # U+5815 ...
    '头': 3, # U+5934 ...
    '欤': 3, # U+6B24 ...
    '逊': 3, # U+900A ...
    '点': 3, # U+70B9 ...
    '韵': 3, # U+97F5 ...
    '銮': 3, # U+92AE ...
    '栾': 3, # U+683E ...
    '衮': 3, # U+886E ...
    '蛮': 3, # U+86EE ...
    '弯': 3, # U+5F2F ...
    '孪': 3, # U+5B6A ...
    '递': 3, # U+9012 ...
    '脔': 3, # U+8114 ...
    '恋': 3, # U+604B ...
    '挛': 3, # U+631B ...
    '峦': 3, # U+5CE6 ...
    '娈': 3, # U+5A08 ...
    '过': 3, # U+8FC7 ...
    '广': 3, # U+5E7F ...
    '选': 3, # U+9009 ...
    '彦': 3, # U+5F66 ...
    '迁': 3, # U+8FC1 ...
    '适': 3, # U+9002 ...
    '弃': 3, # U+5F03 ...
    '斗': 3, # U+6597 ...
    '头': 3, # U+5934 ...
    '刘': 3, # U+5218 ...
    '斋': 3, # U+658B ...
    '边': 3, # U+8FB9 ...
    '还': 3, # U+8FD8 ...
    '远': 3, # U+8FDC ...
    '欤': 3, # U+6B24 ...
    '逊': 3, # U+900A ...
    '迩': 3, # U+8FE9 ...
    '点': 3, # U+70B9 ...
    '战': 3, # U+6218 ...
    '逻': 3, # U+903B ...
    '禀': 3, # U+7980 ...
    '这': 3, # U+8FD9 ...
    '迹': 3, # U+8FF9 Last of https://github.com/mike-fabian/ibus-table/issues/100
    }

def test_detection(generated_script) -> int:
    '''
    Test whether the generated script does the detection correctly.

    Returns the number of errors found.
    '''
    logging.info('Testing detection ...')
    error_count = 0
    for phrase in TEST_DATA:
        if (generated_script.detect_chinese_category(phrase)
                != TEST_DATA[phrase]):
            print('phrase', phrase, repr(phrase),
                  'detected as',
                  generated_script.detect_chinese_category(phrase),
                  'should have been', TEST_DATA[phrase],
                  'FAIL.')
            error_count += 1
        else:
            logging.info('phrase=%s %s detected as %d PASS.',
                         phrase,
                         repr(phrase),
                         TEST_DATA[phrase])
    return error_count

def compare_old_new_detection(phrase, generated_script) -> None:
    '''
    Only for debugging.

    Compares results of the Chinese category detection using the
    old and the new function.
    '''
    if (detect_chinese_category_old(phrase)
            != generated_script.detect_chinese_category(phrase)):
        logging.debug(
            '%s %s old=%d new=%d',
            phrase.encode('utf-8'),
            repr(phrase),
            detect_chinese_category_old(phrase),
            generated_script.detect_chinese_category(phrase))
        if phrase in VARIANTS_TABLE_ORIG_UNIHAN_VARIANTS_ENTRY_USED:
            logging.debug(
                VARIANTS_TABLE_ORIG_UNIHAN_VARIANTS_ENTRY_USED[phrase])

def parse_args() -> Any:
    '''Parse the command line arguments'''
    import argparse
    parser = argparse.ArgumentParser(
        description=(
            'Generate a script containing a table and a function '
            + 'to check whether a string of Chinese characters '
            + 'is simplified or traditional'))
    parser.add_argument('-i', '--inputfilename',
                        nargs='?',
                        type=str,
                        default='./Unihan_Variants.txt',
                        help='input file, default is ./Unihan_Variants.txt')
    parser.add_argument('-o', '--outputfilename',
                        nargs='?',
                        type=str,
                        default='./chinese_variants.py',
                        help='output file, default is ./chinese_variants.py')
    parser.add_argument('-d', '--debug',
                        action='store_true',
                        help='print debugging output')
    return parser.parse_args()

def main() -> None:
    '''Main program'''
    args = parse_args()
    log_level = logging.INFO
    if args.debug:
        log_level = logging.DEBUG
    logging.basicConfig(format="%(levelname)s: %(message)s", level=log_level)
    with open(args.inputfilename) as inputfile:
        logging.info("input file=%s", inputfile)
        read_unihan_variants(inputfile)
    with open(args.outputfilename, 'w') as outputfile:
        logging.info("output file=%s", outputfile)
        write_variants_script(outputfile)

    import imp
    generated_script = imp.load_source('dummy', args.outputfilename)

    logging.info('Testing detection ...')
    error_count = test_detection(generated_script)
    if error_count:
        logging.info('FAIL: %s tests failed, exiting ...', error_count)
        exit(1)
    else:
        logging.info('PASS: All tests passed.')

    for phrase in generated_script.VARIANTS_TABLE: # type: ignore
        compare_old_new_detection(phrase, generated_script)

if __name__ == '__main__':
    main()
