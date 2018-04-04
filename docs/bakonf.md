---
title: BAKONF(8)
date: March 2018
---

# NAME

bakonf - a configuration backup tool

# SYNOPSIS

**bakonf**
[ **-c**, **--config**=*FILENAME* ]
[ **-f**, **--file**=*FILENAME* ]
[ **-d**, **--dir**=*DIRECTORY* ]
[ **-g**, **--gzip** | **-b**, **--bzip2** | **-x**, **--xz** ]
[ **--no-filesystem** | **--no-commands** ]
[ **-L**, **--level**=*0|1* ]
[ **-S**, **--state-file**=*FILENAME* ]
[ **-v**, **--verbose** … ]
[ **-q**, **--quiet** ]

**bakonf**
**--version**

**bakonf**
**-h**, **--help**

# DESCRIPTION

Archive some parts of the filesystem and command output, as directed by
the configuration file.

The following options are recognised:

-L, --level=0|1

:   This options applies to the archiving of files. If the level given
    is 0, the state database is cleared, all files which match the
    configuration options are archived, and their state is then saved in
    the state database. If the level is 1, the database is opened
    readonly, and only the files which are no longer equal with their
    state as recorded in the database, or files which don't have an
    entry in the database, are stored.

    The recommended operation mode is to create weekly an archive using
    level 0, and daily one using level 1. In this way, you need any
    weekly archive to recreate the full system, and if the daily archive
    is also available, you will have the latest configuration.

-c, --config=FILENAME

:   Use FILENAME as configuration file, instead of the default
    `/etc/bakonf/bakonf.yml`.

-f, --file=FILE

:   Save the generated archive as FILE. Note that if this parameter is
    given it will override any directory given with `-d` (i.e. this name
    is taken a a full filename).

-d, --dir=DIRECTORY

:   Save the generated archive under the given DIRECTORY. The filename
    will be constructed using the current hostname and year, month, day
    (e.g. `host.example.com-2002-12-19.tar`). If any of the compression
    options are given, the file will have the proper suffix appended. If
    not given, the default directory is `/var/lib/bakonf/archives`.

-S, --state-file=FILE

:   This options will override the value for the database. It can be
    used for quick testing instead of modifying the config file.

-g, --gzip

:   Compress the generated archive with gzip; mutually exclusive with
    the other compression options.

-b, --bzip2

:   Compress the generated archive with bzip2; mutually exclusive with
    the other compression options.

-x, --xz

:   Compress the generated archive with xz; mutually exclusive with
    the other compression options.

    Note this is only available if you're running bakonf with at least
    Python 3.3, as earlier versions did not support the LZMA
    compression algorithm.

--no-filesystem

:   Do not save any files in the filesystem. In this case bakonf does
    not even open a database.

--no-commands

:   Do not save command output in the archive,

-v, --verbose

:   Increases the verbosity by one; the default level of verbosity is
    one, under which information and higher severity messages are
    displayed; at level two, debug mode is enabled which shows the trace
    of actions.

-q, --quiet

:   Resets the verbosity to zero; at this level, only warning and higher
    messages are shown.

--version

:   Shows the version number and exits.

-h, --help

:   Shows a short help message about the invocation and exits.

# NOTES

Note that the for the compression options, the external command
line tools are not used, but rather internal Python libraries. As
such, you don't need to install for example the `bzip2` package if you
want to use that compression method.

# AUTHORS

Written by Iustin Pop, <iustin@k1024.org>.

# COPYRIGHT

Copyright © 2002, 2004, 2008, 2009, 2010 by Iustin Pop.

This program is free software; you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation; either version 2, or (at your option) any
later version.

You should have received a copy of the GNU General Public License along
with this program; see the file COPYING. If not, please write to the
Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.
