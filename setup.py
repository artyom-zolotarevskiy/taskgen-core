#!/usr/bin/env python
from setuptools import setup, find_packages
import os

with open('README.md', 'r', encoding='utf-8') as fh:
    long_description = fh.read()


def parse_requirements(filename):
    """Load requirements from a pip requirements file."""
    if not os.path.exists(filename):
        return []
    lineiter = (line.strip() for line in open(filename))
    return [
        line
        for line in lineiter
        if line and not line.startswith("#") and not line.startswith("git+")
    ]


setup(name='taskgen',
      version='0.3.8.1',
      author='Артём Золотаревский',
      author_email='artyom@zolotarevskiy.ru',
      description='Ядро генератора банка задач на базе MiKTeX и Jupyter Notebook',
      long_description=long_description,
      long_description_content_type="text/markdown",
      url='https://github.com/artyom-zolotarevskiy/taskgen-core',
      project_urls={
          'Bug Tracker': 'https://github.com/artyom-zolotarevskiy/taskgen-core/issues',
      },
      license='',
      packages=find_packages(),
      install_requires=parse_requirements('requirements.txt'),
      classifiers=[
          'Programming Language :: Python :: 3',
          'Operating System :: OS Independent',
      ],
      )
