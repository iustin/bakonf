"""Tests for bakonf"""

import os
import os.path
import collections
import tarfile
import time
import pytest

import bakonf

# pylint: disable=missing-docstring
# pylint: disable=redefined-outer-name
# pylint: disable=invalid-name

FOO = "foo"
BAR = "bar"

Env = collections.namedtuple("Env", ["tmpdir", "destdir", "config", "fs"])


class Archive():
    def __init__(self, stats):
        self.tar = tarfile.open(name=stats.filename, mode="r")
        self.names = self.tar.getnames()

    @staticmethod
    def filepath(path):
        return os.path.normpath("filesystem/" + str(path))

    @staticmethod
    def cmdpath(path):
        return os.path.normpath("commands/" + str(path))

    def has_member(self, path):
        return path in self.names

    def has_file(self, path):
        return self.has_member(self.filepath(path))

    def has_cmd(self, path):
        return self.has_member(self.cmdpath(path))

    def contents(self, path):
        c = self.tar.extractfile(path)
        assert c is not None
        return bakonf.ensure_text(c.read())

    def file_data(self, path):
        return self.contents(self.filepath(path))

    def link_data(self, path):
        fp = self.filepath(path)
        ti = self.tar.getmember(fp)
        assert ti.issym()
        return ti.linkname

    def cmd_data(self, path):
        return self.contents(self.cmdpath(path))

    def fl_data(self, sym, path):
        if sym:
            return self.link_data(path)
        else:
            return self.file_data(path)


def lp_write(fa, sym, data):
    if sym:
        if os.path.lexists(str(fa)):
            fa.remove()
        fa.mksymlinkto(data)
    else:
        fa.write(data)


@pytest.fixture
def env(tmpdir):
    """Setup environment for a bakonf run"""
    destdir = tmpdir.mkdir("out")
    config = tmpdir.join("cfg")
    config.write("database: %s\n" % tmpdir.join("db"))
    fs = tmpdir.mkdir("fs")
    return Env(tmpdir, destdir, config, fs)


def buildopts(env, args=None):
    if args is None:
        args = []
    op = bakonf.build_options()
    (opts, _) = op.parse_args(args)
    opts.destdir = str(env.destdir)
    opts.configfile = str(env.config)
    return opts


def stats_cnt(stats):
    return (stats.file_count, stats.file_errors,
            stats.cmd_count, stats.cmd_errors)


def assert_empty(stats):
    assert stats_cnt(stats) == (0, 0, 0, 0)


def test_basic(env):
    opts = buildopts(env)
    bm = bakonf.BackupManager(opts)
    assert stats_cnt(bm.run()) == (0, 0, 0, 0)


def test_opts_db_has_precedence(env):
    opts = buildopts(env)
    env.config.write("database: %s\n" % env.tmpdir.join("a", "b", "db"))
    # with wrong database path, raises error
    with pytest.raises(bakonf.bsddb.db.DBNoSuchFileError):
        bm = bakonf.BackupManager(opts)
        assert stats_cnt(bm.run()) == (0, 0, 0, 0)
    # but works if overriden:
    opts.statefile = str(env.tmpdir.join("db"))
    bm = bakonf.BackupManager(opts)
    assert stats_cnt(bm.run()) == (0, 0, 0, 0)


def test_opts_override_file(env):
    opts = buildopts(env)
    opts.destdir = str(env.tmpdir.join("a", "b", "out"))
    # with wrong output path, raises error
    with pytest.raises(bakonf.Error,
                       match=r"Output directory '.*' does not exist"):
        bakonf.BackupManager(opts).run()
    # but works if overriden:
    opts.file = str(env.tmpdir.join("a.tar"))
    bm = bakonf.BackupManager(opts)
    assert stats_cnt(bm.run()) == (0, 0, 0, 0)


def test_opts_bad_dir(env):
    opts = buildopts(env)
    opts.destdir = str(env.tmpdir.join("a").ensure())
    with pytest.raises(bakonf.Error,
                       match="is not a directory"):
        bakonf.BackupManager(opts).run()


