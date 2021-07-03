#!/bin/sh

PYTHONPATH=lib; export PYTHONPATH
flake8 lib scripts tests
pytest tests lib
