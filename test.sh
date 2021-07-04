#!/bin/sh

set -e
flake8 kodespel tests
PYTHONPATH=. pytest kodespel tests
