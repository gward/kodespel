# kodespel

kodespel is a Python script for spell-checking source code.
Its back-end is a package `kodespel`, which does all the work.

kodespel's nifty trick is that it knows how to split
common programming identifiers like
'getAllStuff' or 'DoThingsNow' or 'num_objects' or 'HTTPResponse'
into words, then feed those to ispell,
and interpret ispell's output.

## See also

A tool with similar goals but a different implementation is
[codespell](https://pypi.org/project/codespell/).

The main advantage of codespell is that it seems to have
many fewer false positives.

The main advantage of kodespel is that it checks identifiers,
not just comments and strings,
so can find a lot more errors.
And more false positives too, unfortunately.
