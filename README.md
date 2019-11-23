# bakonf

[![Travis build status](https://img.shields.io/travis/iustin/bakonf)](https://travis-ci.org/iustin/bakonf)
[![Coveralls status](https://img.shields.io/coveralls/github/iustin/bakonf)](https://coveralls.io/github/iustin/bakonf)
[![Read the Docs](https://img.shields.io/readthedocs/bakonf)](http://bakonf.readthedocs.io/en/latest/?badge=latest)
[![GitHub issues](https://img.shields.io/github/issues/iustin/pyxattr)](https://github.com/iustin/bakonf/issues)
![GitHub tag (latest by date)](https://img.shields.io/github/v/tag/iustin/bakonf)
![GitHub release (latest by date)](https://img.shields.io/github/v/release/iustin/bakonf)
![GitHub Release Date](https://img.shields.io/github/release-date/iustin/bakonf)
![GitHub commits since latest release](https://img.shields.io/github/commits-since/iustin/bakonf/latest)
![GitHub last commit](https://img.shields.io/github/last-commit/iustin/bakonf)

_bakonf_ is a small script designed to make minimal backups of the
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

- list of installed packages
- partition table
- various /proc information
- pci & usb device list

Requirements:

- Python 3.5+ (for Python 2.7, use version 0.6)
- PyYaml
- bsdd3

For more information, see the user manual in the doc directory, or
read the documentation [online](https://bakonf.readthedocs.io/).

Iustin Pop, <iustin@k1024.org>.
