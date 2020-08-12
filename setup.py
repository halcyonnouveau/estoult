#!/usr/bin/env python
import io

# Always prefer setuptools over distutils
from setuptools import setup

# To use a consistent encoding
from os import path

here = path.abspath(path.dirname(__file__))

with io.open("README.md", "rt", encoding="utf8") as f:
    readme = f.read()

setup(
    name='estoult',
    version='0.0.0',
    description='Simple SQL data mapper.',
    long_description=readme,
    long_description_content_type="text/markdown",
    author='Justin Duch',
    author_email='justin@justinduch.com',
    url='https://github.com/halcyonnouveau/estoult',
    py_modules=['estoult'],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    license='MIT'
)
