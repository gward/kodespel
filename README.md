# kodespel

kodespel is a spellchecker for source code.
It is implemented as a small Python script with
all the real work done in a library (package `kodespel`).

kodespel's nifty trick is that it knows how to split
common programming identifiers like
'getAllStuff' or 'DoThingsNow' or 'num_objects' or 'HTTPResponse'
into words, feed those to ispell, and interpret ispell's output.

## Requirements & installation

kodespel requires Python 3.6+ and
[ispell](https://www.cs.hmc.edu/~geoff/ispell.html).
To install ispell, use your OS-specific package manager
(e.g. apt, dnf, brew, ...).

To install kodespel itself, use pip:

    pip install --user kodespel

(Or install it in a virtualenv if you prefer.)

## Usage

Basic usage is to run kodespel on one or more individual files
or directories:

    kodespel foo.py main.go README.md

kodespel uses a collection of _dictionaries_ to spellcheck each file.
It always uses the `base` dictionary,
which is a set of words common in source code
across languages and platforms.
Additionally, there is a language-specific dictionary
for each language the kodespel knows about.
Language-specific dictionaries are automatically chosen for you.

In this example, kodespell will spellcheck each file with:
* `foo.py`: dictionaries `base` and `python`
* `main.go`: dictionaries `base` and `go`
* `README.md`: dictionary `base` only
  (no language dictionary for Markdown)

If run on a directory, kodespel will recurse into that directory
and spellcheck every file that it recognizes:

    kodespel src/

will search for `*.py`, `*.c`, `*.h`, and any other
extension that kodespel has built-in support for.
(Currently: Python, Perl, Go, C, C++, and Java.)
Unsupported files are ignored, but if you pass those filenames
explicitly, they will be checked.

kodespel ships with several other common dictionaries.
For example, if the program you are spellchecking uses
a lot of Unix system calls, you would add the `unix` dictionary:

    kodespel -d unix foo.py main.go README.md

The `-d` option applies to every file being checked.

To see the list of all builtin dictionaries, run

    kodespel --list-dicts

Finally, you can create your own dictionaries,
and use as many of them as you like.
A dictionary is a plain text file with one word per line:

    $ cat myproject.dict
    nargs
    args

You can specify your person dictionaries with `-d`,
just  like kodespel's builtin dictionaries:

    kodespel -d unix -d myproject.dict foo.py ...

## See also

A tool with similar goals but a different implementation is
[codespell](https://pypi.org/project/codespell/).

The main advantage of codespell is that it seems to have
many fewer false positives.

The main advantage of kodespel is that it checks identifiers,
not just comments and strings,
so can find a lot more errors.
And more false positives too, unfortunately.
