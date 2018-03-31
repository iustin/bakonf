# `bakonf`

[![Travis build status](https://img.shields.io/travis/iustin/bakonf.svg?maxAge=3600)](https://travis-ci.org/iustin/bakonf)
[![Coveralls status](https://img.shields.io/coveralls/github/iustin/bakonf.svg?maxAge=3600)](https://coveralls.io/github/iustin/bakonf)
[![Read the Docs](https://img.shields.io/readthedocs/bakonf.svg?maxAge=3600)](http://bakonf.readthedocs.io/en/latest/?badge=latest)
[![GitHub issues](https://img.shields.io/github/issues/iustin/pyxattr.svg?maxAge=3600)](https://github.com/iustin/bakonf/issues)
[![GitHub pull requests](https://img.shields.io/github/issues-pr/iustin/bakonf.svg?maxAge=3600)](https://github.com/iustin/bakonf/pulls)

`bakonf` is a small script designed to make minimal backups of the
*configuration* files of a GNU/Linux or Unix-like system. Its aim is
to use various methods to reduce the size of the backup to a
reasonable minimum, in order to be useful for remote/unattended
servers, while still backing up enough to recreate the system (with
effort) in a blank state. The actual user data backup/restore is a
separate matter, which bakonf doesn't deal with.


The contents of the archives created contain enough information so
that the system admininistrator can restore the system to a working,
but blank state.  Beside the actual information from the file system,
it can store output of arbitrary commands, for example:

- partition table
- various /proc information
- pci & usb device list

Requirements:

- Python 2.7/3.5+
- PyYaml
- bsdd3

For more information, see the user manual in the doc directory, or
read the documentation [online](https://bakonf.readthedocs.io/).

Iustin Pop, <iustin@k1024.org>.
