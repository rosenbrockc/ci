#!/usr/bin/env python
try:
    from setuptools import setup
    args = {}
except ImportError:
    from distutils.core import setup
    print("""\
*** WARNING: setuptools is not found.  Using distutils...
""")

from setuptools import setup
try:
    from pypandoc import convert
    read_md = lambda f: convert(f, 'rst')
except ImportError:
    print("warning: pypandoc module not found, could not convert Markdown to RST")
    read_md = lambda f: open(f, 'r').read()

setup(name='pyci',
      version='0.0.4',
      description='Continuous integration server for Github and MediaWiki.',
      long_description=read_md('README.md'),
      author='Conrad W Rosenbrock',
      author_email='rosenbrockc@gmail.com',
      url='https://github.com/rosenbrockc/ci',
      license='MIT',
      install_requires=[
          "argparse",
          "termcolor",
          "dominate",
          "mwclient",
          "python-crontab",
          "pygithub"
      ],
      packages=['pyci'],
      scripts=['pyci/scripts/ci.py'],
      package_data={'pyci': ['templates/start.txt', 'templates/start.html',
                              'templates/error.txt', 'templates/error.html',
                              'templates/failure.txt', 'templates/failure.html',
                              'templates/timeout.txt', 'templates/timeout.html',
                              'templates/success.txt', 'templates/success.html']},
      include_package_data=True,
      classifiers=[
          'Development Status :: 3 - Alpha',
          'Intended Audience :: Developers',
          'Natural Language :: English',
          'License :: OSI Approved :: MIT License',          
          'Operating System :: MacOS',
          'Operating System :: Unix',
          'Programming Language :: Python',
          'Programming Language :: Python :: 2',
          'Programming Language :: Python :: 2.7',
          'Topic :: Software Development :: Libraries :: Python Modules',
      ],
     )
