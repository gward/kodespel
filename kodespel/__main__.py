#!/usr/bin/python3

import sys
from optparse import OptionParser
from kodespel.kodespel import \
    CodeChecker, DictionaryCollection, error, determine_languages


def main():
    parser = OptionParser(usage="%prog [options] filename ...")

    parser.add_option("-u", "--unique", action='store_true',
                      help="report each misspelling only once")
    parser.add_option("-d", "--dictionary",
                      action='append', dest='dictionaries', default=[],
                      metavar="DICT",
                      help="use custom dictionary DICT (can be a filename "
                           "or a dictionary name); use multiple times to "
                           "include multiple dictionaries")
    parser.add_option("-l", "--language",
                      action='append', dest='languages',
                      metavar="LANG",
                      help="specify a programming language (can be used "
                           "multiple times)")
    parser.add_option("--list-dicts", action='store_true',
                      help="list available dictionaries and exit")
    parser.add_option("--dump-dict", action='store_true',
                      help="build custom dictionary (respecting -d options)")
    parser.add_option("-x", "--exclude", action='append', default=[],
                      metavar="STR",
                      help="exclude STR from spell-checking -- strip it from "
                           "input text before splitting into words")
    parser.add_option("-C", "--compound", action='store_true',
                      help="allow compound words (eg. getall) [default]")
    parser.add_option("--no-compound",
                      action='store_false', dest='compound',
                      help="don't allow compound words")
    parser.add_option("-W", "--wordlen", type='int', default=2,
                      metavar="N",
                      help="ignore words with <= N characters")
    parser.set_defaults(compound=True)
    (options, args) = parser.parse_args()
    if options.list_dicts or options.dump_dict:
        if args:
            parser.error("no additional arguments allowed with "
                         "--list-dicts or --dump-dict")

    if options.list_dicts:
        dicts = DictionaryCollection()
        print("\n".join(dicts.get_standard_dictionaries()))
        sys.exit()

    elif options.dump_dict:
        dicts = DictionaryCollection()
        for dict in options.dictionaries:
            dicts.add_dictionary(dict)
        if options.languages:
            dicts.set_languages(options.languages)
        file = open(dicts.get_filename(), "rt")
        for line in file:
            line = line.strip()
            if line:
                print(line)
        sys.exit()

    if not args:
        parser.error("not enough arguments")

    dicts = DictionaryCollection()
    for dictionary in options.dictionaries:
        dicts.add_dictionary(dictionary)

    filenames = args

    languages = options.languages
    if languages is None:
        languages = determine_languages(filenames)
        print("languages: %s" % languages)
    dicts.set_languages(languages)

    any_errors = False
    for filename in filenames:
        try:
            checker = CodeChecker(filename, dictionaries=dicts)
        except IOError as err:
            error("%s: %s" % (filename, err.strerror))
            any_errors = True
        else:
            checker.set_unique(options.unique)
            ispell = checker.get_spell_checker()
            ispell.set_allow_compound(options.compound)
            ispell.set_word_len(options.wordlen)
            for s in options.exclude:
                checker.exclude_string(s)
            if checker.check_file():
                any_errors = True

    dicts.close()
    sys.exit(any_errors and 1 or 0)


if __name__ == '__main__':
    main()
