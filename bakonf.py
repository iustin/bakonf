#!/usr/bin/python3
#
# Copyright (C) 2002, 2004, 2008, 2009, 2010, 2014 Iustin Pop
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

"""Configuration backup program.

This program backs up the configuration files in a GNU/Linux or other
Unix-like system. It does this by examining a list of directories for
files which have been modified since the last time it has run and
creates a tar archive with them. Output of custom commands can also be
included in the generated archive.

"""

import sys
import stat
import os
import glob
import re
import time
import subprocess
import tarfile
import logging
import argparse
import collections
from io import BytesIO
import hashlib

import yaml
import bsddb3

_COPY = ("Written by Iustin Pop\n\n"
         "Copyright (C) 2002, 2004, 2008, 2009, 2010 Iustin Pop\n"
         "This is free software; see the source for copying conditions."
         " There is NO\n"
         "warranty; not even for MERCHANTABILITY or FITNESS"
         " FOR A PARTICULAR PURPOSE.")
PKG_VERSION = "0.6.0"
DB_VERSION = "1"
ENCODING = "utf-8"

# constants
DEFAULT_VPATH = "/var/lib/bakonf/statefile.db"
DEFAULT_ODIR = "/var/lib/bakonf/archives"
CMD_PREFIX = "commands"
ROOT_TAG = "bakonf"
DBKEY_VERSION = "bakonf:db_version"
DBKEY_DATE = "bakonf:db_date"
COMP_NONE = ""
COMP_GZ = "gz"
COMP_BZ2 = "bz2"
COMP_XZ = "xz"

FORMATS = {
    "ustar": tarfile.USTAR_FORMAT,
    "gnu": tarfile.GNU_FORMAT,
    "pax": tarfile.PAX_FORMAT,
}

HAVE_LZMA = sys.hexversion >= 0x03030000


Stats = collections.namedtuple(
    "Stats", "filename file_count file_errors cmd_count cmd_errors")


def ensure_text(val):
    """Ensure a string/bytes/unicode object is a 'text' object."""
    if isinstance(val, bytes):
        # this is an encoded (bytes) value, need to decode
        val = val.decode(ENCODING)
    return val


def ensure_bytes(val):
    """Ensure a string/bytes/unicode object is a 'bytes' object."""
    if isinstance(val, str):
        # this is a decoded (text) value, need to encode
        val = val.encode(ENCODING)
    return val


def genfakefile(sio=None, name=None, user='root', group='root', mtime=None):
    """Generate a fake TarInfo object from a BytesIO object."""
    ti = tarfile.TarInfo()
    ti.name = name
    ti.uname = user
    ti.gname = group
    ti.mtime = mtime or time.time()
    sio.seek(0, 2)
    ti.size = sio.tell()
    sio.seek(0, 0)
    return ti


def storefakefile(archive, contents, name):
    """Stores a string as a fake file in the archive."""

    sio = BytesIO(ensure_bytes(contents))
    ff = genfakefile(sio, name=name)
    archive.addfile(ff, sio)


class Error(Exception):
    """Basic exception type."""
    def __init__(self, error):
        Exception.__init__(self)
        self.error = error

    def __str__(self):
        return str(self.error)


class ConfigurationError(Error):
    """Exception for invalid configuration files."""
    def __init__(self, filename, error):
        Error.__init__(self, error)
        self.filename = filename

    def __str__(self):
        return "in file '%s': %s" % (self.filename, self.error)


