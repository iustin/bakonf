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

__version__ = "$Revision: 1.2 $"
# $Source: /alte/cvsroot/bakonf/bakonf.py,v $

from __future__ import generators
from optik import OptionParser
import rpm, md5, stat, os, sys, pwd, grp, types, glob, shlex, re, time

def enumerate(collection):
    'Generates an indexed series:  (0,coll[0]), (1,coll[1]) ...'     
    i = 0
    it = iter(collection)
    while 1:
        yield (i, it.next())
        i += 1


class GlobLex(shlex.shlex):
    def sourcehook(self, newfile):
        if newfile[0] == '"':
            newfile = newfile[1:-1]
        flist = glob.glob(newfile)
        for filename in flist:
            self.push_source(file(filename, "r"), filename)
        return None

class FileState(object):
    """Represents the state of a file.

    An instance of this class represents the state of a file, either
    sinteticaly given (with values from package database) or with
    values read from the filesystem. If the attributes are not given,
    they will be lazy-read from the filesystem at the time of the
    first compare.

    """
    #__slots__ = ('name', 'mode', 'user', 'group', 'size', 'mtime', 'lnkdest', '__md5')
    
    def __init__(self, name, mode=None, user=None, group=None,
                 size=None, mtime=None, md5=None, lnkdest=None):
        """Initialize the members of this instance.
        
        If any of the values given is none, the state will be read
        from disk. Otherwise, the state will be filled with the values
        given.
        
        """
        self.name = name
        if mode is not None and user is not None and group is not None and \
               size is not None and mtime is not None and md5 is not None and \
               lnkdest is not None:
            # This means a fully specified virtual file
            self.mode = mode
            self.user = user
            self.group = group
            self.size = size
            self.mtime = mtime
            self.__md5 = md5
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
            self.__md5 = None
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
                
    def _readmd5(self):
        """Compute the md5 hash of the file's contents."""
        if not self.force and stat.S_ISREG(self.mode):
            try:
                hash = md5.new()
                fh = file(self.name, "r")
                r = fh.read(65535)
                while r != "":
                    hash.update(r)
                    r = fh.read(65535)
                fh.close()
                self.__md5 = hash.hexdigest()
            except IOError:
                self.__md5 = ""
        else:
            self.__md5 = ""
            
    def __eq__(self, other):
        """Compare this entry with another one, usually for the same file.

        In case of symbolic links, return equal if destination,
        permissions and user/group are the same.  In case of regular
        files, return equal if md5 are the same.  Other cases are not
        yet implemented, and return false.

        """
        if type(self) != type(other):
            return NotImplemented
        if self.force or other.force:
            return 0
        if stat.S_ISLNK(self.mode) and stat.S_ISLNK(other.mode):
            # Both files are symlinks
            return self.lnkdest == other.lnkdest and self.user == other.user and self.group == other.group
        elif stat.S_ISREG(self.mode) and stat.S_ISREG(other.mode):
            # Both files are regular files
            # I hope here python optimizes in cases where the sizes differ,
            # and doesn't read the md5 in case it is not needed :)
            return self.size == other.size and self.md5 == other.md5
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
            ret += ", u/g: %s/%s, md5: %s, mtime: %u>" % (self.user, self.group, self.md5, self.mtime)
        return ret

    def getmd5(self):
        """Getter function for the MD5 hash.

        This function looks to see if we already computed the hash,
        and in that case just return it. Otherwise, compute it now and
        return it.

        """
        if self.__md5 is None:
            if not self.virtual and not self.force and stat.S_ISREG(self.mode):
                self._readmd5()
                return self.__md5
            else:
                return ""
        else:
            return self.__md5

    md5 = property(fget=getmd5, doc="The MD5 hash of the file's contents")

        
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
            self.virtualstate = self.physicalstate = None
        else:
            (self.name, virtsize, virtmode, virtmtime, virtlnkdest, virtuser, virtgroup, virtmd5) = fi
            self.virtualstate = FileState(self.name, md5 = virtmd5, user = virtuser, group = virtgroup, size = virtsize, lnkdest = virtlnkdest, mode = virtmode, mtime = virtmtime)
            self.physicalstate = FileState(self.name)
            self.force = 0
        
    def __str__(self):
        """Nice string version of self"""
        return "<SubjectFile instance, virtual %s, physical %s>" % (self.virtualstate, self.physicalstate)

    def needsbackup(self):
        """Checks whether this file needs backup."""
        return self.force or self.virtualstate != self.physicalstate

class BackupManager(object):
    """Class which deals with overall issues of selecting files
    for backup."""
    def __init__(self, configfile="/etc/bakonf/bakonf.cfg", filename
                 = "filenames.lst", separator="\n"):
        """Constructor for class BackupManager."""
        self.ts = rpm.TransactionSet()
        self.configfile = configfile
        self.filename = filename
        self.separator = separator
        
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
        """Helper for the scandir method."""
        for basename in names:
            fullpath = os.path.join(dirname, basename)
            if self._isexcluded(fullpath):
                continue
            if not stat.S_ISDIR(os.stat(fullpath).st_mode):
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
        for item in self.srclist:
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
    
    def _writelist(self):
        """Writes a list of filenames to the configured
        output file."""
        fh = file(self.filename, "w")
        pathlist = []
        for path in self.filelist:
            self._addparents(path, pathlist)
        for path in pathlist:
            fh.write("%s%s" % (path, self.separator))
        for path in self.filelist:
            fh.write("%s%s" % (path, self.separator))
        fh.close()
        
    def _parsecfg(self):
        """Parses the configuration files, reading the list of sources to use."""
        
        lst = []
        excl = []
        g = GlobLex(file(self.configfile, 'r'), self.configfile)
        #g.debug=1
        g.wordchars += "*./_-+=^$"
        g.source = "include"
        token = g.get_token()
        while token != '':
            if token == "sysitem":
                lst.extend(glob.glob(g.get_token()))
            elif token == "excludeitem":
                excl.append(re.compile(g.get_token()))
            else:
                print "Unknown token %s!" % token
            token = g.get_token()
        self.srclist = lst
        self.excludelist = excl

    def run(self):
        """Do the thing."""
        self._parsecfg()
        self._checksources()
        self._writelist()
        
if __name__ == "__main__":
    def_file = "%s-%s.tar" % (os.uname()[1], time.strftime("%F"))
    config_file = "bakonf.cfg"
    op = OptionParser(version = "0.2")
    op.add_option("-c", "--config-file", dest="configfile",
                  help="configuration FILE [%s]" % config_file,
                  metavar="FILE", default=config_file)
    op.add_option("-f", "--file", dest="file",
                  help="name of the ARCHIVE to be generated",
                  metavar="ARCHIVE", default=def_file)
    op.add_option("-d", "--dir", dest="dir",
                  help="DIRECTORY where to store the archive",
                  metavar="DIRECTORY", default="/var/lib/bakonf")
    op.add_option("-w", "--work-dir", dest="work",
                  help="DIRECTORY to use for temporary files (NOT world readable/writable!)",
                  metavar="DIRECTORY", default=".")
    op.add_option("-n", "--null", dest="separator", action="store_const",
                  const="\0", help="separate the filenames with NULL")
    op.add_option("-l", "--newline", dest="separator", action="store_const",
                  const="\n", help="separate the filenames with" \
                  "newline  [default]",
                  default="\n")
    op.add_option("-v", "--verbose", dest="verbose", action="store_true",
                  help="be verbose in operation", default=0)
    (options, args) = op.parse_args()
    bm = BackupManager(configfile=options.configfile,
                       separator=options.separator, filename = "" )
    bm.run()
