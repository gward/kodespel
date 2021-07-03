# kodespel

kodespel is a Python script for spell-checking source code;
its back-end is kodespel.py, a module that does all the work.
The main trick is that it knows how to split common programming
identifiers like 'getAllStuff' or 'DoThingsNow' or 'num_objects'
or 'HTTPResponse' into words, and then feed those to ispell.
