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

import sys
import os
import re
import subprocess
from glob import glob
from tempfile import mkstemp

assert sys.hexversion >= 0x03060000, "requires Python 3.6 or greater"


def warn(msg):
    sys.stderr.write("warning: %s: %s\n" % (__name__, msg))


def error(msg):
    sys.stderr.write("error: %s: %s\n" % (__name__, msg))


EXTENSION_LANG = {
    ".go": "go",
    ".py": "python",
    ".pl": "perl",
    ".pm": "perl",
    ".c": "c",
    ".h": "c",
    ".cpp": "c",
    ".hpp": "c",
    ".java": "java",
}


def determine_languages(filenames):
    '''
    Analyze a list of files and return the set of programming
    languages represented.  Goes by filename first, and then handles
    scripts (ie. if executable, open and read first line looking
    for name of interpreter).
    '''
    languages = set()
    for filename in filenames:
        ext = os.path.splitext(filename)[1]
        lang = EXTENSION_LANG.get(ext)
        if not lang and os.stat(filename).st_mode & 0o111:
            file = open(filename, "rt")
            first_line = file.readline()
            file.close()

            if not first_line.startswith("#!"):
                continue
            if "python" in first_line:
                lang = "python"
            elif "perl" in first_line:
                lang = "perl"

        if lang:
            languages.add(lang)
        else:
            warn("unable to determine language of file %r" % filename)

    return languages


class SpellChecker:
    '''
    A wrapper for ispell.  Opens two pipes to ispell: one for writing
    (sending) words to ispell, and the other for reading reports
    of misspelled words back from it.
    '''

    def __init__(self):
        self.allow_compound = None
        self.word_len = None
        self.dictionary = None
        self.ispell_in = None
        self.ispell_out = None

    def set_dictionary(self, dictionary):
        self.dictionary = dictionary

    def set_allow_compound(self, allow_compound):
        self.allow_compound = allow_compound

    def set_word_len(self, word_len):
        self.word_len = word_len

    def open(self):
        cmd = ["ispell", "-a"]
        if self.allow_compound:
            cmd.append("-C")
        if self.word_len is not None:
            cmd.append("-W%d" % self.word_len)
        if self.dictionary:
            cmd.extend(["-p", self.dictionary])

        try:
            pipe = subprocess.Popen(cmd,
                                    stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE,
                                    close_fds=True,
                                    encoding="utf-8")
        except OSError as err:
            raise OSError("error executing %s: %s" % (cmd[0], err.strerror))

        self.ispell_in = pipe.stdin
        self.ispell_out = pipe.stdout

        firstline = self.ispell_out.readline()
        assert firstline.startswith("@(#)"), \
            "expected \"@(#)\" line from ispell (got %r)" % firstline

        # Put ispell in terse mode (no output for correctly-spelled
        # words).
        self.ispell_in.write("!\n")

        # Total number of unique spelling errors seen.
        self.total_errors = 0

    def close(self):
        in_status = self.ispell_in.close()
        out_status = self.ispell_out.close()
        if in_status != out_status:
            warn("huh? ispell_in status was %r, but ispell_out status was %r"
                 % (in_status, out_status))
        elif in_status is not None:
            warn("ispell failed with exit status %r" % in_status)

    def send(self, word):
        '''Send a word to ispell to be checked.'''
        self.ispell_in.write("^" + word + "\n")

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

            if code in "&?":
                # ispell has near-misses or guesses, formatted like this:
                #   "& orig count offset: miss, miss, ..., guess, ..."
                #   "? orig 0 offset: guess, ..."
                # I don't care about the distinction between near-misses
                # and guesses.
                (orig, count, offset, extra) = extra.split(None, 3)
                count = int(count)
                guesses = extra.split(", ")
                report.append((orig, guesses))
            elif code == "#":
                # ispell has no clue
                orig = extra.split()[0]
                report.append((orig, []))

        self.total_errors += len(report)
        return report


