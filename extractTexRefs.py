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
import csv


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


def restrictTypes(objs: Sequence[dict[str, Any]], types: Sequence[str]) -> list[dict[str, Any]]:
    typeSet = {t.lower() for t in types}
    return [obj for obj in objs if obj['type'].lower() in typeSet]


def parseTypes(s: str) -> list[str]:
    types = [t.strip() for t in s.split(',') if t.strip()]
    if not types:
        raise argparse.ArgumentTypeError('no types specified')
    return types


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


def myCsvOutput(objs: Sequence[dict[str, Any]], fp: TextIO, keys: Optional[Sequence[str]] = None):
    if keys is None:
        # use all known keys that occur in at least one object
        present = {k for obj in objs for k in obj}
        keys = [k for k in ALL_KEYS if k in present]
    writer = csv.DictWriter(fp, fieldnames=keys, extrasaction='ignore', lineterminator='\n')
    writer.writeheader()
    writer.writerows(objs)


def writeOutput(objs: Sequence[Any], format: str, fp: TextIO, keys: Optional[Sequence[str]] = None):
    if format == 'json':
        myJsonOutput(objs, fp)
    elif format == 'csv':
        myCsvOutput(objs, fp, keys)
    else:
        myTexOutput(objs, fp)


def inferFormat(args: Any):
    if args.format is None:
        if args.output is None:
            args.format = 'json'
        else:
            _, ext = splitext(args.output)
            args.format = {'.tex': 'tex', '.csv': 'csv'}.get(ext.lower(), 'json')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fpath', help='path to LaTeX aux file')
    parser.add_argument('-o', '--output', help='path to output JSON/TeX/CSV file')
    parser.add_argument('-f', '--format', choices=('json', 'tex', 'csv'),
        help='output format (default: inferred from the extension of --output, else json)')
    parser.add_argument('--include-bib', action='store_true', default=False,
        help='also include bibliography')
    parser.add_argument('-k', '--keys', type=parseKeys,
        help='comma-separated list of keys to keep in each JSON object (or columns in CSV)'
        ' (e.g., type,texLabel,outputId); other keys are dropped.'
        ' Valid keys: ' + ', '.join(ALL_KEYS))
    parser.add_argument('-t', '--types', type=parseTypes,
        help='comma-separated list of types (case-insensitive) of objects to keep'
        ' (e.g., theorem,lemma,definition); objects of other types are dropped')
    args = parser.parse_args()
    with open(args.fpath) as fp:
        output = extractInfo(fp, args.include_bib)
    inferFormat(args)
    if args.types is not None:
        output = restrictTypes(output, args.types)
    if args.keys is not None:
        if args.format == 'tex':
            parser.error('--keys is not supported for TeX output')
        output = restrictKeys(output, args.keys)
    if args.output is None:
        writeOutput(output, args.format, sys.stdout, args.keys)
    else:
        with open(args.output, 'w', newline='') as fp:
            writeOutput(output, args.format, fp, args.keys)


if __name__ == '__main__':
    main()
    """
    for line in sys.stdin:
        line = line.strip()
        output, end2 = parseRecursiveBrackets(line, 0, len(line))
        print(output)
    """
