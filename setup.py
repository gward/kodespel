#!/usr/bin/python

from time import time, localtime, strftime
from glob import glob
from distutils.core import setup

datestamp = strftime("%Y%m%d", localtime(time()))
dict_files = glob("dict/*.dict")

setup(name="codespell",
      version=datestamp,
      description="script and Python module for spell-checking source code",
      long_description="""\
codespell is a Python script for spell-checking source code;
its back-end is codespell.py, a module that does all the work.
The main trick is that it knows how to split common programming
identifiers like 'getAllStuff' or 'DoThingsNow' or 'num_objects'
or 'HTTPResponse' into words, and then feed those to ispell.
""",

      author="Greg Ward",
      author_email="gward-codespell@python.net",
      scripts=["scripts/codespell"],
      py_modules=["codespell"],
      package_dir={"": "lib"},

      data_files=[('/usr/share/codespell', dict_files)],
      )