class DictionaryCollection:
    '''
    A collection of dictionaries that can be used for spell-checking
    many files (ie. with many instances of CodeChecker).  A dictionary
    may be standard dictionary, shipped and installed with kodespel
    and identified by name (e.g. "unix", "java"); or it may be a custom
    dictionary, identified by filename (e.g. "./dict/myproject.dict").
    '''

    __slots__ = [
        # List of directories to search for dictionary files.
        'dict_path',

        'dict_filename',

        # The set of programming languages to be checked (this is just
        # a specialized form of standard dictionary).
        'languages',

        # List of dictionaries.  Dictionaries are specified either
        # as a filename ("dict/myproject.dict") or a basename ("unix"),
        # which is resolved against the CodeChecker's dict_path.
        'dictionaries',
    ]

    def __init__(self):
        prog = sys.argv[0]
        while os.path.islink(prog):
            prog = os.path.join(os.path.dirname(prog), os.readlink(prog))
        script_dir = os.path.dirname(prog)

        self.dict_path = [os.path.join(sys.prefix, "share/kodespel"),
                          os.path.join(script_dir, "../dict")]
        self.languages = []
        self.dictionaries = []
        self.dict_filename = None       # file with concatenated dictionaries

    def close(self):
        if self.dict_filename and os.path.exists(self.dict_filename):
            os.unlink(self.dict_filename)
            self.dict_filename = None

    def __del__(self):
        self.close()

    def set_languages(self, languages):
        '''
        Specify the set of programming languages which will be checked
        (this is just a specialized form of standard dictionary).
        '''
        self.languages = list(languages)

    def add_dictionary(self, dictionary):
        '''
        Specify a dictionary, which can either be a working filename, or
        a base filename which is searched for in 'dict_path' after
        appending ".dict".
        '''
        self.dictionaries.append(dictionary)

    def get_standard_dictionaries(self):
        filenames = []
        for dir in self.dict_path:
            filenames.extend(glob(os.path.join(dir, "*.dict")))
        return filenames

    def _create_dict(self):
        dicts = ["base"] + self.languages + self.dictionaries
        dict_files = []
        for dict in dicts:
            # If a working filename was supplied, use it.
            if os.path.isfile(dict):
                dict_files.append(dict)

            # Otherwise, append ".dict" and search the dict_path.
            else:
                for dir in self.dict_path:
                    dict_file = os.path.join(dir, dict + ".dict")
                    if os.path.exists(dict_file):
                        dict_files.append(dict_file)
                        break
                else:
                    warn("%s dictionary not found" % dict)

        (out_fd, out_filename) = mkstemp(".dict", "kodespel-")
        out_file = os.fdopen(out_fd, "wt")
        for filename in dict_files:
            in_file = open(filename, "rt")
            out_file.write(in_file.read())
            in_file.close()

        out_file.close()
        self.dict_filename = out_filename

    def get_filename(self):
        if self.dict_filename is None:
            self._create_dict()
            assert (self.dict_filename is not None and
                    os.path.isfile(self.dict_filename)), \
                "bad dict_filename: %r" % self.dict_filename
        return self.dict_filename


class CodeChecker:
    '''
    Object that reads a source code file, splits it into tokens,
    splits the tokens into words, and spell-checks each word.
    '''

    __slots__ = [
        # Name of the file currently being read.
        'filename',

        # The file currently being read.
        'file',

        # Current line number in 'file'.
        'line_num',

        # Map word to list of line numbers where that word occurs, and
        # coincidentally allows us to prevent checking the same word
        # twice.
        'locations',

        # SpellChecker object -- a pair of pipes to send words to ispell
        # and read errors back.
        'ispell',

        # The programming language of the current file (used to determine
        # excluded words).  This can be derived either from the filename
        # or from the first line of a script.
        'language',

        # List of strings that are excluded from spell-checking.
        'exclude',

        # Regex used to strip excluded strings from input.
        'exclude_re',

        # DictionaryCollection instance for finding and concatenating
        # various custom dictionaries.
        'dictionaries',

        # If true, report each misspelling only once (at its first
        # occurrence).
        'unique',
    ]

    def __init__(self, filename=None, file=None, dictionaries=None):
        self.filename = filename
        if file is None and filename is not None:
            self.file = open(filename, "rt")
        else:
            self.file = file

        self.line_num = 0
        self.locations = {}
        self.ispell = SpellChecker()

        self.language = None
        self.exclude = []
        self.exclude_re = None
        self.dictionaries = dictionaries
        self.unique = False

    def get_spell_checker(self):
        '''
        Return the SpellChecker instance (wrapper around ispell)
        that this CodeChecker will use.
        '''
        return self.ispell

    def exclude_string(self, string):
        '''
        Exclude 'string' from spell-checking.
        '''
        self.exclude.append(string)

    def set_unique(self, unique):
        self.unique = unique

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
          "match = pat.search(current_line, 0, pos)"
        is split into
          ["match", "pat", "search", "current", "line", "pos"]
        '''
        if self.exclude_re:
            line = self.exclude_re.sub('', line)
        return self._word_re.findall(line)

    def _send_words(self):
        self.ispell.set_dictionary(self.dictionaries.get_filename())
        self.ispell.open()

        for line in self.file:
            self.line_num += 1
            for word in self.split_line(line):
                if word in self.locations:
                    self.locations[word].append(self.line_num)
                else:
                    self.locations[word] = [self.line_num]
                    self.ispell.send(word)

        self.ispell.done_sending()

    def _check(self):
        '''
        Report spelling errors found in the current file to stderr.
        Return true if there were any spelling errors.
        '''
        errors = []
        for (bad_word, guesses) in self.ispell.check():
            locations = self.locations[bad_word]
            if self.unique:
                del locations[1:]
            for line_num in locations:
                errors.append((line_num, bad_word, guesses))

        errors.sort()                   # sort on line number
        return errors

    def _report(self, messages, file):
        for (line_num, bad_word, guesses) in messages:
            guesses = ", ".join(guesses)
            print("%s:%d: %s: %s?"
                  % (self.filename, line_num, bad_word, guesses),
                  file=file)

    def check_file(self):
        '''
        Spell-check the current file, reporting errors to stdout.
        Return true if there were any spelling errors.
        '''
        if self.exclude:
            self.exclude_re = re.compile(r'\b(%s)\b' % '|'.join(self.exclude))
        self._send_words()
        errors = self._check()
        self._report(errors, sys.stdout)
        return bool(errors)


if __name__ == "__main__":
    import sys
    sys.exit(CodeChecker(sys.argv[1]).check_file() and 1 or 0)
