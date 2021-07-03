from glob import glob
from setuptools import setup

dict_files = glob("dict/*.dict")

setup(
    packages=["codespell"],
    data_files=[('share/codespell', dict_files)],
)