class FileState():
    """Represents the state of a file.

    An instance of this class represents the state of a file, either
    sinteticaly given (with values from a previously-generated
    database) or with values read from the filesystem. If the
    attributes are not given, they will be read from filesystem at
    init time, and the checksums computed at the time of the first
    compare.

    """
    __slots__ = ('name', 'mode', 'user', 'group', 'size', 'mtime',
                 'lnkdest', 'virtual', 'force', '_md5', '_sha')

    def __init__(self, **kwargs):
        """Initialize the members of this instance.

        Either the filename or the serialdata must be given, as
        keyword arguments. If the filename is given, create a
        FileState representing a physical file. If the serialdata is
        given, create a virtual file with values unserialized from the
        given data.

        """
        if len(kwargs) != 1:  # pragma: no cover
            raise ValueError("Invalid invocation of constructor "
                             "- give either filename or serialdata")
        if 'filename' not in kwargs and \
           'serialdata' not in kwargs:  # pragma: no cover
            raise ValueError("Invalid invocation of constructor "
                             "- give either filename or serialdata")
        self.force = None
        self.virtual = None
        self._md5 = None
        self._sha = None
        self.mode = None
        self.size = None
        self.mtime = None
        self.lnkdest = None
        self.user = None
        self.group = None

        if 'filename' in kwargs:
            # This means a physical file
            self.name = kwargs['filename']
            self._readdisk()
        else:
            self.unserialize(kwargs['serialdata'])

    def _readdisk(self):
        """Read the state from disk.

        Updates the members with values from disk (os.lstat).  For all
        types, read mode, uid, gid, size, mtime.  For symbolic links,
        also read the link target.

        """
        self.force = False
        self.virtual = False
        self._md5 = None
        self._sha = None
        try:
            arr = os.lstat(self.name)
            self.mode = arr.st_mode
            self.user = arr.st_uid
            self.group = arr.st_gid
            self.size = arr.st_size
            self.mtime = arr.st_mtime
            if stat.S_ISLNK(self.mode):
                self.lnkdest = os.readlink(self.name)
            else:
                self.lnkdest = ""
        except (OSError, IOError) as err:
            logging.error("Cannot stat '%s', will force backup: %s",
                          self.name, err)
            self.force = True

    def _readhashes(self):
        """Compute the hashes of the file's contents."""

        if self.virtual or self.force or not stat.S_ISREG(self.mode):
            self._md5 = ""
            self._sha = ""
        else:
            try:
                md5hash = hashlib.md5()
                shahash = hashlib.sha1()
                with open(self.name, "rb") as fh:
                    data = fh.read(65535)
                    while data:
                        md5hash.update(data)
                        shahash.update(data)
                        data = fh.read(65535)
                self._md5 = md5hash.hexdigest()
                self._sha = shahash.hexdigest()
            except IOError:
                self._md5 = ""
                self._sha = ""

    def __eq__(self, other):
        """Compare this entry with another one, usually for the same file.

        In case of symbolic links, return equal if destination,
        permissions and user/group are the same.  In case of regular
        files, return equal if md5 are the same.  Other cases are not
        yet implemented, and return false.

        """
        if type(self) != type(other):  # pragma: no cover pylint: disable=C0123
            return NotImplemented
        assert self.virtual != other.virtual, \
            "Comparison of two files of the same kind (%u)!" % self.virtual
        if self.force or other.force:
            return False
        if stat.S_ISLNK(self.mode) and stat.S_ISLNK(other.mode):
            # Both files are symlinks
            return self.lnkdest == other.lnkdest and \
                   self.user == other.user and \
                   self.group == other.group and \
                   stat.S_IMODE(self.mode) == stat.S_IMODE(other.mode)
        elif stat.S_ISREG(self.mode) and stat.S_ISREG(other.mode):
            # Both files are regular files
            # I hope here python optimizes in cases where the sizes differ,
            # and doesn't compute the hashes in case it is not needed :)
            return self.size == other.size and \
                   self.md5 == other.md5 and \
                   self.sha == other.sha
        else:
            return False

    def __ne__(self, other):
        """Reflexive function for __eq__."""
        return not self == other

    def __str__(self):  # pragma: no cover (only debug)
        """Return a stringified version of self, useful for debugging."""
        ret = ("""<FileState instance for %s file '%s'""" %
               (self.virtual and "virtual" or "physical", self.name))
        if self.force:
            ret += ", unreadable -> will be selected>"
        else:
            ret += (", size: %u, u/g: %s/%s, md5: %s, sha: %s, mtime: %u>" %
                    (self.size, self.user, self.group, self.md5,
                     self.sha, self.mtime))
        return ret

    def _gethash(self, kind):
        """Return a cached hash or force compute it."""
        val = getattr(self, kind)
        if val is None:
            self._readhashes()
            return getattr(self, kind)
        else:
            return val

    @property
    def md5(self):
        """The MD5 hash of the file's contents."""
        return self._gethash('_md5')

    @property
    def sha(self):
        """The SHA hash of the file's contents."""
        return self._gethash('_sha')

    def serialize(self):
        """Encode the file state as a string"""

        out = ""
        out += "%s\0" % self.name
        out += "%i\0" % self.mode
        out += "%s\0" % self.user
        out += "%s\0" % self.group
        out += "%i\0" % self.size
        out += "%i\0" % self.mtime
        out += "%s\0" % self.lnkdest
        out += "%s\0" % self.md5
        out += "%s" % self.sha

        return out

    def unserialize(self, text):
        """Decode the file state from a string"""
        # If the following raises ValueError, the parent must! catch it
        (name, mode, user, group, size, mtime, lnkdest, md5sum, shasum) \
            = text.split('\0')
        mode = int(mode)
        size = int(size)
        mtime = int(mtime)
        if len(md5sum) not in (0, 32) or \
           len(shasum) not in (0, 40):  # pragma: no cover
            raise ValueError("Invalid hash length!")
        # Here we should have all the data needed
        self.virtual = True
        self.force = False
        self.name = name
        self.mode = mode
        self.user = int(user)
        self.group = int(group)
        self.size = size
        self.mtime = mtime
        self.lnkdest = lnkdest
        self._md5 = md5sum
        self._sha = shasum


