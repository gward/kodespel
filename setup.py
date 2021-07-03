from glob import glob
from setuptools import setup

dict_files = glob("dict/*.dict")

setup(
    packages=["kodespel"],
    data_files=[('share/kodespel', dict_files)],
)
