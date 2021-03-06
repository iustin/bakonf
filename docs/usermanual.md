---
title: bakonf user manual
---
## About this document

This is the user manual for the bakonf project, version 0.7.0; the
homepage is at <http://github.com/iustin/bakonf/>. You can also get
new versions of this document there.

## Introduction

Making backup is an important aspect of system administration. The
techniques of backing up data are explained in any good document about
system administration, and they won't be explained here again.

bakonf comes into play into a particular part of the backups: minimal
backups of the system's configuration and state, for the case where a
standard (full) backup is unfeasible.

The basic idea is that on a standard installation of a Unix-like system
you have a lot of data which can be very easily restored from the
original media, thus there is no point in archiving it. For example,
after a fresh install of a RedHat Linux 8.0, you have ~4.5GB of space
used. However, only a *very* small part of this amount is holding
important information, the other part being binaries, libraries and
other kind of data which will never modify in normal usage. Only the
configuration files are changing (of course, also the user data is
changing, but we are talking about an empty system).

If we classify the files existing on a Unix system, we have:

configuration data

:   These are the target of bakonf; they are usually small text files,
    partly coming from the system installation, maybe edited by the
    administrator, partly created by him. Size is (on the workstation I
    write this) around 15MB (true in 2002, still true in 2018).

binaries, libraries, other system files

:   These are mostly read-only; in a package based distribution, they
    came from the packages and are replaced when the package is
    upgraded. In classical systems, they come from the install archives.
    Size is (in our hypothetical rh8.0 full install) ~4.5GB.

system and user data

:   These are emails, web pages, documents, etc. - this is important
    data, and needs to be backed up regularly. They also don't come
    from the installation media, and are not touched by the
    system. Size is undetermined, but is guaranteed to be exactly the
    amount of free space on the system :). This is the main target of
    a regular backup.

system maintenance data

:   These are the files created and managed by the system, usually from
    the configuration files and other external variables. Examples:
    `/var/lib/logrotate.status`, `/var/lib/slocate/slocate.db`. These
    are not all critical files, some are needed to be included in a
    backup only for analysis purposes, others should not be included in
    backups (e.g. if you reinstall your system or restore from backup,
    some files will have for sure other contents, generated from the new
    installation).

non-file data

:   This is data that still lives on storage, but not directly as
    files. For example, partition tables, logical volume
    configuration.

From all these, only the configuration data and the system/user data
are absolutely required to recreate the system. Depending on the
setup, the non-file data might be required as well, but (in case of
partitions, for example) is not required exactly as it was before. The
binaries can come from the installation source. The system maintenance
data will be recreated by the system. And since the difference in size
between the configuration and user data is so great in a typical
system, that I believe it deserves another backup method than a
regular, full-backup - which, as said before, definitely has its
place.

## Quick start

-   run bakonf with the `-L0` option to archive all config files and
    create its database:

        root@test:~$ bakonf -L0

    If everything went well, bakonf has created an archive under
    `/var/lib/bakonf/archives` named after your host. Look into that
    directory to find it. If any errors have occurred, bakonf will tell
    you:

        user@test:~$ bakonf -L0
        Error: cannot read '/nfs/README': 'Permission denied'. Not archived.
        Warning: '/sbin/lsusb -vv' exited with status 1.
        Warning: '/sbin/sfdisk -d /dev/hda' exited with status 1.
        [user@test user]$

-   run daily (or more often) bakonf with the `-L1` option to archive
    only the changed files since the previous step. This archive should
    be much smaller. It will be easy, *after encryption*, to email it:

        root@test:~ bakonf -L1

-   every week, go back to the first step.

## Generated archive

bakonf's output is a tar archive (optionally compressed) that contains
some metadata and (if both enabled) two sections: file backup and
command output.

| Filename                     | Description                                                                                                                                                         | Created when                               |
|------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------|
| README                       | A file which contains information about the archive: when it was generated, with which options and on what host                                                     | Always                                     |
| ``unarchived_files.lst``     | A file which contains details about which files couldn't be backed up; this can happen when bakonf is not run as root, or for example when it scans NFS directories | When file system backup has been performed |
| ``commands_with_errors.lst`` | A file which contains details about which commands have exited with non-zero status. Their output is still stored in the archive, though.                           | When command execution has been performed  |
| ``filesystem/``              | Files backed up are stored under this path.                                                                                                                         | When file system backup has been performed |
| ``commands/``                | Outputs from the command execution are stored under this path.                                                                                                      | When command execution has been performed  |

