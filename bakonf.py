#!/usr/bin/python
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
files which have been modified since installation (determined, for
now, only for RPM-based systems) and creates a file list suitable to
be used with tar or star. Then it proceeds in creating that archive,
including in it the modified configuration file and some other
metadata (like installed packages, etc.)

"""

__version__ = "$Revision: 1.7 $"
PKG_VERSION = "0.5"
# $Source: /alte/cvsroot/bakonf/bakonf.py,v $

from __future__ import generators
from optik import OptionParser
import rpm, md5, sha, stat, os, sys, pwd, grp, types, glob, re
import time, errno, StringIO, xml.dom.minidom, commands
import tarfile

def enumerate(collection):
    'Generates an indexed series:  (0,coll[0]), (1,coll[1]) ...'     
    i = 0
    it = iter(collection)
    while 1:
        yield (i, it.next())
        i += 1


class ConfigurationError(Exception):
    """Exception for invalid configuration files."""
    def __init__(self, filename, error):
        Exception.__init__()
        self.filename = filename
        self.error = error
        
    def __str__(self):
        return "ConfigurationError in file '%s': %s" % (self.filename, self.error)

    
class FileState(object):
    """Represents the state of a file.

    An instance of this class represents the state of a file, either
    sinteticaly given (with values from a previously-generated
    database) or with values read from the filesystem. If the
    attributes are not given, they will be read from filesystem at
    init time, and the checksums computed at the time of the first
    compare.

    """
    __slots__ = ('name', 'mode', 'user', 'group', 'size', 'mtime', 'lnkdest', 'virtual', 'force', 'uid', 'gid', '_md5', '_sha')
    
    def __init__(self, name, mode=None, user=None, group=None,
                 size=None, mtime=None, md5=None, sha=None,
                 lnkdest=None):
        """Initialize the members of this instance.
        
        If any of the values given is none, the state will be read
        from disk. Otherwise, the state will be filled with the values
        given.
        
        """
        self.name = name
        if mode is not None and user is not None and group is not None and \
               size is not None and mtime is not None and md5 is not None and \
               sha is not None and lnkdest is not None:
            # This means a fully specified virtual file
            self.mode = mode
            self.user = user
            self.group = group
            self.size = size
            self.mtime = mtime
            self._md5 = md5
            self._sha = sha
            self.lnkdest = lnkdest
            self.virtual = 1
            self.force = 0
        else:
            # This means a physical file
            self._readdisk()
            

    def _readdisk(self):
        """Read the state from disk.

        Updates the members with values from disk (os.lstat).  For all
        types, read mode, uid, gid, size, mtime.  For symbolic links,
        also read the link target.

        """
        self.force = 0
        try:
            self.virtual = 0
            self._md5 = None
            self._sha = None
            arr = os.lstat(self.name)
            self.mode = arr.st_mode
            self.uid = arr.st_uid
            self.gid = arr.st_gid
            self.size = arr.st_size
            self.mtime = arr.st_mtime
            if stat.S_ISLNK(self.mode):
                self.lnkdest = os.readlink(self.name)
            else:
                self.lnkdest = ""
        except OSError:
            self.force = 1
        except IOError:
            self.force = 1
        if not self.force:
            try:
                self.user = pwd.getpwuid(self.uid)[0]
            except KeyError:
                self.user = self.uid
            try:
                self.group = grp.getgrgid(self.gid)[0]
            except KeyError:
                self.group = self.gid
                
    def _readhashes(self):
        """Compute the hashes of the file's contents."""
        
        if not self.force and stat.S_ISREG(self.mode):
            try:
                md5hash = md5.new()
                shahash = sha.new()
                fh = file(self.name, "r")
                r = fh.read(65535)
                while r != "":
                    md5hash.update(r)
                    shahash.update(r)
                    r = fh.read(65535)
                fh.close()
                self._md5 = md5hash.hexdigest()
                self._sha = shahash.hexdigest()
            except IOError:
                self._md5 = ""
                self._sha = ""
        else:
            self._md5 = ""
            self._sha = ""
            
    def __eq__(self, other):
        """Compare this entry with another one, usually for the same file.

        In case of symbolic links, return equal if destination,
        permissions and user/group are the same.  In case of regular
        files, return equal if md5 are the same.  Other cases are not
        yet implemented, and return false.

        """
        if type(self) != type(other):
            return NotImplemented
        if self.virtual == other.virtual:
            raise "Comparison of two files of the same kind (virtual or non-virtual)!"
        if self.force or other.force:
            return 0
        if stat.S_ISLNK(self.mode) and stat.S_ISLNK(other.mode):
            # Both files are symlinks
            return self.lnkdest == other.lnkdest and self.user == other.user and self.group == other.group
        elif stat.S_ISREG(self.mode) and stat.S_ISREG(other.mode):
            # Both files are regular files
            # I hope here python optimizes in cases where the sizes differ,
            # and doesn't read the md5 in case it is not needed :)
            return self.size == other.size and self.md5 == other.md5 #and self.sha == other.sha
        else:
            return 0
        return 0

    def __ne__(self, other):
        """Reflexive function for __eq__."""
        return not self == other
    
    def __str__(self):
        """Return a stringified version of self, usefull for debugging."""
        ret = """<FileState instance for %s file '%s'""" % (self.virtual and "virtual" or "physical", self.name)
        if self.force:
            ret += ", unreadable -> will be selected>"
        else:
            ret += ", size: %u, u/g: %s/%s, md5: %s, sha: %s, mtime: %u>" % (self.size, self.user, self.group, self.md5, self.sha, self.mtime)
        return ret

    def getmd5(self):
        """Getter function for the MD5 hash.

        This function looks to see if we already computed the hash,
        and in that case just return it. Otherwise, compute it now and
        return it.

        """
        if self._md5 is None:
            if not self.virtual and not self.force and stat.S_ISREG(self.mode):
                self._readhashes()
                return self._md5
            else:
                return ""
        else:
            return self._md5

    def getsha(self):
        """Getter function for the SHA hash.

        This function looks to see if we already computed the hash,
        and in that case just return it. Otherwise, compute it now and
        return it.

        """
        if self._sha is None:
            if not self.virtual and not self.force and stat.S_ISREG(self.mode):
                self._readhashes()
                return self._sha
            else:
                return ""
        else:
            return self._sha

    md5 = property(fget=getmd5, doc="The MD5 hash of the file's contents")
    sha = property(fget=getsha, doc="The SHA hash of the file's contents")

        
