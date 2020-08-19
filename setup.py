#!/usr/bin/env python
import io

# Always prefer setuptools over distutils
from setuptools import setup

# To use a consistent encoding
from os import path

from estoult import __version__

here = path.abspath(path.dirname(__file__))

with io.open("README.md", "rt", encoding="utf8") as f:
    readme = f.read()

setup(
    name="estoult",
    version=__version__,
    description="Data mapper and query builder for SQL databases.",
    long_description=readme,
    long_description_content_type="text/markdown",
    author="Justin Duch",
    author_email="justin@justinduch.com",
    url="https://github.com/halcyonnouveau/estoult",
    py_modules=["estoult"],
    packages=["apocryphan"],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    license="MIT",
)
