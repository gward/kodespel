from glob import glob
from setuptools import setup

dict_files = glob("dict/*.dict")

setup(
    scripts=["scripts/codespell"],
    py_modules=["codespell"],
    package_dir={"": "lib"},
    data_files=[('share/codespell', dict_files)],
)