class SubjectFile(object):
    def __init__(self, fi):
        """Constructor for the SubjectFile.
        
        Passed either a tuple of (name, size, mode, mtime, symlink
        destination, user, group, md5) for normal cases or a tuple of
        (name) if the file hasn't been found, in which case it will
        always be backed up.

        """
        if len(fi) == 1:
            self.force = 1
            self.name = fi[0]
            self.virtualstate = None
            self.physicalstate = FileState(self.name)
        else:
            (self.name, virtsize, virtmode, virtmtime, virtlnkdest, virtuser, virtgroup, virtmd5) = fi
            self.virtualstate = FileState(self.name, md5 = virtmd5, user = virtuser, group = virtgroup, size = virtsize, lnkdest = virtlnkdest, mode = virtmode, mtime = virtmtime, sha = "")
            self.physicalstate = FileState(self.name)
            self.force = 0
        
    def __str__(self):
        """Nice string version of self"""
        return "<SubjectFile instance, virtual %s, physical %s>" % (self.virtualstate, self.physicalstate)

    def needsbackup(self):
        """Checks whether this file needs backup."""
        return self.force or self.virtualstate != self.physicalstate

class FileManager(object):
    """Class which deals with overall issues of selecting files
    for backup."""
    def __init__(self, scanlist, excludelist):
        """Constructor for class BackupManager."""
        self.ts = rpm.TransactionSet()
        self.scanlist = scanlist
        self.excludelist = map(re.compile, excludelist)
        self.errorlist = []
        
    def _findfile(self, name):
        """Locate a file's entry in the package database.

        Locate the file's entry and returns a SubjectFile with these
        values. If the file is not found, it will return a SubjectFile
        which will be always selected for backup.

        """
        
        match = self.ts.dbMatch(rpm.RPMTAG_BASENAMES, name)
        if match.count() == 0:
            return SubjectFile((name,))
        else:
            hdr = match.next()
            for index, hdr_filename in enumerate(hdr[rpm.RPMTAG_FILENAMES]):
                if hdr_filename == name:
                    sfile = SubjectFile((hdr_filename, hdr[rpm.RPMTAG_FILESIZES][index],
                                         hdr[rpm.RPMTAG_FILEMODES][index], hdr[rpm.RPMTAG_FILEMTIMES][index],
                                         hdr[rpm.RPMTAG_FILELINKTOS][index], hdr[rpm.RPMTAG_FILEUSERNAME][index],
                                         hdr[rpm.RPMTAG_FILEGROUPNAME][index], hdr[rpm.RPMTAG_FILEMD5S][index]))
                    return sfile
        return SubjectFile((name,))

    def _helper(self, filelist, dirname, names):
        """Helper for the scandir method.

        This function scans a directory's entries and processes the
        non-dir elements found in it.
        
        """
        for basename in names:
            fullpath = os.path.join(dirname, basename)
            if self._isexcluded(fullpath):
                continue
            try:
                statres = os.lstat(fullpath)
            except OSError, e:
                self.errorlist.append((fullpath, e.strerror))
                print >>sys.stderr, "Cannot stat file %s, reason: '%s'. Will not be archived." % (fullpath, e.strerror)
            else:
                if not stat.S_ISDIR(statres.st_mode):
                    a = self._findfile(fullpath)
                    if a.needsbackup():
                        filelist.append(fullpath)
                    
    def _scandir(self, path):
        """Gather the files needing backup under a directory.

        Arguments:
        path - the directory which should be recusrively descended.

        """
        mylist = []
        os.path.walk(path, self._helper, mylist)
        return mylist

    def _scanfile(self, path):
        """Examine a file for inclusion in the backup."""
        if self._isexcluded(path):
            return []
        sf = self._findfile(path)
        if sf.needsbackup():
            return [sf.name]
        else:
            return []
        
    def _isexcluded(self, path):
        """Check to see if a path must be excluded."""
        for mo in self.excludelist:
            if mo.match(path) is not None:
                return 1
        return 0

    def _checksources(self):
        """Examine the list of sources and process them."""
        biglist = []
        for item in self.scanlist:
            if self._isexcluded(item):
                continue
            st = os.lstat(item)
            if stat.S_ISDIR(st.st_mode):
                biglist.extend(self._scandir(item))
            else:
                biglist.extend(self._scanfile(item))
        self.filelist = biglist

    def _addparents(self, item, list):
        """Extract the parents of a certain file/directory.

        This function extracts the parents of an item and puts them in
        proper order in the given list, so that tar gets the file list
        sorted properly.

        """
        base = os.path.dirname(item)
        if base == "/":
            return
        self._addparents(base, list)
        if not base in list:
            list.append(base)
    
    def _makelist(self):
        """Creates the full list of items to be put in the archive."""
        pathlist = []
        for path in self.filelist:
            self._addparents(path, pathlist)
        for path in self.filelist:
            pathlist.append(path)
        self.memberlist = pathlist
        
    def run(self):
        """Run the selection process."""
        self._checksources()
        self._makelist()

    def writepkglist(self, fhandle):
        """Write the rpm package list in the fhandle fileobject."""
        lst = []
        mi = self.ts.dbMatch()
        hdr = mi.next()
        while hdr is not None:
            lst.append(hdr.sprintf("%{NAME}-%{VERSION}-%{RELEASE} %{ARCH} %{SIGMD5}"))
            hdr = mi.next()
        lst.sort()
        for line in lst:
            fhandle.write("%s\n" % line)

