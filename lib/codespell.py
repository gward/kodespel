'''
Module for spell-check programming language source code.  The trick is
that it knows how to split identifiers up into words: e.g. if the token
getRemaningObjects occurs in source code, it is split into "get",
"Remaning", "Objects", and those words are piped to ispell, which easily
detects the spelling error.  Handles various common ways of munging
words together: identifiers like DoSomething, get_remaning_objects,
SOME_CONSTENT, and HTTPResponse are all handled correctly.
'''

import sys, os
import re
import select

def warn(msg):
    sys.stderr.write("warning: %s\n" % msg)

def error(msg):
    sys.stderr.write("error: %s\n" % msg)

class SpellChecker:
    '''
    A wrapper for ispell.  Opens two pipes to ispell: one for writing
    (sending) words to ispell, and the other for reading reports
    of misspelled words back from it.
    '''

    def __init__(self):
        cmd = ["ispell", "-a"]
        #cmd = ["strace", "-o", "ispell-pipe.log", "ispell", "-a"]
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
        #print "sending %r to ispell" % word
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
            

class CodeChecker:
    '''
    Object that reads a source code file, splits it into tokens,
    splits the tokens into words, and spellchecks each word.
    '''

    def __init__(self, filename=None, file=None):
        self.filename = filename
        if file is None and filename is not None:
            self.file = open(filename, "rt")
        else:
            self.file = file
        self.line_num = 0

        # Map word to list of line numbers where that word occurs.
        # Also tracks which words we've already checked, so we don't
        # need to bother ispell with the same word twice.
        self.locations = {}

        # If true, report each misspelling only once (at its first
        # occurrence).
        self.unique = False

        # Pair of pipes to send words to ispell and read errors back.
        self.ispell = SpellChecker()

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
    _word_re = re.compile(r'[A-Z]?[a-z]+|[A-Z]+(?![a-z])')

    def split(self, line):
        '''
        Given a line (or larger chunk) of source code, splits it
        into words.  Eg. the string
          "match = pat.search(current_line, 0, pos)"
        is split into
          ["match", "pat", "search", "current", "line", "pos"]
        '''
        return self._word_re.findall(line)

    def _send_words(self):
        for line in self.file:
            self.line_num += 1
            for word in self.split(line):
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
        messages = []
        for (bad_word, guesses) in self.ispell.check():
            if guesses:
                message = "%s: %s ?" % (bad_word, ", ".join(guesses))
            else:
                message = "%s ?" % bad_word

            if self.unique:
                messages.append((self.locations[bad_word][0], message))
            else:
                for line_num in self.locations[bad_word]:
                    messages.append((line_num, message))

        messages.sort()
        for (line_num, message) in messages:
            sys.stderr.write("spelling: %s:%d: %s\n"
                             % (self.filename, line_num, message))
        return bool(messages)

    def check_file(self):
        '''
        Spell-check the current file, reporting errors to stderr.
        Return true if there were any spelling errors.
        '''
        self._send_words()
        return self._check()


if __name__ == "__main__":
    import sys
    sys.exit(CodeChecker(sys.argv[1]).check_file() and 1 or 0)
