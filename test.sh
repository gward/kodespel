#!/bin/sh

flake8 kodespel tests
PYTHONPATH=. pytest kodespel tests