class MetaOutput(object):
    """Denoted a meta-information to be stored in an archive.

    This class represents the element storeoutput in the configuration
    file. It will store the output of a command in the archive.

    """
    def __init__(self, command, destination):
        """Constructor for the MetaOutput class."""
        self.command = command
        self.destination = destination
        if self.destination.startswith("/"):
            self.destination = self.destination[1:]
        self.errors = None

    def store(self, archive):
        """Store the output of my command in the archive."""
        nret = 1
        (status, output) = commands.getstatusoutput(self.command)
        if not os.WIFEXITED(status) or not os.WEXITSTATUS(status) == 0:
            if os.WIFEXITED(status):
                err = "exited with status %i" % os.WEXITSTATUS(status)
            elif os.WIFSIGNALED(status):
                err = "was killed with signal %i" % os.WTERMSIG(status)
            elif os.WIFSTOPPED(status):
                err = "was stopped with signal %i" % os.WSTOPSIG(status)
            else:
                err = "unknown status code %i" % status
            self.errors = (self.command, err)
            nret = 0
            print >>sys.stderr, "Warning: command '%s' %s. Output is still stored in the archive" % (self.command, err)
        fhandle = StringIO.StringIO()
        fhandle.write(output)
        ti = genfakefile(fhandle, name=os.path.join("meta", self.destination))
        archive.addfile(ti, fhandle)
        return nret
        
