#!/bin/sh

flake8 codespell tests
PYTHONPATH=. pytest codespell tests