class SubjectFile():
    """A file to be backed up"""

    __slots__ = ('_backup', 'name', 'virtual', 'physical')

    def __init__(self, name, virtualdata=None):
        """Constructor for the SubjectFile.

        Creates a physical member based on the given filename. If
        virtualdata is also given, create a virtual member based on
        that data; otherwise, the file will always be selected for
        backup.

        """
        self.name = name
        self.physical = FileState(filename=name)
        if virtualdata is not None:
            try:
                self.virtual = FileState(serialdata=virtualdata)
            except ValueError as err:
                logging.error("Unable to de-serialise the file '%s': %s",
                              name, err)
                self._backup = True
                self.virtual = None
            else:
                self._backup = self.virtual != self.physical
        else:
            self._backup = True
            self.virtual = None

    def __str__(self):  # pragma: no cover (only debug)
        """Nice string version of self"""
        return ("<SubjectFile instance, virtual %s, physical %s>" %
                (self.virtual, self.physical))

    @property
    def needsbackup(self):
        """Checks whether this file needs backup."""
        return self._backup

    def serialize(self):
        """Returns a serialized state of this file."""

        return self.physical.serialize()


class FileManager():
    """Class which deals with overall issues of selecting files
    for backup.

    An instance is created by giving it the desired options (see the
    constructor). Afterwards, the checksources() method will create
    the filelist.

    Other data members are subjects, which holds associations between
    filenames and the SubjectFile instances, useful for later updating
    the database, and errorlist, which contains tuples (filename,
    error string) with files which could not be backed up. The list
    scanned is a list which contains already-processed names, so that
    we don't double-add to the archive.

    """
    __slots__ = ('scanlist', 'excludelist', 'errorlist', 'statedb',
                 'backuplevel', 'subjects', 'scanned',
                 'filelist', 'memberlist', 'maxsize')

    def __init__(self, scanlist, excludelist, statefile, backuplevel,
                 maxsize):
        """Constructor for class FileManager."""
        self.scanlist = scanlist
        self.excludelist = list(map(re.compile, excludelist))
        statefile = os.path.abspath(statefile)
        self.excludelist.append(re.compile("^%s$" % statefile))
        self.maxsize = maxsize
        self.errorlist = []
        self.filelist = []
        self.subjects = {}
        self.scanned = []
        if backuplevel == 0:
            mode = "n"
        elif backuplevel == 1:
            mode = "r"
        else:
            raise ValueError("Unknown backup level %u" % backuplevel)
        self.backuplevel = backuplevel
        self.statedb = bsddb3.hashopen(statefile, mode)
        if backuplevel == 0:
            self._dbput(DBKEY_VERSION, DB_VERSION)
            self._dbput(DBKEY_DATE, str(time.time()))
        else:
            for check in (DBKEY_VERSION, DBKEY_DATE):
                if not self._dbhas(check):
                    raise ConfigurationError(statefile,
                                             "Invalid database contents!")
            currvers = self._dbget(DBKEY_VERSION)
            if currvers != DB_VERSION:
                raise ConfigurationError(statefile,
                                         "Invalid database version '%s'" %
                                         currvers)
            dbtime = float(self._dbget(DBKEY_DATE))
            if time.time() - dbtime > 8 * 86400:
                logging.warning("Database is more than 8 days old!")

    def _dbput(self, key, value):
        """Add/replace an entry in the virtuals database.

        This is just small wrapper that abstracts this operations, so
        in case we need to change the implementation there is only one
        point of change.

        """
        key = key.encode(ENCODING)
        self.statedb[key] = value.encode(ENCODING)

    def _dbget(self, key):
        """Get and entry from the virtuals database.

        This is just small wrapper that abstracts this operations, so
        in case we need to change the implementation there is only one
        point of change.

        """
        key = key.encode(ENCODING)
        if key in self.statedb:
            value = self.statedb[key].decode(ENCODING)
        else:
            value = None
        return value

    def _dbhas(self, key):
        """Check if we have an entry in the virtuals database.

        This is just small wrapper that abstracts this operations, so
        in case we need to change the implementation there is only one
        point of change.

        """
        key = key.encode(ENCODING)
        return key in self.statedb

    def _findfile(self, name):
        """Locate a file's entry in the virtuals database.

        Locate the file's entry and returns a SubjectFile with these
        values. If the file is not found, it will return a SubjectFile
        which will be always selected for backup.

        """

        key = "file:/%s" % (name,)
        virtualdata = self._dbget(key)
        return SubjectFile(name, virtualdata)

    def _ehandler(self, err):
        """Error handler for directory walk.

        """
        self.errorlist.append((err.filename, err.strerror))
        logging.error("Not archiving '%s', cannot stat: '%s'.",
                      err.filename, err.strerror)

    def _helper(self, dirname, names):
        """Helper for the scandir method.

        This function scans a directory's entries and processes the
        non-dir elements found in it.

        """
        self.scanned.append(dirname)
        for basename in names:
            fullpath = os.path.join(dirname, basename)
            if self._isexcluded(fullpath):
                logging.debug("Skipping excluded path '%s'", fullpath)
                continue
            try:
                statres = os.lstat(fullpath)
            except OSError as err:
                self._ehandler(err)
            else:
                if stat.S_ISDIR(statres.st_mode):  # pragma: no cover
                    logging.error("Directory passed to _helper")
                else:
                    self._scanfile(fullpath)

    def _scandir(self, path):
        """Gather the files needing backup under a directory.

        Arguments:
        path - the directory which should be recusrively descended.

        """
        for dpath, dnames, fnames in os.walk(path, onerror=self._ehandler):
            for subdir in list(dnames):
                fullpath = os.path.join(dpath, subdir)
                if self._isexcluded(fullpath):
                    logging.debug("Skipping recursion in "
                                  "excluded directory '%s'",
                                  fullpath)
                    dnames.remove(subdir)
            self._helper(dpath, fnames)

    def _scanfile(self, path):
        """Examine a file for inclusion in the backup."""
        if path in self.scanned:  # pragma: no cover
            logging.error("Already scanned path passed to _scanfile: %s",
                          path)
            return []
        if self._isexcluded(path):  # pragma: no cover
            logging.error("Excluded path passed to _scanfile: %s", path)
            return []
        self.scanned.append(path)
        logging.debug("Examining path %s", path)
        sf = self._findfile(path)
        if (self.maxsize > 0 and sf.physical.size and
                sf.physical.size > self.maxsize):
            logging.warning("Skipping path %s due to size limit (%s > %s)",
                            path, sf.physical.size, self.maxsize)
            return []
        elif sf.needsbackup:
            logging.debug("Selecting path %s", path)
            self.subjects[sf.name] = sf
            FileManager.addparents(path, self.filelist)
            return [sf.name]
        else:
            logging.debug("No backup needed for %s", path)
            return []

    def _isexcluded(self, path):
        """Check to see if a path must be excluded."""
        for mo in self.excludelist:
            if mo.match(path) is not None:
                return True
        return False

    def checksources(self):
        """Examine the list of sources and process them."""
        for item in self.scanlist:
            if self._isexcluded(item) or item in self.scanned:
                logging.debug("Ignoring excluded or duplicated "
                              "top-level item %s", item)
                continue
            st = os.lstat(item)
            if stat.S_ISDIR(st.st_mode):
                self._scandir(item)
            else:
                self._scanfile(item)

    @staticmethod
    def addparents(item, item_lst):
        """Smartly insert a filename into a list.

        This function extracts the parents of an item and puts them in
        proper order in the given list, so that tar gets the file list
        sorted properly. Then it adds the given filename.

        """
        base = os.path.dirname(item)
        if base == "/":
            return
        FileManager.addparents(base, item_lst)
        if base not in item_lst:
            item_lst.append(base)
        if item not in item_lst:
            item_lst.append(item)

    def notifywritten(self, path):
        """Notify that a file has been archived.

        This method is called by the BackupManager when the archive
        containing a file has been successfuly written to disk and
        closed. In turn, we update the file's entry in the virtuals
        database with the checksums written.

        """
        # If a file hasn't been found (as it is with directories), the
        # worst case is that we ignore that we backed up that file.
        if self.backuplevel == 0 and path in self.subjects:
            self._dbput("file:/%s" % (path,), self.subjects[path].serialize())

    def close(self):
        """Ensure database has been written to disc."""

        self.statedb.close()


