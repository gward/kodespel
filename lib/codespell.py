'''
Module for spell-checking programming language source code.  The trick
is that it knows how to split identifiers up into words: e.g. if the
token getRemaningObjects occurs in source code, it is split into "get",
"Remaning", "Objects", and those words are piped to ispell, which easily
detects the spelling error.  Handles various common ways of munging
words together: identifiers like DoSomethng, get_remaning_objects,
SOME_CONSTENT, and HTTPRepsonse are all handled correctly.

Requires Python 2.3 or greater.
'''

import sys, os
import re
from tempfile import mkstemp

assert sys.hexversion >= 0x02030000, "requires Python 2.3 or greater"


def warn(msg):
    sys.stderr.write("warning: %s: %s\n" % (__name__, msg))

def error(msg):
    sys.stderr.write("error: %s: %s\n" % (__name__, msg))

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
        # Use -C to handle identifiers like "hashopen" or
        # "getallmatchingheaders" (which are conventional in Python).
        cmd = ["ispell", "-a"]
        if self.allow_compound:
            cmd.append("-C")
        if self.word_len is not None:
            cmd.append("-W%d" % self.word_len)
        if self.dictionary:
            cmd.extend(["-p", self.dictionary])
        #print " ".join(cmd)
        (self.ispell_in, self.ispell_out) = os.popen2(cmd, "t", 1)
        firstline = self.ispell_out.readline()
        assert firstline.startswith("@(#)"), \
               "expected \"@(#)\" line from ispell (got %r)" % firstline

        # Put ispell in terse mode (no output for correctly-spelled
        # words).
        self.ispell_in.write("!\n")

        # Total number of unique spelling errors seen.
        self.total_errors = 0

    def close():
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
            #(ready, _, _) = select.select([self.ispell_out], [], [])
            #if not ready:               # nothing to read
            #    break
            #assert ready[0] is self.ispell_out

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


class CodeChecker(object):
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

        # If true, report each misspelling only once (at its first
        # occurrence).
        'unique',

        # List of directories to search for dictionary files.
        'dict_path',

        # List of custom dictionaries.  Dictionaries are specified either
        # as a filename ("dict/myproject.dict") or a basename ("unix"),
        # which is resolved against the CodeChecker's dict_path.
        'custom_dictionaries',
        ]

    EXTENSION_LANG = {".py": "python",
                      ".c": "c",
                      ".h": "c",
                      ".cpp": "c",
                      ".hpp": "c",
                      ".java": "java"}


    def __init__(self, filename=None, file=None):
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
        self.unique = False

        prog = sys.argv[0]
        while os.path.islink(prog):
            prog = os.path.join(os.path.dirname(prog), os.readlink(prog))
        script_dir = os.path.dirname(prog)
        self.dict_path = ["/usr/share/codespell",
                          os.path.join(script_dir, "../dict")]
        self.custom_dictionaries = []

        # Try to determine the language from the filename, and from
        # that get the list of exclusions.
        if filename:
            ext = os.path.splitext(filename)[1]
            lang = self.EXTENSION_LANG.get(ext)
            if lang:
                self.set_language(lang)

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

    def set_language(self, lang):
        '''
        Set the language for the current file (used to determine the
        custom dictionary).
        '''
        self.language = lang

    def add_dictionary(self, dictionary):
        '''
        Specify a custom dictionary file, which can either be a working
        filename, or a base filename which is searched for in 'dict_path'
        after appending ".dict".
        '''
        self.custom_dictionaries.append(dictionary)

    def guess_language(self, first_line):
        '''
        Attempt to guess the programming language of the current file
        by examining the first line of source code.  Mainly useful
        for Unix scripts with a #! line.
        '''
        if not first_line.startswith("#!"):
            return
        if "python" in first_line:
            self.set_language("python")
        elif "perl" in first_line:
            self.set_language("perl")

    def set_unique(self, unique):
        self.unique = unique

    # A word is either:
    #   1) a string of letters, optionally capitalized; or
    #   2) a string of uppercase letters not immediately followed
    #      by a lowercase letter
    # Case 1 handles almost everything, eg. "getNext", "get_next",
    # "GetNext", "HTTP_NOT_FOUND", "HttpResponse", etc.  Case 2 is
    # needed for uppercase acronyms in mixed-case identifiers,
    # eg. "HTTPResponse", "getHTTPResponse".
    _word_re = re.compile(r'[A-Z]?[a-z\']+|[A-Z\']+(?![a-z])')

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

    def _create_dict(self):
        dicts = ["base", self.language] + self.custom_dictionaries
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

        (out_fd, out_filename) = mkstemp(".dict", "codespell-")
        #print "creating %r" % out_filename
        out_file = os.fdopen(out_fd, "wt")
        for filename in dict_files:
            #print "appending %r" % filename
            in_file = open(filename, "rt")
            out_file.write(in_file.read())
            in_file.close()

        return out_filename


    def _send_words(self):
        dict_filename = None
        for line in self.file:
            # If this is the first line of the file, and we don't yet
            # know the programming language, try to guess it from the
            # content of the line (which might be something like
            # "#!/usr/bin/python" or "#!/usr/bin/perl")
            if self.line_num == 0:
                if self.language is None:
                    self.guess_language(line)
                dict_filename = self._create_dict()

                self.ispell.set_dictionary(dict_filename)
                self.ispell.open()

            self.line_num += 1
            for word in self.split_line(line):
                if word in self.locations:
                    self.locations[word].append(self.line_num)
                else:
                    self.locations[word] = [self.line_num]
                    self.ispell.send(word)

        self.ispell.done_sending()
        if dict_filename:
            os.unlink(dict_filename)

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
            print >>file, ("%s:%d: %s: %s?"
                           % (self.filename, line_num, bad_word, guesses))

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
