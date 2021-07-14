#!/usr/bin/python3

import re
import sys
from optparse import OptionParser
from . import kodespel


def main():
    parser = OptionParser(usage='%prog [options] file_or_dir ...')

    parser.add_option('-a', '--all', action='store_false', dest='unique',
                      help='report every single misspelling [default: --unique]')
    parser.add_option('-u', '--unique', action='store_true',
                      help='report each misspelling only once [default]')
    parser.add_option('-d', '--dictionary',
                      action='append', dest='dictionaries', default=[],
                      metavar='DICT',
                      help='use custom dictionary DICT (can be a filename '
                           'or a dictionary name); use multiple times to '
                           'include multiple dictionaries')
    parser.add_option('--list-dicts', action='store_true',
                      help='list available dictionaries and exit')
    parser.add_option('--dump-dict', action='store_true',
                      help='build custom dictionary (respecting -d options)')
    parser.add_option('--make-dict', action='store',
                      metavar='DICTFILE',
                      help='write unknown words to DICTFILE')
    parser.add_option('-I', '--ignore', action='append', default=[],
                      metavar='REGEX',
                      help='ignore any words matching REGEX')
    parser.add_option('-C', '--compound', action='store_true',
                      help='allow compound words (eg. getall) [default]')
    parser.add_option('--no-compound',
                      action='store_false', dest='compound',
                      help='do not allow compound words')
    parser.add_option('-W', '--wordlen', type='int', default=3,
                      metavar='N',
                      help='ignore words with <= N characters')
    parser.set_defaults(compound=True, unique=True)
    (options, args) = parser.parse_args()
    if options.list_dicts or options.dump_dict:
        if args:
            parser.error('no additional arguments allowed with '
                         '--list-dicts or --dump-dict')

    builtins = kodespel.BuiltinDictionaries()
    if options.list_dicts:
        print('\n'.join(builtins.get_names()))
        sys.exit()

    if options.ignore:
        for pat in options.ignore:
            try:
                re.compile(pat)
            except re.error as err:
                parser.error(f'invalid ignore pattern {pat!r}: {err}')

    report = report_errors
    outfile = sys.stderr
    if options.make_dict:
        report = make_dict
        outfile = open(options.make_dict, 'wt')

    dictionaries = ['base'] + options.dictionaries
    cache = kodespel.WordlistCache(builtins)
    try:
        base_wordlist = cache.get_wordlist(dictionaries)

        if options.dump_dict:
            file = open(base_wordlist.get_filename(), 'rt')
            for line in file:
                line = line.strip()
                if line:
                    print(line)
            sys.exit()

        if not args:
            parser.error('not enough arguments')

        any_errors = False
        reports = kodespel.check_inputs(
            options,
            dictionaries,
            args,
            cache,
            base_wordlist)
        try:
            any_errors = report(reports, outfile)
        except kodespel.BadInputs:
            # no need to print anything -- that's already been done in check_inputs()
            any_errors = True
    finally:
        cache.close()
    sys.exit(any_errors and 1 or 0)


def report_errors(reports, outfile) -> bool:
    any_errors = False
    for report in reports:
        report.report_errors(outfile)
        any_errors = True
    return any_errors


def make_dict(reports, outfile) -> bool:
    words = set()
    for report in reports:
        for error in report.errors:
            words.add(error.word.lower())

    print('\n'.join(sorted(words)), file=outfile)
    return False


if __name__ == '__main__':
    main()