class BackupManager(object):
    """Main class for this program.

    Class which deals with top-level issues regarding archiving:
    creation of the archive, parsing of configuration files, storing
    meta-informations, etc.

    """
    def __init__(self, options):
        """Constructor for BackupManager."""
        self.options = options
        self._parseconf(options.configfile)

    def _getdoms(cls, dom):
        """Helper for the _parseconf.

        This function scans the given DOM for top-level elements with
        tagName equal to 'include' and adds to the to-be-parsed list
        the files matching shell-patern of the path attribute.

        """
        if dom.firstChild.tagName != "bakonf":
            dom.unlink()
            return []

        domlist = [dom]
        cfgs = [glob.glob(incl.getAttribute("path")) for incl in
                dom.firstChild.getElementsByTagName("include")]
        paths = reduce(lambda x,y: x+y, cfgs, [])
        for fname in paths:
            childdom = xml.dom.minidom.parse(fname)
            if childdom.firstChild.tagName != "bakonf":
                childdom.unlink()
                continue
            domlist.append(childdom)
        return domlist

    _getdoms = classmethod(_getdoms)

    def _parseconf(self, filename):
        """Parse the configuration file."""
        self.fs_include = []
        self.fs_exclude = []
        self.meta_outputs = []
        
        masterdom = xml.dom.minidom.parse(filename)

        if masterdom.firstChild.tagName != "bakonf":
            raise ConfigurationError(filename, "XML file root is not bakonf")

        doms = BackupManager._getdoms(masterdom)

        for de in doms:
            for fses in de.firstChild.getElementsByTagName("filesystem"):
                for scans in fses.getElementsByTagName("scan"):
                    path = scans.getAttribute("path")
                    #print "Will scan %s=%s" % (path, glob.glob(path))
                    self.fs_include += map(os.path.abspath, glob.glob(path))
                for regexcl in fses.getElementsByTagName("noscan"):
                    #print "Will exclude %s" % regexcl.getAttribute("regex")
                    self.fs_exclude.append(regexcl.getAttribute("regex"))

            for metas in de.firstChild.getElementsByTagName("meta"):
                for cmdouts in metas.getElementsByTagName("storeoutput"):
                    #print "Will store the output of %s in file %s" % (cmdouts.getAttribute("command"), cmdouts.getAttribute("destination"))
                    self.meta_outputs.append(MetaOutput(cmdouts.getAttribute("command"), cmdouts.getAttribute("destination")))

            de.unlink()

    def _addfilesys(self, archive):
        """Add the selected files to the archive.

        This function adds the files which need to be backed up to the
        archive. If any file cannot be opened, it will be listed in
        /unarchived_files.lst.

        """
        verbose = self.options.verbose
        if verbose:
            stime = time.time()
            print "Scanning files..."
        fm = FileManager(self.fs_include, self.fs_exclude)
        fm.run()
        errorlist = list(fm.errorlist)
        fs_list = fm.memberlist
        if verbose:
            ntime = time.time()
            print "Done scanning, in %.2f seconds" % (ntime - stime)
            print "Archiving files..."
        archive.add(name="/", arcname="filesystem/", recursive=0)
        for path in fs_list:
            if path.startswith("/"):
                arcx = os.path.join("filesystem", path[1:])
            else:
                arcx = os.path.join("filesystem", path)
            try:
                archive.add(name=path, arcname=arcx, recursive=0)
            except IOError, e:
                errorlist.append((path, e.strerror))
                print >>sys.stderr, "Cannot read file %s, error: '%s'. Will not be archived." % (path, e.strerror)
        if verbose:
            ptime = time.time()
            print "Done archiving files, in %.2f seconds." % (ptime - ntime)
        sio = StringIO.StringIO()
        for (filename, error) in errorlist:
            sio.write("'%s'\t'%s'\n" % (filename, error))
        fh = genfakefile(sio, name="unarchived_files.lst")
        archive.addfile(fh, sio)

    def _addmetas(self, archive):
        """Add the metainformations to the archive.

        This functions adds the configured metainformations to the
        archive. If any command exits with status non-zero, or other
        error is encountered, its output will still be listed in the
        archive, but the command and its status will be listed in
        /commands_with_error.lst file.

        """
        errorlist = []
        for meta in self.meta_outputs:
            if not meta.store(archive):
                errorlist.append(meta.errors)
        sio = StringIO.StringIO()
        for (cmd, error) in errorlist:
            sio.write("'%s'\t'%s'\n" % (cmd, error))
        fh = genfakefile(sio, name="commands_with_errors.lst")
        archive.addfile(fh, sio)
        
            
    def run(self):
        """Create the archive.

        This method creates the archive with the given options from
        the command line and the configuration file.
        
        """
        final_tar = os.path.join(self.options.destdir, "%s.tar" % options.archive_id)
        if options.compression == 1:
            tarmode = "w:gz"
            final_tar += ".gz"
        elif options.compression == 2:
            tarmode = "w:bz2"
            final_tar += ".bz2"
        else:
            tarmode = "w"
        if options.file is not None:
            final_tar = os.path.abspath(options.file)
        tarh = tarfile.open(name=final_tar, mode=tarmode)
        tarh.posix = 0 # Need to work around 100 char filename length

        my_hostname = os.uname()[1]
        signature = """Archive generated by bakonf ver. %s - www.nongnu.org/bakonf\nHost: %s\nDate: %s\nOptions:""" % (PKG_VERSION, my_hostname, time.strftime("%F %T%z"))

        # Archiving files
        if options.do_files:
            signature += " do_filesystem"
            self._addfilesys(tarh)

        # Add metainformations
        if options.do_metas:
            signature += " do_metainformations"
            self._addmetas(tarh)

        signature += "\n"
        # Add readme stuff
        if options.verbose:
            print signature,
        sio = StringIO.StringIO(signature)
        fh = genfakefile(sio, "README")
        tarh.addfile(fh, sio)
        
        # Done with the archive
        tarh.close()

        if options.verbose:
            statres = os.stat(final_tar)
            print "Archive generated at '%s', size %i." % (final_tar, statres.st_size)
        