class CmdOutput():
    """Denotes a command result to be stored in an archive.

    This class represents the element storeoutput in the configuration
    file. It will store the output of a command in the archive.

    """
    __slots__ = ('command', 'destination', 'errors')

    def __init__(self, command, destination):
        """Constructor for the CmdOutput class."""
        self.command = command
        if destination is None:
            destination = self._sanitize_name(command)
        self.destination = destination
        if self.destination.startswith("/"):
            self.destination = self.destination[1:]
        self.errors = None

    @staticmethod
    def _sanitize_name(path):
        """Makes sure path can be used as a plain filename.

        This just replaces slashes with underscores.

        """
        path = path.replace(os.path.sep, "_")
        if os.path.altsep is not None:  # pragma: no cover
            path = path.replace(os.path.altsep, "_")
        return path

    def store(self, archive):
        """Store the output of my command in the archive."""
        logging.debug("Executing command %s, storing output as %s",
                      self.command, self.destination)
        success = True
        child = subprocess.Popen(self.command, shell=True,
                                 stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT,
                                 cwd="/")
        child.stdin.close()
        output = child.stdout.read()
        status = child.wait()
        if status != 0:
            if status > 0:
                err = "exited with status %i" % status
            else:
                err = "was killed with signal %i" % (-status, )
            self.errors = (self.command, err)
            success = False
            logging.warning("'%s' %s.", self.command, err)
        name = os.path.join(CMD_PREFIX, self.destination)
        storefakefile(archive, output, name)
        return success