def test_opts_bad_level(env):
    opts = buildopts(env)
    opts.level = 2
    bm = bakonf.BackupManager(opts)
    with pytest.raises(ValueError, match="Unknown backup level 2"):
        bm.run()


def test_opts_compression(env):
    opts = buildopts(env)
    fnames = set()
    levels = [bakonf.COMP_NONE, bakonf.COMP_GZ, bakonf.COMP_BZ2]
    if bakonf.HAVE_LZMA:
        levels.append(bakonf.COMP_XZ)
    for level in levels:
        opts.compression = level
        stats = bakonf.BackupManager(opts).run()
        assert_empty(stats)
        assert stats.filename not in fnames
        fnames.add(stats.filename)


def test_opts_bad_compression(env):
    opts = buildopts(env)
    opts.compression = "no-such-compression"
    with pytest.raises(bakonf.Error, match="Unexpected compression mode"):
        bakonf.BackupManager(opts).run()


def test_opts_comp_xz_fail(env, monkeypatch):
    opts = buildopts(env)
    monkeypatch.setattr(bakonf, "HAVE_LZMA", False)
    opts.compression = bakonf.COMP_XZ
    with pytest.raises(bakonf.Error, match="doesn't support LZMA"):
        bakonf.BackupManager(opts).run()


def test_opts_comp_unsupported(env, monkeypatch):
    opts = buildopts(env)
    monkeypatch.setattr(bakonf, "COMP_GZ", "foobar")
    opts.compression = bakonf.COMP_GZ
    with pytest.raises(bakonf.Error, match="Unexpected compression error"):
        bakonf.BackupManager(opts).run()


@pytest.mark.parametrize("key", ["DBKEY_VERSION",
                                 "DBKEY_DATE"])
def test_bad_db_missing_key(env, monkeypatch, key):
    opts = buildopts(env)
    bakonf.BackupManager(opts).run()
    opts.level = 1
    monkeypatch.setattr(bakonf, key, "foobar")
    bm = bakonf.BackupManager(opts)
    with pytest.raises(bakonf.ConfigurationError,
                       match="Invalid database contents"):
        bm.run()


def test_bad_db_level(env, monkeypatch):
    opts = buildopts(env)
    bakonf.BackupManager(opts).run()
    opts.level = 1
    monkeypatch.setattr(bakonf, "DB_VERSION", 2)
    bm = bakonf.BackupManager(opts)
    with pytest.raises(bakonf.ConfigurationError,
                       match="Invalid database version"):
        bm.run()


def test_bad_db_old_time(env, monkeypatch, caplog):
    opts = buildopts(env)

    def old_time():
        return 0
    monkeypatch.setattr(time, "time", old_time)
    bakonf.BackupManager(opts).run()
    monkeypatch.undo()
    opts.level = 1
    caplog.clear()
    bakonf.BackupManager(opts).run()
    assert "Database is more than 8 days old" in caplog.text


def test_bad_db_deserialisation(env, monkeypatch):
    opts = buildopts(env)
    with env.config.open("a") as f:
        f.write("include: [%s]\n" % env.fs)
    fa = env.fs.join("a")
    fa.write(FOO)
    stats = bakonf.BackupManager(opts).run()
    assert Archive(stats).file_data(fa) == FOO
    opts.level = 1

    def unser(_s, _p):
        raise ValueError("mock!")
    monkeypatch.setattr(bakonf.FileState, "unserialize",
                        unser)
    bakonf.BackupManager(opts).run()
    stats = bakonf.BackupManager(opts).run()
    assert Archive(stats).file_data(fa) == FOO


def test_extra_cfg(env):
    opts = buildopts(env)
    extra_cfg = env.tmpdir.join("cfg-2")
    extra_cfg.write("commands:\n- cmd: echo\n")
    with env.config.open("a") as f:
        f.write("configs:\n - %s\n" % extra_cfg)
    bm = bakonf.BackupManager(opts)
    assert stats_cnt(bm.run()) == (0, 0, 1, 0)


@pytest.mark.parametrize("line,msg", [
    ("database: - foo\n", "Error reading file"),
    ("include:\n- null\n", "Invalid include entry"),
    ("exclude:\n- null\n", "Invalid exclude entry"),
    ("maxsize: abc\n", "Invalid maxsize"),
    ])
