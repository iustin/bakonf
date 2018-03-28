# bakonf

bakonf is a trivial tool designed to make backups of the configuration
files of a GNU/Linux or Unix-like system. Its aim is to use various
methods in order to reduce the size of the backup to a reasonable
minimum, in order to be useful for remote/unattended servers, while
still backing up enough to recreate the system.

The contents of the archives created contain enough information so that
the system admininistrator can restore the system to a working state.
Beside the actual information from the filesystem, it can store output
of various commands, for example:

- partition table
- various /proc information
- pci & usb device list

For more information, see the user manual in the doc directory.

Iustin Pop, <iustin@k1024.org>