class BackupManager():
    """Main class for this program.

    Class which deals with top-level issues regarding archiving:
    creation of the archive, parsing of configuration files, storing
    command output, etc.

    """
    def __init__(self, options):
        """Constructor for BackupManager."""
        self.options = options
        self.fs_include = []
        self.fs_exclude = []
        self.fs_maxsize = -1
        self.cmd_outputs = []
        self.fs_statefile = None
        self.fs_donelist = []
        self.fs_manager = None
        self._cur_cfgfile = None
        self._parseconf(options.configfile)

    def _check_val(self, val, msg):
        """Checks that a given value is well-formed.

        Right now this is just not empty (None).

        """
        if val is None:
            raise ConfigurationError(self._cur_cfgfile, "%s: %r" % (msg, val))

    def _get_extra_sources(self, mainfile, maincfg):
        """Helper for the _parseconf.

        This function scans the given config for a 'configs' mapping
        and returns the loaded objects for the files matching
        shell-pattern of the path attribute (including the given
        configuration).

        """
        elist = [(mainfile, maincfg)]
        for incl in maincfg.get("configs", []):
            self._check_val(incl, "Invalid configs entry")
            logging.debug("Expanding configuration pattern '%s'", incl)
            for fname in glob.glob(incl):
                logging.debug("Reading extra config file '%s'", fname)
                with open(fname) as stream:
                    subcfg = yaml.safe_load(stream)
                elist.append((fname, subcfg))
        return elist

    def _parseconf(self, filename):
        """Parse the configuration file."""

        logging.debug("Opening configuration file '%s'", filename)
        try:
            with open(filename) as stream:
                config = yaml.safe_load(stream)
        except Exception as err:
            raise ConfigurationError(filename,
                                     "Error reading file: %s" % str(err))

        self._cur_cfgfile = filename
        if self.options.statefile is None:
            vpath = config.get("database", None)
            if vpath is None:
                self.fs_statefile = DEFAULT_VPATH
            else:
                self.fs_statefile = vpath
        else:
            self.fs_statefile = self.options.statefile

        msize = config.get("maxsize", None)
        if msize is not None:
            try:
                self.fs_maxsize = int(msize)
            except (ValueError, TypeError) as err:
                raise ConfigurationError(filename, "Invalid maxsize"
                                         " value: %s" % err)
        tlist = self._get_extra_sources(filename, config)

        # process scanning targets
        for cfile, conft in tlist:
            self._cur_cfgfile = cfile
            logging.debug("Processing config file '%s'", cfile)
            # process file system include paths
            for scan_path in conft.get("include", []):
                self._check_val(scan_path, "Invalid include entry")
                paths = [os.path.abspath(i) for i in glob.glob(scan_path)]
                self.fs_include += [ensure_text(i) for i in paths]

            # process file system exclude paths
            for noscan_path in conft.get("exclude", []):
                self._check_val(noscan_path, "Invalid exclude entry")
                self.fs_exclude.append(ensure_text(noscan_path))

            # command output
            commands = conft.get("commands", [])
            for entry in commands:
                cmd_line = ensure_text(entry.get("cmd", None))
                cmd_dest = ensure_text(entry.get("dest", None))
                self._check_val(cmd_line, "Invalid 'cmd' key")
                self.cmd_outputs.append(CmdOutput(cmd_line, cmd_dest))

    def _addfilesys(self, archive):
        """Add the selected files to the archive.

        This function adds the files which need to be backed up to the
        archive. If any file cannot be opened, it will be listed in
        /unarchived_files.lst.

        """
        stime = time.time()
        logging.info("Scanning files...")
        self.fs_manager = fm = FileManager(self.fs_include, self.fs_exclude,
                                           self.fs_statefile,
                                           self.options.level, self.fs_maxsize)
        fm.checksources()
        errorlist = list(fm.errorlist)
        fs_list = fm.filelist
        ntime = time.time()
        logging.info("Done scanning, %.4f seconds, %d files",
                     ntime - stime, len(fs_list))
        logging.info("Archiving files...")
        donelist = self.fs_donelist
        archive.add(name="/", arcname="filesystem/", recursive=0)
        for path in fs_list:
            arcx = os.path.join("filesystem", path.lstrip("/"))
            try:
                if not hasattr(archive, "encoding"):  # pragma: no cover
                    # older tarfile library
                    arcx = arcx.encode(ENCODING)
                archive.add(name=path,
                            arcname=arcx,
                            recursive=0)
            except IOError as err:
                errorlist.append((path, err.strerror))
                logging.error("Cannot read '%s': '%s'. Not archived.",
                              path, err.strerror)
            else:  # Successful archiving of the member
                donelist.append(path)
        ptime = time.time()
        logging.info("Done archiving files, %.4f seconds.", ptime - ntime)

        contents = ["'%s'\t'%s'" % v for v in errorlist]
        storefakefile(archive, "\n".join(contents), "unarchived_files.lst")
        return (len(donelist), len(errorlist))

    def _addcommands(self, archive):
        """Add the command outputs to the archive.

        This functions adds the configured command outputs to the
        archive. If any command exits with status non-zero, or other
        error is encountered, its output will still be listed in the
        archive, but the command and its status will be listed in
        /commands_with_error.lst file.

        """
        errorlist = []
        for cmd in self.cmd_outputs:
            if not cmd.store(archive):
                errorlist.append(cmd.errors)

        contents = ["'%s'\t'%s'\n" % v for v in errorlist]
        storefakefile(archive, "\n".join(contents), "commands_with_errors.lst")
        return (len(self.cmd_outputs), len(errorlist))

    def _addsignature(self, archive):
        """Add a signature to the archive.

        This adds a README file to the archive containing the
        signature for the current bakonf run.

        """
        ropts = []
        if self.options.do_files:
            ropts.append("do_filesystem")
        if self.options.do_commands:
            ropts.append("do_command_output")
        my_hostname = os.uname()[1]
        signature = [
            "Creator: bakonf %s - http://www.nongnu.org/bakonf" % PKG_VERSION,
            "Host: %s" % my_hostname,
            "Date: %s" % time.strftime("%F %T%z"),
            "Options: %s" % " ".join(ropts),
            "Level: %d" % self.options.level,
            ]

        signature = "\n".join(signature) + "\n"

        logging.info(signature)

        storefakefile(archive, signature, "README")
        storefakefile(archive, my_hostname, "host")
        storefakefile(archive, PKG_VERSION, "version")

    def run(self):
        """Create the archive.

        This method creates the archive with the given options from
        the command line and the configuration file.

        """
        opts = self.options
        final_tar = os.path.join(opts.destdir, "%s-L%u.tar" %
                                 (opts.archive_id, opts.level))
        compr = opts.compression
        if compr == COMP_XZ and not HAVE_LZMA:
            raise Error("Your Python version doesn't support LZMA compression")

        if compr == COMP_NONE:
            tarmode = "w"
        elif compr in [COMP_GZ, COMP_BZ2, COMP_XZ]:
            tarmode = "w:" + compr
            final_tar += "." + compr
        else:
            raise Error("Unexpected compression mode found, "
                        "please report this!")
        if opts.file is not None:
            # overrides the entire path, including any extension added above
            final_tar = os.path.abspath(opts.file)
        final_dir = os.path.dirname(final_tar)
        if not os.path.exists(final_dir):
            raise Error("Output directory '%s' does not exist" % final_dir)
        if not os.path.isdir(final_dir):
            raise Error("Output directory '%s' is not a directory" % final_dir)

        if opts.format:
            if opts.format not in FORMATS:
                raise Error("Unexpected format '{}'?!".format(opts.format))
            tar_format = FORMATS[opts.format]
        else:
            tar_format = tarfile.DEFAULT_FORMAT
        try:
            tarh = tarfile.open(name=final_tar, mode=tarmode,
                                format=tar_format)
        except EnvironmentError as err:
            raise Error("Can't create archive '%s': %s" % (final_tar, err))
        except tarfile.CompressionError as err:
            raise Error("Unexpected compression error: %s" % str(err))

        # Archiving files
        if opts.do_files:
            (f_stored, f_skipped) = self._addfilesys(tarh)
        else:
            f_stored = f_skipped = 0

        # Add command output
        if opts.do_commands:
            (c_stored, c_skipped) = self._addcommands(tarh)
        else:
            c_stored = c_skipped = 0

        # Add readme stuff
        self._addsignature(tarh)

        # Done with the archive
        tarh.close()

        statres = os.stat(final_tar)
        logging.info("Archive generated at '%s', size %i.",
                     final_tar, statres.st_size)

        # Now update the database with the files which have been stored
        if opts.do_files:
            for path in self.fs_donelist:
                self.fs_manager.notifywritten(path)
            # Close the db now
            self.fs_manager.close()
        return Stats(final_tar, f_stored, f_skipped, c_stored, c_skipped)