### File system backup

Bakonf supports a simple incremental backup, by the use of two level:
0 and 1. In level 0, it archives all of the specified configuration
files and registers the state of those configuration files in a
database (called state database), of type Berkeley DB. In level 1, it
archives only the files modified since the last level 0 backup; it
does this by comparing the state database with the current state of
the file system.

#### File types and states

##### directories

Directories won't be archived if they don't contain files to be backed
up.  On the other hand, for each file to be backed up, bakonf will
also backup (non-recursively) its parent directories (except root) so
that you have the user, group, modification time and permissions of
each directory. For example, if `/usr/local/etc/myconfig` has been
selected for archiving, bakonf will actually archive this list of
items: `/usr`, `/usr/local`, `/usr/local/etc`,
`/usr/local/etc/myconfig`.

##### regular files

Regular files will be archived by bakonf if they aren't excluded by
the `noscan` configuration directive. In case this is a partial backup
(as opposed to a full backup), bakonf will make the following tests:

-   does the size of file saved in database differ from the current
    file size? if so, include;
-   do the saved hashes (md5 and sha1) differ from the current hashes?
    if so, include;
-   otherwise, file will not be included in the incremental backup.

##### symbolic links

bakonf doesn't follow symbolic links; it treats a symbolic link like a
configuration file (its configuration data resides in its name and its
target). For an incremental backup, the tests made by bakonf are, in
order:

-   link target must be equal, or the file is backed up
-   user and group ownership must be equal, or the file is backed up
-   permission bits must be equal, or the file is backed up
-   the file is not backed up

##### block devices, character devices, fifos, sockets

bakonf always selects these to backed up. Of course, some of them
won't be backed up by tar, but regarding bakonf, it will select those
for backup.

##### changed file types

In case the file type has changed between the level 0 and level 1
backup, bakonf will always include this file.

### Command execution/output

This section allows you to save more information about a system than is
available in the file-system. The current implementation allows you to
store output of shell commands. Suggestions about other items are
welcome.

#### Examples

##### Partition table

One of the most important items about a system (that is not stored in a
file) is partition table about your disks, in the eventuality that you
have a data error in partition table. The command to back this up
varies, for example `sfdisk`, `fdisk`, etc.

Further, one could consider the volume group configuration similar to
the partition table, although this usually has backups.

##### Device list

Having the device list is and their hardware configuration is useful in
order to have a quick overview if you want to clone the configuration
from one system to another (to see correspondence between config files
and hardware config). Examples of scanning the configuration are
`lspci -vv`, `lsusb -vv`, `pciconf -lv`, etc.

##### Installed package list

While the installed package list can be recovered from a package
database, sometimes this database is binary, or much more verbose. So
the output of, for example, `dpkg -l` or `rpm -ql` is much easier to
read and feed back to `apt-get` or `rpm`.

### What can I use bakonf for?

Potential use cases:

-   Configuration rollback. Since the archives are small, you can keep
    many versions, but unlike in differential backup, here one archive
    contains all the needed data.
-   Configuration cloning. You can take a bakonf-generated archive from
    one system to another and 'clone' as much of the settings as you
    want.
-   Quick restore of a server in case of catastrophic hard-disk failure.
    Just reinstall the OS and put the config files back.

### Requirements

To use bakonf, you must have the following:

-   a Unix-like operating system
-   [Python](http://www.python.org/) version 2.4 or higher
-   the ElementTree library for Python, for parsing the configuration
    file(s)
-   the pybsddb library, if not bundled with your Python distribution

## Configuration

**Note:** Older bakonf versions (before 0.5) had an entirely different
config file, and version 0.5 had a different schema for the
configuration files. If you upgraded, be sure to forward you changes
to the new config files.

bakonf uses a main configuration file (by default
`/etc/bakonf/bakonf.yaml`), which does some standard settings and
tells bakonf what other files to include. These additional files are
usually located in `/etc/bakonf/sources` and tell bakonf how to handle
some special cases.

### Configuration language

The configuration file is written in YAML, and should represent an
object (map) with the following keys:

configs

:   (list) tells bakonf to also parse any files which match the shell
    patterns passed. These are files which modify bakonf's own
    behaviour, and are usually located in /etc/bakonf/sources. These
    are not directories to be backed up!  (Although, if modified and
    included by the `filesystem/include` entries, they will be). Note
    that the sub-files can contain only `filesystem` and `commands`
    keys.

include

:   (list) Tells bakonf to add any file or directory which matches
    shell pattern given by the contents of the tag to its include
    list.  These can be files or directories. Bakonf will descend
    directories, but will **not** follow symbolic links! The symbolic
    links are considered configuration items also, so they will be
    backed up themselves.

exclude

:   (list) Tells bakonf to ignore any file or directory which matches
     the contents of the elements (interpreted as a regular
     expression) from the archive; it won't even open or stat these
     files. Note that the patterns given are prefix matches, so for
     example an expression `/path/to` will match (and thus exclude) a
     file `/path/to/file`.

commands

:   (list) Contains declarations about command output to be included
    in the archive. Each element in the list is a dictionary with the
    following keys:

    cmd:

    :   Defines the command line to be executed (as a shell command).

    dest:

    :   Defines the destination archive member to be used for the
        output under the `commands` subtree in the created archive. If
        this key is not given, then the destination is takes as the
        command line with slashes replaced by underscores. For
        example, the element:

                cmd: cat /proc/version
                path: proc/version

        will create a file in the archive with the name
        `commands/proc/version` which will contain the `/proc/version`
        file. A shortened entry of:

                cmd: /usr/bin/uptime

        will create a file `commands/usr_bin_uptime`.

database

:   This elements contains the filename of the state database.

maxsize

:   This element denotes the maximum size of files to be backed up.

The order of precedence for include/exclude is:

-   bakonf will start scanning all items defined with 'include'.
-   if at any point in the file system scan, the current file matches
    any one of `noscan` regexps, the scan will ignore it. For
    directories, it will prevent recursion into them, which means
    ignoring all the files they contain, so please be careful about
    it.

Using these, you can select where you want bakonf to look for files for
archiving. The default config file includes `/etc`, `/usr/etc`,
`/usr/local/etc` and some others (look in `/etc/bakonf` after
installing).

Example main configuration file (the file included in the
distribution):

~~~{.yaml}
database: /var/lib/bakonf/state.db
configs:
- /etc/bakonf/sources/*.yaml
include:
- /etc
- /usr/etc
- /usr/local/etc
- /var/lib/alternatives
exclude:
- /etc/ssl/private
~~~

Example configuration file for saving system information:

~~~{.yaml}
commands:
- cmd: lsblk
- cmd: sfdisk -d /dev/sda
  path: partitions/sda
- cmd: dpkg -l
  path: dpkg.list
~~~

### File list

bakonf is composed of:

`/etc/bakonf/bakonf.yml`

:   Main configuration file.

`/etc/bakonf/conf.d/*.yml`

:   Configuration files for special cases (config files outside of etc
    dirs).

`/usr/bin/bakonf`

:   Main program

`/etc/cron.d/bakonf`

:   Cron file, by default it does not run bakonf, you must un-comment a
    line to run it.

`/var/lib/bakonf/archives`

:   Default directory for configuration file archives.

**Note:** You must decide yourself what to do with the configuration archives
after bakonf creates them!

## Using bakonf

### Backup phase

For details about the actual parameters to bakonf, see the man page.

To use bakonf, choose to either:

-   run it manually, when you want, either always with `-L0` or with a
    combination of multiple backup levels
-   use the provided cron script to run it automatically

In any case, you have to do something with the generated archives. Write
the to tape, CD, other machine, but don't just ignore them, you defeat
the purpose of bakonf.

### Restore phase

#### Configuration rollback

In this case, just make sure you have the bakonf-generated archive near
the date in the past you are interested in. If so:

1. if your system uses packages/ports, compare the actual package list
with the one recorded by bakonf when it created the archive

1.  install/remove software as needed

1. copy the configuration files for the services you want to rollback
over the current files

#### Complete system restoration

If you had a catastrophic system failure, you should follow these steps:

1.  Reinstall the operating system on a clean machine. Use the given
    information in the `/commands` directory in the archive to achieve
    an as close as possible configuration as the old system (e.g.
    partition layout, packages installed, etc.)
1.  Copy all the files in the archive in the file system, overwriting the
    defaults from the packages.

## Glossary

statefile

:   The database that is used for saving file states for the multi-level
    backup method