def test_bad_cfg(env, line, msg):
    opts = buildopts(env)
    env.config.write(line)
    with pytest.raises(bakonf.Error, match=msg):
        bakonf.BackupManager(opts)


def test_cmd(env):
    opts = buildopts(env)
    with env.config.open("a") as f:
        f.write("commands:\n")
        f.write("- cmd: echo test\n  dest: echo\n")
        f.write("- cmd: uptime\n")
    stats = bakonf.BackupManager(opts).run()
    assert stats_cnt(stats) == (0, 0, 2, 0)
    a = Archive(stats)
    assert a.has_cmd("echo")
    assert a.cmd_data("echo") == "test\n"


def test_cmd_slash(env):
    opts = buildopts(env)
    with env.config.open("a") as f:
        f.write("commands:\n")
        f.write("- cmd: echo test\n  dest: /echo\n")
    stats = bakonf.BackupManager(opts).run()
    assert stats_cnt(stats) == (0, 0, 1, 0)
    a = Archive(stats)
    assert a.has_cmd("echo")
    assert a.cmd_data("echo") == "test\n"


def test_cmd_no_commands(env):
    opts = buildopts(env)
    with env.config.open("a") as f:
        f.write("commands:\n")
        f.write("- cmd: uptime\n")
    opts.do_commands = False
    bm = bakonf.BackupManager(opts)
    assert_empty(bm.run())


def test_cmd_err(env):
    opts = buildopts(env)
    with env.config.open("a") as f:
        f.write("commands:\n")
        f.write("- cmd: exit 1\n")
    bm = bakonf.BackupManager(opts)
    assert stats_cnt(bm.run()) == (0, 0, 1, 1)


def test_cmd_signal(env):
    opts = buildopts(env)
    with env.config.open("a") as f:
        f.write("commands:\n")
        f.write("- cmd: kill $$\n")
    bm = bakonf.BackupManager(opts)
    assert stats_cnt(bm.run()) == (0, 0, 1, 1)


def test_fs_empty(env):
    opts = buildopts(env)
    with env.config.open("a") as f:
        f.write("include:\n- %s\n" % env.fs)
    bm = bakonf.BackupManager(opts)
    # no files for an empty dir
    assert_empty(bm.run())


@pytest.mark.parametrize("incfile", [True, False])
@pytest.mark.parametrize("files", [
    [("a", "abc")],
    [("a", "abc"),
     ("1", "123")],
    [("a", "abc"),
     ("1/2", "345")],
    [("a/b/c/d", "12345"),
     ("a/b/e", "ghi")],
    ])
def test_fs_simple(env, files, incfile):
    opts = buildopts(env)
    with env.config.open("a") as f:
        f.write("include:\n")
        if incfile:
            for (path, _) in files:
                f.write("- %s\n" % env.fs.join(path))
        else:
            f.write("- %s\n" % env.fs)
    for (path, contents) in files:
        env.fs.join(path).ensure().write(contents)
    stats = bakonf.BackupManager(opts).run()

    assert stats.file_count > len(files)
    a = Archive(stats)
    for (path, contents) in files:
        fp = env.fs.join(path)
        assert a.has_file(fp)
        assert a.file_data(fp) == contents


def test_fs_symlink(env):
    opts = buildopts(env)
    with env.config.open("a") as f:
        f.write("include: [%s]\n" % env.fs)
    sym = env.fs.join("a")
    dst = "foobarbaz"
    sym.mksymlinkto(dst)
    stats = bakonf.BackupManager(opts).run()
    assert stats.file_count > 1
    a = Archive(stats)
    assert a.has_file(sym)
    assert a.link_data(sym) == dst


def test_fs_include_excluded(env):
    opts = buildopts(env)
    with env.config.open("a") as f:
        f.write("include: [%s]\n" % env.fs)
        f.write("exclude: [%s]\n" % env.fs)
    env.fs.join("a").write(FOO)
    bm = bakonf.BackupManager(opts)
    # no files if parent directory is excluded
    assert_empty(bm.run())


