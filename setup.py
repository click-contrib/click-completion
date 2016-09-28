#!/usr/bin/env python
# -*- coding:utf-8 -*-

import ast
import re

from setuptools import setup

_version_re = re.compile(r'__version__\s+=\s+(.*)')

with open('click_completion.py', 'rb') as f:
    version = str(ast.literal_eval(_version_re.search(
        f.read().decode('utf-8')).group(1)))

setup(
    name='click-completion',
    version=version,
    description='Fish, Bash, Zsh and PowerShell completion for Click',
    author='Gaëtan Lehmann',
    author_email='gaetan.lehmann@gmail.com',
    url='https://github.com/glehmann/click-completion',
    license='MIT',
    py_modules=['click_completion'],
    install_requires=[
        'click',
        'jinja2',
        'six',
    ],
)
