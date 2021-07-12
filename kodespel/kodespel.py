'''
Module for spell-checking programming language source code.  The trick
is that it knows how to split identifiers up into words: e.g. if the
token getRemaningObjects occurs in source code, it is split into "get",
"Remaning", "Objects", and those words are piped to ispell, which easily
detects the spelling error.  Handles various common ways of munging
words together: identifiers like DoSomethng, get_remaning_objects,
SOME_CONSTENT, and HTTPRepsonse are all handled correctly.

Requires Python 3.6 or greater.
'''

import collections
import glob
import os
import re
import subprocess
import sys
import tempfile
from typing import Union, Optional, Iterable, Callable, Dict, List, Tuple, IO

assert sys.hexversion >= 0x03060000, 'requires Python 3.6 or greater'


def warn(msg):
    sys.stderr.write('warning: %s: %s\n' % (__name__, msg))


def error(msg):
    sys.stderr.write('error: %s: %s\n' % (__name__, msg))


def _stdrepr(self):
    return '<%s at %x: %s>' % (type(self).__name__, id(self), self)


EXTENSION_LANG = {
    '.go': 'go',
    '.py': 'python',
    '.pl': 'perl',
    '.pm': 'perl',
    '.c': 'c',
    '.h': 'c',
    '.cpp': 'c',
    '.hpp': 'c',
    '.java': 'java',
}


def determine_language(filename: str) -> Optional[str]:
    '''Analyze a file and return the programming language used. Goes by
    filename first, and then handles scripts (ie. if executable, open and
    read first line looking for name of interpreter).

    :return: one of the values of EXTENSION_LANG, or None if unknown language
    '''
    ext = os.path.splitext(filename)[1]
    lang = EXTENSION_LANG.get(ext)
    if lang:
        return lang

    try:
        stat = os.stat(filename)
    except OSError:
        return None

    if stat.st_mode & 0o111:
        file = open(filename, 'rt')
        first_line = file.readline()
        file.close()

        if not first_line.startswith('#!'):
            lang = None
        elif 'python' in first_line:
            lang = 'python'
        elif 'perl' in first_line:
            lang = 'perl'

    return lang


class SpellChecker:
    '''
    A wrapper for ispell.  Opens two pipes to ispell: one for writing
    (sending) words to ispell, and the other for reading reports
    of misspelled words back from it.
    '''

    ispell_in: IO[str]
    ispell_out: IO[str]

    def __init__(self):
        self.allow_compound = None
        self.word_len = None
        self.dictionary = None

    def set_dictionary(self, dictionary):
        self.dictionary = dictionary

    def set_allow_compound(self, allow_compound):
        self.allow_compound = allow_compound

    def set_word_len(self, word_len):
        self.word_len = word_len

    def open(self):
        cmd = ['ispell', '-a']
        if self.allow_compound:
            cmd.append('-C')
        if self.word_len is not None:
            cmd.append('-W%d' % self.word_len)
        if self.dictionary:
            cmd.extend(['-p', self.dictionary])

        try:
            pipe = subprocess.Popen(cmd,
                                    stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE,
                                    close_fds=True,
                                    encoding='utf-8')
        except OSError as err:
            raise OSError('error executing %s: %s' % (cmd[0], err.strerror))

        assert pipe.stdin is not None
        assert pipe.stdout is not None
        self.ispell_in = pipe.stdin
        self.ispell_out = pipe.stdout

        firstline = self.ispell_out.readline()
        assert firstline.startswith('@(#)'), \
            'expected "@(#)" line from ispell (got %r)' % firstline

        # Put ispell in terse mode (no output for correctly-spelled
        # words).
        self.ispell_in.write('!\n')

        # Total number of unique spelling errors seen.
        self.total_errors = 0

    def close(self):
        in_status = self.ispell_in.close()
        out_status = self.ispell_out.close()
        if in_status != out_status:
            warn('huh? ispell_in status was %r, but ispell_out status was %r'
                 % (in_status, out_status))
        elif in_status is not None:
            warn('ispell failed with exit status %r' % in_status)

    def send(self, word):
        '''Send a word to ispell to be checked.'''
        self.ispell_in.write('^' + word + '\n')

    def done_sending(self):
        self.ispell_in.close()

    def check(self):
        '''
        Read any output available from ispell, ie. reports of misspelled
        words sent since initialization.  Return a list of tuples
        (bad_word, guesses) where 'guesses' is a list (possibly empty)
        of suggested replacements for 'guesses'.
        '''
        report = []                     # list of (bad_word, suggestions)
        while True:
            line = self.ispell_out.readline()
            if not line:
                break

            code = line[0]
            extra = line[1:-1]

            if code in '&?':
                # ispell has near-misses or guesses, formatted like this:
                #   "& orig count offset: miss, miss, ..., guess, ..."
                #   "? orig 0 offset: guess, ..."
                # I don't care about the distinction between near-misses
                # and guesses.
                count: Union[str, int]
                (orig, count, offset, extra) = extra.split(None, 3)
                count = int(count)
                guesses = extra.split(', ')
                report.append((orig, guesses))
            elif code == '#':
                # ispell has no clue
                orig = extra.split()[0]
                report.append((orig, []))

        self.total_errors += len(report)
        return report