def test_fs_dir_excluded(env):
    opts = buildopts(env)
    with env.config.open("a") as f:
        f.write("include:\n- %s\n" % env.fs)
        f.write("exclude:\n- %s\n" % env.fs.join("a"))
    env.fs.join("a/b").ensure().write(FOO)
    bm = bakonf.BackupManager(opts)
    # no files if parent directory is excluded
    assert_empty(bm.run())


def test_fs_file_excluded(env):
    opts = buildopts(env)
    with env.config.open("a") as f:
        f.write("include:\n- %s\n" % env.fs)
        f.write("exclude:\n- %s\n" % env.fs.join("a/b"))
    env.fs.join("a/b").ensure().write(FOO)
    bm = bakonf.BackupManager(opts)
    # no files if parent directory is excluded
    assert_empty(bm.run())


def test_fs_file_maxsize(env):
    opts = buildopts(env)
    with env.config.open("a") as f:
        f.write("maxsize: 1\n")
        f.write("include:\n- %s\n" % env.fs)
    env.fs.join("a").ensure().write("abc")
    bm = bakonf.BackupManager(opts)
    # no files if parent directory is excluded
    assert_empty(bm.run())


def test_fs_no_files(env):
    opts = buildopts(env)
    with env.config.open("a") as f:
        f.write("include:\n- %s\n" % env.fs)
    env.fs.join("a").ensure().write(FOO)
    opts.do_files = False
    bm = bakonf.BackupManager(opts)
    # no files if parent directory is excluded
    assert_empty(bm.run())


@pytest.mark.parametrize("symlink", [True, False])
def test_fs_incremental_noop(env, symlink):
    opts = buildopts(env)
    with env.config.open("a") as f:
        f.write("include:\n- %s\n" % env.fs)
    f = env.fs.join("a")
    lp_write(f, symlink, FOO)
    stats = bakonf.BackupManager(opts).run()
    assert stats.file_count > 1
    a = Archive(stats)
    assert a.has_file(f)
    assert a.fl_data(symlink, f) == FOO
    opts.level = 1
    stats = bakonf.BackupManager(opts).run()
    assert_empty(stats)
    assert not Archive(stats).has_file(f)


@pytest.mark.parametrize("symlink", [True, False])
def test_fs_incremental_update(env, symlink):
    opts = buildopts(env)
    with env.config.open("a") as f:
        f.write("include:\n- %s\n" % env.fs)
    fa = env.fs.join("a")
    lp_write(fa, symlink, FOO)
    stats = bakonf.BackupManager(opts).run()
    assert stats.file_count > 1
    assert Archive(stats).fl_data(symlink, fa) == FOO
    opts.level = 1
    lp_write(fa, symlink, BAR)
    stats = bakonf.BackupManager(opts).run()
    assert stats.file_count > 1
    assert Archive(stats).fl_data(symlink, fa) == BAR


@pytest.mark.parametrize("from_symlink", [True, False])
def test_fs_incremental_changed_type(env, from_symlink):
    opts = buildopts(env)
    with env.config.open("a") as f:
        f.write("include:\n- %s\n" % env.fs)
    fa = env.fs.join("a")
    lp_write(fa, from_symlink, FOO)
    stats = bakonf.BackupManager(opts).run()
    assert stats.file_count > 1
    assert Archive(stats).fl_data(from_symlink, fa) == FOO
    opts.level = 1
    fa.remove()
    lp_write(fa, not from_symlink, BAR)
    stats = bakonf.BackupManager(opts).run()
    assert stats.file_count > 1
    assert Archive(stats).fl_data(not from_symlink, fa) == BAR


def test_fs_lstat_error(env, monkeypatch):
    opts = buildopts(env)
    with env.config.open("a") as f:
        f.write("include:\n- %s\n" % env.fs)
    fa = env.fs.join("a")
    fa.write(FOO)

    def lstat(path, up=os.lstat):
        if path == str(fa):
            raise OSError("Mock raise")
        return up(path)
    bm = bakonf.BackupManager(opts)
    monkeypatch.setattr(os, "lstat", lstat)
    stats = bm.run()
    assert stats.file_errors == 1
    assert not Archive(stats).has_file(fa)


