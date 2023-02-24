#!/usr/bin/env python
from setuptools import setup, find_packages

with open('README.md', 'r', encoding='utf-8') as fh:
    long_description = fh.read()


def parse_requirements(filename):
    """Load requirements from a pip requirements file."""
    lineiter = (line.strip() for line in open(filename))
    return [
        line
        for line in lineiter
        if line and not line.startswith("#") and not line.startswith("git+")
    ]


setup(name='taskgen',
      version='0.3.1',
      author='Артём Золотаревский',
      author_email='artyom@zolotarevskiy.ru',
      description='Генератор экзаменационных билетов на базе MikTex',
      long_description=long_description,
      long_description_content_type="text/markdown",
      url='https://github.com/artyom-zolotarevskiy/taskgen',
      project_urls={
          'Bug Tracker': 'https://github.com/artyom-zolotarevskiy/taskgen/issues',
      },
      license='GPLV3',
      packages=find_packages(),
      install_requires=parse_requirements('requirements.txt'),
      classifiers=[
          'Programming Language :: Python :: 3',
          'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
          'Operating System :: OS Independent',
      ],
      )
