Version 0.7.0
-------------

*Sun, 24 Nov 2019*

Require Python 3.5+. Python 2 has been sunset, and removing
compatibility with it allows code simplification.

New features:

- allow selection of archive format (-F/--format)

Bugs fixed:

- actually show skipped files in debug mode; this was the intent all
  along, but was not done due to a logic bug;

Version 0.6.0
-------------

Many changes in this major release:

- compatibility with Python 3.x
- hopefully even better Unicode compatibility
- format of the configuration file has changed, in order to simplify it
- the meta data information stored in the archive (e.g. the top-level
  README file) has changed
- the layout of the archive has changed (the path of command output)
- the output of the program has changed (switched to the logging
  module), and the verbosity level can be changed

Due to the Python 3.x compatibility, the required libraries have been
changed:

- for Python 2.4, the ElementTree library is needed
- for Python 3.0 and higher, the pybsddb library is needed

Version 0.5.3
-------------

Fixed compatibility with python 2.5/2.6 - we were (needlessly) using an
internal function in the tarfile module which changed its return type.

Also don't store the user and group names in the virtualsdb, but always
the IDs; this should give a speed-up for certain setups.
