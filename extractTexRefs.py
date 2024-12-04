#!/usr/bin/env python3

"""
Reads a LaTeX aux file and outputs a list of references to all
bibliographic entries, theorems, definitions, sections, etc.
"""

from collections.abc import Sequence
from typing import Optional, TextIO
import sys
import argparse
import json


def findEndBracket(s: str, beg: int, end: int) -> int:
    """find the length of the longest prefix containing matching brackets"""
    depth = 0
    while beg != end:
        openI = s.find('{', beg, end)
        closeI = s.find('}', beg, end)
        if openI == -1:
            openI = end
        if closeI == -1:
            closeI = end
        if openI < closeI:
            depth += 1
            beg = openI + 1
        elif closeI < end:
            if depth == 0:
                return closeI
            else:
                depth -= 1
                beg = closeI + 1
        else:
            beg = end
    return beg


def parseRecursiveBrackets(s: str, beg: int, end: Optional[int] = None) -> tuple[object, int]:
    """
    Parses the grammar A -> S | ('{' + A + '}')+, where S is a string that doesn't start with '{' or '}'
    and contains matching nested '{' and '}'.
    """
    if end is None:
        end = len(s)
    if beg == end or s[beg] != '{':
        closeI = findEndBracket(s, beg, end)
        end2 = closeI if closeI >= 0 else end
        return (s[beg:end2], end2)
    else:
        a = []
        while beg != end and s[beg] != '}':
            assert s[beg] == '{'
            sPart, endPart = parseRecursiveBrackets(s, beg+1, end)
            if endPart == end:
                raise ValueError("missing '}'")
            a.append(sPart)
            beg = endPart + 1
        return (a, beg)


def deflesh(a: object) -> object:
    if isinstance(a, str):
        return None
    elif isinstance(a, Sequence):
        return [deflesh(x) for x in a]


# For \newlabel{defn:monoid@cref}{{[definition][1][]1}{[1][1][]1}},
# output should be ['defn:monoid@cref', ['[definition][1][]1', '[1][1][]1']]
def extractInfo(fp: TextIO, include_bib: bool):
    output = []
    for line in fp:
        line = line.strip()
        if line.startswith('\\bibcite'):
            if include_bib:
                info, _ = parseRecursiveBrackets(line, len('\\bibcite'))
                assert len(info) == 2
                output.append({'type': 'cite', 'texLabel': info[0], 'anchor': 'cite.' + info[0]})
        elif line.startswith('\\newlabel'):
            info, _ = parseRecursiveBrackets(line, len('\\newlabel'))
            # print(info, file=sys.stderr)
            assert(len(info) == 2)
            if info[0].endswith('@cref'):
                assert len(output) > 0
                prevD = output[-1]
                assert info[0][:-5] == prevD['texLabel']
                assert info[1][0][0] == '['
                closeI = info[1][0].find(']')
                assert closeI != -1
                type = info[1][0][1:closeI]
                prevD['type'] = type
            else:
                assert deflesh(info) == [None, [None] * 5]
                anchor = info[1][3]
                if '.' in anchor:
                    type = anchor.split('.')[0]
                d = {'type': type, 'texLabel': info[0], 'outputId': info[1][0], 'anchor': anchor, 'page': info[1][1]}
                if info[1][2]:
                    d['context'] = info[1][2]
                if info[1][4]:
                    d['misc'] = info[1][4]
                output.append(d)
    return output


def myJsonOutput(x: object, fp: TextIO):
    if isinstance(x, list) or isinstance(x, tuple):
        n = len(x)
        fp.write('[\n')
        for i, y in enumerate(x):
            json.dump(y, fp)
            if i != n-1:
                fp.write(',\n')
            else:
                fp.write('\n')
        fp.write(']\n')
    else:
        json.dump(x, fp)
        fp.write('\n')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fpath', help='path to LaTeX aux file')
    parser.add_argument('-o', '--output', help='path to output JSON file')
    parser.add_argument('--include-bib', action='store_true', default=False,
        help='also include bibliography')
    args = parser.parse_args()
    with open(args.fpath) as fp:
        output = extractInfo(fp, args.include_bib)
    if args.output:
        with open(args.output, 'w') as fp:
            myJsonOutput(output, fp)
    else:
        myJsonOutput(output, sys.stdout)


if __name__ == '__main__':
    main()
    """
    for line in sys.stdin:
        line = line.strip()
        output, end2 = parseRecursiveBrackets(line, 0, len(line))
        print(output)
    """
