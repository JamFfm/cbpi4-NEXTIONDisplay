from setuptools import setup

# read the contents of your README file
from os import path
this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(name='NEXTIONDisplay',
      version='0.0.1',
      description='CraftBeerPi Plugin',
      author='',
      author_email='',
      url='',
      include_package_data=True,
      package_data={
          # If any package contains *.txt or *.rst files, include them:
          '': ['*.txt', '*.rst', '*.yaml'],
          'NEXTIONDisplay': ['*', '*.txt', '*.rst', '*.yaml']},
      packages=['NEXTIONDisplay'],
      install_requires=['cbpi>=4.0.0.33',
                        'pyserial>=3.4',
                        ],
      long_description=long_description,
      long_description_content_type='text/markdown'
      )