def build_options():
    """Builds the options structure"""

    my_hostname = os.uname()[1]
    archive_id = "%s-%s" % (my_hostname, time.strftime("%F"))
    config_file = "/etc/bakonf/bakonf.yml"
    usage = ("""\
Simple backup tool for small (e.g. configuration) files and program
output (e.g. sfdisk -d /dev/sda).

Program can be run either in "always back up everything" (don't pass
-L) or in a simple incremental backup (combined -L0 and -L1 usage).

See the manpage for more information. Defaults are:
  - uncompressed archives (override by -g/-b/-x)
  - archives will be named hostname-YYYY-MM-DD-L$level.tar
  - archives will be stored under {}\n""".format(DEFAULT_ODIR))
    op = argparse.ArgumentParser(
        prog="bakonf",
        description=usage,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    op.set_defaults(verbose=1)
    op.add_argument("--version", action="version",
                    version="%%(prog)s v%s" % (PKG_VERSION, ))
    op.add_argument("-v", "--verbose", dest="verbose", action="count",
                    help="be verbose in operation")
    op.add_argument("-q", "--quiet", dest="verbose", action="store_const",
                    help="set verbosity to zero", const=0)

    gen = op.add_argument_group(title="General configuration")
    gen.add_argument("-c", "--config-file", dest="configfile",
                     help="configuration file (defaut: %(default)s)",
                     metavar="FILE", default=config_file)
    gen.add_argument("-S", "--statefile", dest="statefile",
                     help="location of the state file (overrides config file)",
                     metavar="FILE", default=None)

    out = op.add_argument_group(title="Archive creation/output")
    out.add_argument("-f", "--file", dest="file",
                     help="name of the archive file to be generated "
                     "(default: '{}-L$level.tar')".format(archive_id),
                     metavar="ARCHIVE", default=None)
    out.add_argument("-d", "--dir", dest="destdir",
                     help="the directory where to store the archive "
                     "(default: %(default)s)",
                     metavar="DIRECTORY", default=DEFAULT_ODIR)
    out.add_argument("-L", "--level", dest="level",
                     help="specify the level of the backup: 0, 1 "
                     "(default: %(default)s)",
                     metavar="LEVEL", default=0, type=int)
    out.add_argument("-F", "--format", dest="format",
                     help="specify the archive format (default: gnu)",
                     choices=FORMATS.keys())
    out.add_argument("--archive-id", dest="archive_id",
                     help="informational identifier to store in "
                     "the generated archive (default: '%(default)s')",
                     default=archive_id)

    comp = op.add_argument_group(title="Compression options").\
        add_mutually_exclusive_group()
    comp.add_argument("-g", "--gzip", dest="compression",
                      help="enable compression with gzip",
                      action="store_const", const=COMP_GZ, default=COMP_NONE)
    comp.add_argument("-b", "--bzip2", dest="compression",
                      help="enable compression with bzip2",
                      action="store_const", const=COMP_BZ2)
    comp.add_argument("-x", "--xz", dest="compression",
                      help="enable compression with xz (lzma)",
                      action="store_const", const=COMP_XZ)

    noact = op.add_argument_group(title="Skipping actions")
    noact.add_argument("--no-filesystem", dest="do_files",
                       help="skip files backup",
                       action="store_false", default=True)
    noact.add_argument("--no-commands", dest="do_commands",
                       help="skip command execution and the storing "
                       "of their results",
                       action="store_false", default=True)
    return op


def real_main():  # pragma: no cover
    """Main function"""

    os.umask(0o077)
    op = build_options()
    options = op.parse_args()
    if options.verbose >= 2:
        lvl = logging.DEBUG
    elif options.verbose == 1:
        lvl = logging.INFO
    else:
        lvl = logging.WARNING
    logging.basicConfig(level=lvl, format="%(levelname)s: %(message)s")

    if not options.do_files and not options.do_commands:
        raise Error("Nothing to backup!")

    if options.level is None:
        raise Error(("You must give the backup level, either 0 or 1."))

    if options.level not in (0, 1):
        raise Error("Invalid backup level %u, must be 0 or 1." %
                    options.level)

    bm = BackupManager(options)
    bm.run()


def main():  # pragma: no cover
    """Wrapper over real_main()."""
    try:
        real_main()
    except Error as err:
        msg = str(err)
        punctuation = "." if msg and msg[-1] not in "?!." else ""
        logging.error("%s%s", msg, punctuation)
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