def test_fs_unreadable(env, caplog):
    opts = buildopts(env)
    with env.config.open("a") as f:
        f.write("include:\n- %s\n" % env.fs)
    fa = env.fs.join("a")
    fa.write(FOO)
    fa.chmod(0)
    bm = bakonf.BackupManager(opts)
    stats = bm.run()
    assert stats.file_errors == 1
    assert not Archive(stats).has_file(fa)
    assert "Cannot read '%s'" % fa in caplog.text


def test_fs_unreadable_in_l1(env, caplog):
    opts = buildopts(env)
    with env.config.open("a") as f:
        f.write("include:\n- %s\n" % env.fs)
    fa = env.fs.join("a")
    fa.write(FOO)
    stats = bakonf.BackupManager(opts).run()
    assert stats.file_count > 1
    assert Archive(stats).has_file(fa)
    opts.level = 1
    fa.chmod(0)
    caplog.clear()
    stats = bakonf.BackupManager(opts).run()
    assert "Cannot read '%s'" % fa in caplog.text


def test_fs_readlink_error(env, monkeypatch):
    opts = buildopts(env)
    with env.config.open("a") as f:
        f.write("include:\n- %s\n" % env.fs)
    fa = env.fs.join("a")
    fa.mksymlinkto(FOO)
    state = {"r": 0}

    def readlink(path, up=os.readlink):
        if path == str(fa):
            # This is ugly, but needed to play around tarfile...
            state["r"] += 1
            if state["r"] <= 1:
                raise OSError("Mock raise: %s" % str(fa))
        return up(path)
    bm = bakonf.BackupManager(opts)
    monkeypatch.setattr(os, "readlink", readlink)
    stats = bm.run()
    assert stats.file_errors == 0
    assert stats.file_count > 0
    assert Archive(stats).link_data(fa) == FOO


def test_fs_readlink_error_l1(env, monkeypatch):
    opts = buildopts(env)
    with env.config.open("a") as f:
        f.write("include:\n- %s\n" % env.fs)
    fa = env.fs.join("a")
    fa.mksymlinkto(FOO)
    bm = bakonf.BackupManager(opts)
    stats = bm.run()
    assert stats.file_errors == 0
    assert stats.file_count > 0
    assert Archive(stats).link_data(fa) == FOO

    state = {"r": 0}

    def readlink(path, up=os.readlink):
        if path == str(fa):
            # This is ugly, but needed to play around tarfile...
            state["r"] += 1
            if state["r"] <= 1:
                raise OSError("Mock raise: %s" % str(fa))
        return up(path)
    opts.level = 1
    bm = bakonf.BackupManager(opts)
    monkeypatch.setattr(os, "readlink", readlink)
    stats = bm.run()
    # force backed up, although unchanged, and still the same link target.
    assert stats.file_errors == 0
    assert stats.file_count > 0
    assert Archive(stats).link_data(fa) == FOO


def test_fs_duplicate_includes(env):
    opts = buildopts(env)
    with env.config.open("a") as f:
        f.write("include:\n- %s\n" % env.fs)
    fd = env.fs.join("a")
    fa = fd.join("b").ensure()
    fa.write(FOO)
    s1 = bakonf.BackupManager(opts).run()
    with env.config.open("a") as f:
        f.write("- %s\n" % fd)
    s2 = bakonf.BackupManager(opts).run()
    assert s1 == s2


def test_fs_relative_includes(env, monkeypatch):
    opts = buildopts(env)
    with env.config.open("a") as f:
        f.write("include: [fs]\n")
    monkeypatch.chdir(env.tmpdir)
    fd = env.tmpdir.join("fs", "a")
    fa = fd.join("b").ensure()
    fa.write(BAR)
    stats = bakonf.BackupManager(opts).run()
    assert stats.file_count > 0
    assert Archive(stats).file_data(fa) == BAR


def test_fs_cant_write(env):
    opts = buildopts(env)
    env.destdir.chmod(0o555)
    with pytest.raises(bakonf.Error,
                       match="Can't create archive"):
        bakonf.BackupManager(opts).run()