def genfakefile(sio=None, name = None, user='root', group='root', mtime=None):
    """Generate a fake TarInfo object from a StringIO object."""
    ti = tarfile.TarInfo()
    ti.name = name
    ti.uname = user
    ti.gname = group
    ti.mtime = mtime or time.time()
    ti.chksum = tarfile.calc_chksum(sio.getvalue())
    sio.seek(0, 2)
    ti.size = sio.tell()
    sio.seek(0, 0)
    return ti

if __name__ == "__main__":
    os.umask(0077)
    my_hostname = os.uname()[1]
    archive_id = "%s-%s" % (my_hostname, time.strftime("%F"))
    def_file = "%s.tar" % archive_id
    config_file = "/etc/bakonf/bakonf.xml"
    op = OptionParser(version="%%prog %s\nWritten by Iustin Pop\n\nCopyright (C) 2002 Iustin Pop\nThis is free software; see the source for copying conditions.  There is NO\nwarranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE." % PKG_VERSION, usage="""usage: %prog [options]

See the manpage for more informations. Defaults are:
  - archives will be named hostname-YYYY-MM-DD.tar
  - archives will be stored under /var/lib/bakonf/archives
  """)
    op.add_option("-c", "--config-file", dest="configfile",
                  help="configuration FILE [%s]" % config_file,
                  metavar="FILE", default=config_file)
    op.add_option("-f", "--file", dest="file",
                  help="name of the ARCHIVE to be generated",
                  metavar="ARCHIVE", default=None)
    op.add_option("-d", "--dir", dest="destdir",
                  help="DIRECTORY where to store the archive",
                  metavar="DIRECTORY", default="/var/lib/bakonf/archives")
    op.add_option("-g", "--gzip", dest="compression",
                   help="enable compression with gzip",
                   action="store_const", const=1, default=0)
    op.add_option("-b", "--bzip2", dest="compression",
                   help="enable compression with bzip2",
                   action="store_const", const=2)
    op.add_option("", "--no-filesystem", dest="do_files",
                  help="don't backup files",
                  action="store_false", default=1)
    op.add_option("", "--no-metas", dest="do_metas",
                  help="don't backup meta-informations",
                  action="store_false", default=1)
    op.add_option("-v", "--verbose", dest="verbose", action="store_true",
                  help="be verbose in operation", default=0)
    (options, args) = op.parse_args()
    options.archive_id = archive_id

    if not options.do_files and not options.do_metas:
        print >>sys.stderr, "Error: nothing to backup!"
        sys.exit(1)

    bm = BackupManager(options)
    bm.run()
