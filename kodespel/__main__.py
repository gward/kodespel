#!/usr/bin/python3

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
    parser.add_option('-x', '--exclude', action='append', default=[],
                      metavar='STR',
                      help='exclude STR from spell-checking -- strip it from '
                           'input text before splitting into words')
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

        any_errors = kodespel.check_inputs(
            options,
            dictionaries,
            args,
            cache,
            base_wordlist)
    finally:
        cache.close()
    sys.exit(any_errors and 1 or 0)


if __name__ == '__main__':
    main()