class BuiltinDictionaries:
    '''The collection of all of kodespel's builtin dictionaries.'''
    def __init__(self):
        script_dir = os.path.dirname(sys.argv[0])
        self.dict_path = [
            os.path.join(sys.prefix, 'share/kodespel'),
            os.path.join(script_dir, '../dict'),
            os.path.join(os.path.dirname(__file__), '../dict'),
        ]

    def get_filenames(self) -> List[str]:
        '''return the list of all builtin dicts (as bare names)'''
        filenames = []
        for dir in self.dict_path:
            filenames.extend(glob.glob(os.path.join(
                os.path.abspath(dir), '*.dict')))
        return filenames

    def get_names(self) -> Iterable[str]:
        for fn in self.get_filenames():
            yield os.path.basename(os.path.splitext(fn)[0])

    def find(self, name: str) -> Optional[str]:
        for dir in self.dict_path:
            fn = os.path.join(dir, name + '.dict')
            if os.path.isfile(fn):
                return fn
        return None


class Wordlist:
    '''A list of words that can be used to spellcheck any number of files.'''

    names: List[str]            # dictionary names or filenames
    filename: Optional[str]
    is_temp: bool

    def __init__(self, builtins: BuiltinDictionaries, names: List[str]):
        self.builtins = builtins
        self.names = names

        self.filename = None
        self.is_temp = False

    def __str__(self):
        return ','.join(self.names)

    __repr__ = _stdrepr

    def close(self):
        if self.is_temp and self.filename is not None:
            print(f'unlink {self.filename}')
            os.unlink(self.filename)

    def get_filename(self) -> str:
        if self.filename is not None:
            return self.filename
        if len(self.names) == 1:
            self.filename = self._resolve(self.names[0])
            if self.filename is None:
                raise RuntimeError(
                    f'could not resolve dictionary: {self.names[0]}')
            self.is_temp = False
            return self.filename

        tfile = tempfile.NamedTemporaryFile(
            mode='wt', prefix='kodespel-', suffix='.dict', delete=False)
        self.filename = tfile.name
        self.is_temp = True

        # write content to the temp file
        for name in self.names:
            input = self._resolve(name)
            if input is None:
                continue
            with open(input) as infile:
                tfile.write(infile.read())
            tfile.write('\n')
        tfile.close()

        return self.filename

    def _resolve(self, name) -> Optional[str]:
        # if name is already a file, nothing to do
        if os.path.isfile(name):
            return name

        # ok, see if it it's a builtin dict like "base" (i.e. does it exist
        # in the dictionary search path)
        fn = self.builtins.find(name)
        if fn is not None:
            return fn

        # no luck
        warn(f'dictionary not found: {name}')
        return None


class WordlistCache:
    builtins: BuiltinDictionaries
    cache: Dict[str, Wordlist]

    def __init__(self, builtins: BuiltinDictionaries):
        self.builtins = builtins
        self.cache = {}

    def close(self):
        for wl in self.cache.values():
            wl.close()

    def get_wordlist(self, names: List[str]) -> Wordlist:
        key = '\0'.join(names)
        try:
            wordlist = self.cache[key]
        except KeyError:
            self.cache[key] = wordlist = Wordlist(self.builtins, names)
        return wordlist


