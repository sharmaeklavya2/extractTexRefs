#!/usr/bin/env python3

"""
Reads a LaTeX aux file and outputs a list of references to all
bibliographic entries, theorems, definitions, sections, etc.
"""

from collections.abc import Sequence
from typing import Any, Optional, TextIO
import sys
from os.path import splitext
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


def parseRecursiveBrackets(s: str, beg: int, end: Optional[int] = None) -> tuple[Any, int]:
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
    else:
        return None


# For \newlabel{defn:monoid@cref}{{[definition][1][]1}{[1][1][]1}},
# output should be ['defn:monoid@cref', ['[definition][1][]1', '[1][1][]1']]
def extractInfo(fp: TextIO, include_bib: bool):
    output = []
    for line in fp:
        line = line.strip()
        try:
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
                    if info[1] and info[1][0]:
                        assert info[1][0][0] == '['
                        closeI = info[1][0].find(']')
                        assert closeI != -1
                        type = info[1][0][1:closeI]
                        prevD['type'] = type
                else:
                    assert deflesh(info) == [None, [None] * 5]
                    anchor = info[1][3]
                    assert '.' in anchor
                    type = anchor.split('.')[0]
                    d = {'type': type, 'texLabel': info[0], 'outputId': info[1][0], 'anchor': anchor, 'page': info[1][1]}
                    if info[1][2]:
                        d['context'] = info[1][2]
                    if info[1][4]:
                        d['misc'] = info[1][4]
                    output.append(d)
        except Exception as e:
            print('An error occurred while parsing this line:', file=sys.stderr)
            print(line, file=sys.stderr)
            raise e
    return output


ALL_KEYS = ('type', 'texLabel', 'outputId', 'anchor', 'page', 'context', 'misc')


def restrictKeys(objs: Sequence[dict[str, Any]], keys: Sequence[str]) -> list[dict[str, Any]]:
    return [{k: obj[k] for k in keys if k in obj} for obj in objs]


def parseKeys(s: str) -> list[str]:
    keys = [k.strip() for k in s.split(',') if k.strip()]
    unknown = [k for k in keys if k not in ALL_KEYS]
    if unknown:
        raise argparse.ArgumentTypeError('unknown key(s): {}. Valid keys: {}'.format(
            ', '.join(unknown), ', '.join(ALL_KEYS)))
    if not keys:
        raise argparse.ArgumentTypeError('no keys specified')
    return keys


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


def changeRefType(x: str) -> str:
    x = x.lower()
    i = 0
    while x.startswith('sub', i):
        i += 3
    x = x[i:]
    return x.capitalize()


def myTexOutput(objs: Sequence[Any], fp: TextIO):
    for obj in objs:
        if obj['type'] != 'cite':
            line = '\\refinedLabel{%s}{%s}{%s}\n' % (obj['texLabel'], changeRefType(obj['type']), obj['outputId'])
            fp.write(line)


def writeOutput(objs: Sequence[Any], format: str, fp: TextIO):
    if format == 'json':
        myJsonOutput(objs, fp)
    else:
        myTexOutput(objs, fp)


def inferFormat(args: Any):
    if args.format is None:
        if args.output is None:
            args.format = 'json'
        else:
            _, ext = splitext(args.output)
            args.format = 'tex' if ext == '.tex' else 'json'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fpath', help='path to LaTeX aux file')
    parser.add_argument('-o', '--output', help='path to output JSON/TeX file')
    parser.add_argument('-f', '--format', choices=('json', 'tex'))
    parser.add_argument('--include-bib', action='store_true', default=False,
        help='also include bibliography')
    parser.add_argument('-k', '--keys', type=parseKeys,
        help='comma-separated list of keys to keep in each JSON object'
        ' (e.g., type,texLabel,outputId); other keys are dropped.'
        ' Valid keys: ' + ', '.join(ALL_KEYS))
    args = parser.parse_args()
    with open(args.fpath) as fp:
        output = extractInfo(fp, args.include_bib)
    inferFormat(args)
    if args.keys is not None:
        if args.format != 'json':
            parser.error('--keys is only supported for JSON output')
        output = restrictKeys(output, args.keys)
    if args.output is None:
        writeOutput(output, args.format, sys.stdout)
    else:
        with open(args.output, 'w') as fp:
            writeOutput(output, args.format, fp)


if __name__ == '__main__':
    main()
    """
    for line in sys.stdin:
        line = line.strip()
        output, end2 = parseRecursiveBrackets(line, 0, len(line))
        print(output)
    """
