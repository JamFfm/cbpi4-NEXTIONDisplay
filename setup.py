from setuptools import setup, find_packages
from os import path

# read the contents of your README file
this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(name='cbpi4-NEXTIONDisplay',
      version='0.0.1',
      description='CraftBeerPi4 NEXTIONDisplay Plugin',
      author='Jan Battermann',
      author_email='jan.battermann@t-online.de',
      url='https://github.com/JamFfm/cbpi4-NEXTIONDisplay',
      license='GPLv3',
      include_package_data=True,
      package_data={
          # If any package contains *.txt or *.rst files, include them:
          '': ['*.txt', '*.rst', '*.yaml'],
          'cbpi4-NEXTIONDisplay': ['*', '*.txt', '*.rst', '*.yaml']},
      # packages=['cbpi4-NEXTIONDisplay'],
      packages=find_packages(),
      install_requires=[
            'cbpi>=4.0.0.33',
            'pyserial',
      ],
      long_description=long_description,
      long_description_content_type='text/markdown'
      )