class CodeChecker:
    '''
    Object that reads a source code file, splits it into tokens,
    splits the tokens into words, and spell-checks each word.
    '''

    ispell: SpellChecker
    unique: bool
    ignore: Callable[[str], bool]

    def __init__(self):
        self.ispell = SpellChecker()
        self.ignore = lambda word: False     # type: ignore
        self.unique = False

    def get_spell_checker(self):
        '''
        Return the SpellChecker instance (wrapper around ispell)
        that this CodeChecker will use.
        '''
        return self.ispell

    def set_unique(self, unique):
        self.unique = unique

    def set_ignore(self, ignore: List[str]):
        if ignore:
            ignore_re = re.compile(r'|'.join(ignore), re.IGNORECASE)
            self.ignore = ignore_re.search   # type: ignore

    # A word can match one of 3 patterns.
    _word_re = re.compile(
        # Case 1: a string of mixed-case letters interspersed with
        # single apostrophes: aren't, O'Reilly, rock'n'roll. This is
        # for regular English text in comments and strings. It's not
        # the common case, but has to come first because of regex
        # matching rules.
        r'[A-Za-z]+(?:\'[A-Za-z]+)+|'

        # Case 2: a string of letters, optionally capitalized; this
        # covers almost everything: getNext, get_next, GetNext,
        # HTTP_NOT_FOUND, HttpResponse, etc.
        r'[A-Z]?[a-z]+|'

        # Case 3: a string of uppercase letters not immediately
        # followed by a lowercase letter. Needed for uppercase
        # acronyms in mixed-case identifiers, eg. "HTTPResponse",
        # "getHTTPResponse".
        r'[A-Z]+(?![a-z])'
    )

    def split_line(self, line):
        '''
        Given a line (or larger chunk) of source code, splits it
        into words.  Eg. the string
          'match = pat.search(current_line, 0, pos)'
        is split into
          ['match', 'pat', 'search', 'current', 'line', 'pos']
        '''
        return self._word_re.findall(line)

    def _extract_words(self, file: IO[str]) -> Dict[str, List[int]]:
        '''find all distinct words in file

        :return: dict mapping word to list of 1-based line numbers
        '''
        locations = collections.defaultdict(list)
        for (idx, line) in enumerate(file):
            line_num = idx + 1
            for word in self.split_line(line):
                if not self.ignore(word):    # type: ignore
                    locations[word].append(line_num)
        return dict(locations)

    def _send_words(self, wordlist: Wordlist, words: Iterable[str]):
        self.ispell.set_dictionary(wordlist.get_filename())
        self.ispell.open()
        for word in words:
            self.ispell.send(word)
        self.ispell.done_sending()

    def _check(
            self, locations: Dict[str, List[int]]) \
            -> List[Tuple[int, str, List[str]]]:
        '''analyze output of ispell'''
        errors = []
        for (bad_word, guesses) in self.ispell.check():
            # ispell accepts "JSON" but not "json": swallow errors that
            # are only wrong because of case mismatch.
            guesses_lower = [guess.lower() for guess in guesses]
            if bad_word.lower() in guesses_lower:
                continue

            line_nums = locations[bad_word]
            if self.unique:
                del line_nums[1:]
            for line_num in line_nums:
                errors.append((line_num, bad_word, guesses))

        errors.sort()                   # sort on line number
        return errors

    def _report(self, filename, messages, outfile):
        for (line_num, bad_word, guesses) in messages:
            guesses = ', '.join(guesses)
            print('%s:%d: %s: %s?'
                  % (filename, line_num, bad_word, guesses),
                  file=outfile)

    def check_file(self, filename: str, wordlist: Wordlist) -> bool:
        '''
        Spell-check the current file, reporting errors to stdout.
        Return true if there were any spelling errors.
        '''
        with open(filename, 'rt') as infile:
            locations = self._extract_words(infile)
            self._send_words(wordlist, locations)
        errors = self._check(locations)
        self._report(filename, errors, sys.stdout)
        return bool(errors)


def check_inputs(
        options,
        dictionaries: List[str],
        inputs: List[str],
        cache: WordlistCache,
        base_wordlist: Wordlist) -> bool:

    checker = CodeChecker()
    checker.set_unique(options.unique)
    checker.set_ignore(options.ignore)
    ispell = checker.get_spell_checker()
    ispell.set_allow_compound(options.compound)
    ispell.set_word_len(options.wordlen)

    any_errors = False
    for filename in find_files(inputs):
        lang = determine_language(filename)
        if lang is not None:
            wordlist = cache.get_wordlist(dictionaries + [lang])
        else:
            wordlist = base_wordlist

        print(f'checking {filename} with {wordlist!r}')
        try:
            if checker.check_file(filename, wordlist):
                any_errors = True
        except IOError as err:
            error('%s: %s' % (filename, err.strerror))
            any_errors = True

    return any_errors


def find_files(inputs: List[str]) -> Iterable[str]:
    for input in inputs:
        if os.path.isdir(input):
            for (dirpath, dirnames, filenames) in os.walk(input):
                for fn in filenames:
                    ext = os.path.splitext(fn)[1]
                    if ext in EXTENSION_LANG:
                        yield os.path.join(dirpath, fn)
        else:
            yield input
