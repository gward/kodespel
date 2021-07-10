#!/bin/sh

set -e
flake8 kodespel tests
mypy --check-untyped-defs kodespel tests
PYTHONPATH=. pytest kodespel tests
