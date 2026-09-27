#!/usr/bin/python3 -I
"""Account Bootstrap: the one root process of a Construct.

Resolves the Node Daemon's service UID and GID to the `agent` account, applies
the Construct's sudo setting, drops every privilege, publishes the identity-v2
handoff into the per-launch mounted file without replacing its inode, and execs
the wrapped command. The handoff reports identity readiness only; the runtime
observes workload state on its own.

The isolated absolute interpreter above is load-bearing: the image PATH leads with
directories the workload can write, so a bare `python3` on a restarted container
would run the earlier workload's program as root.
"""

from __future__ import annotations

import argparse
import ctypes
import grp
import json
import os
import pwd
import re
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ACCOUNT = "agent"
ACCOUNT_TOOLS = ("useradd", "usermod", "groupadd", "groupmod")
REFUSED_GROUPS = ("root", "sudo", "docker")
SUDO_GRANT = Path("/etc/sudoers.d") / ACCOUNT
TOOLS_PATH = "/usr/sbin:/usr/bin:/sbin:/bin"
HOME_PARENT = "/home"
MOUNTINFO = "/proc/self/mountinfo"
MAX_INPUT = 16384
PR_SET_KEEPCAPS = 8
PR_SET_NO_NEW_PRIVS = 38
PR_GET_NO_NEW_PRIVS = 39
PR_CAP_AMBIENT = 47
PR_CAP_AMBIENT_CLEAR_ALL = 4


class BootstrapError(ValueError):
    pass


def absolute_path(value):
    if (
        not isinstance(value, str)
        or not value.startswith("/")
        or value == "/"
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
        or any(part in ("", ".", "..") for part in value.split("/")[1:])
    ):
        raise BootstrapError("expected a non-root absolute path")
    return value


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BootstrapError("duplicate identity field")
        result[key] = value
    return result


@dataclass(frozen=True)
class Identity:
    launch_id: str
    uid: int
    gid: int
    sudo: bool
    home: str
    shell: str

    @classmethod
    def parse(cls, raw):
        try:
            value = json.loads(raw, object_pairs_hook=unique_pairs)
        except (ValueError, UnicodeError) as error:
            raise BootstrapError("invalid identity JSON") from error
        if not isinstance(value, dict) or set(value) != {
            "version",
            "launch_id",
            "uid",
            "gid",
            "sudo",
            "home",
            "shell",
        }:
            raise BootstrapError("invalid identity fields")
        # The identity input stays at version 1 under identity-v2; only the handoff is version 2.
        if type(value["version"]) is not int or value["version"] != 1:
            raise BootstrapError("unsupported identity version")
        if not isinstance(value["launch_id"], str) or not re.fullmatch(
            r"[A-Za-z0-9_.-]{1,128}", value["launch_id"]
        ):
            raise BootstrapError("invalid launch identity")
        if any(
            type(value[key]) is not int or not 1 <= value[key] <= 2147483647
            for key in ("uid", "gid")
        ):
            raise BootstrapError("ordinary identity must be non-root")
        if type(value["sudo"]) is not bool:
            raise BootstrapError("sudo must be boolean")
        return cls(
            value["launch_id"],
            value["uid"],
            value["gid"],
            value["sudo"],
            absolute_path(value["home"]),
            absolute_path(value["shell"]),
        )


def read_identity(path):
    fd = os.open(absolute_path(str(path)), os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_INPUT:
            raise BootstrapError("identity input must be a bounded regular file")
        raw = stream.read(MAX_INPUT + 1)
    if len(raw) > MAX_INPUT:
        raise BootstrapError("identity input is too large")
    return Identity.parse(raw)


def prctl(option, argument=0):
    libc = ctypes.CDLL(None, use_errno=True)
    result = libc.prctl(
        ctypes.c_int(option),
        ctypes.c_ulong(argument),
        ctypes.c_ulong(0),
        ctypes.c_ulong(0),
        ctypes.c_ulong(0),
    )
    if result < 0:
        raise BootstrapError(f"identity process restriction failed ({ctypes.get_errno()})")
    return result


def tool(name, *arguments):
    executable = shutil.which(name, path=TOOLS_PATH)
    if executable is None:
        raise BootstrapError(f"required account tool unavailable: {name}")
    result = subprocess.run(
        [executable, *arguments],
        capture_output=True,
        timeout=30,
        check=False,
        env={"PATH": TOOLS_PATH, "LANG": "C"},
    )
    if result.returncode:
        raise BootstrapError(f"account tool failed: {name}")


def require_tools(identity):
    needed = ACCOUNT_TOOLS + (("sudo",) if identity.sudo else ())
    missing = sorted(name for name in needed if shutil.which(name, path=TOOLS_PATH) is None)
    if missing:
        raise BootstrapError("missing account tools: " + ", ".join(missing))


def lookup(getter, key):
    try:
        return getter(key)
    except KeyError:
        return None


def mount_points():
    points = set()
    for line in Path(MOUNTINFO).read_text().splitlines():
        fields = line.split()
        if len(fields) > 4:
            points.add(re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), fields[4]))
    return points


def own_unmounted_home(identity):
    """Give an image-owned home to the service identity; mounted contents keep their owners."""
    mounted = mount_points()
    info = os.stat(identity.home)
    if identity.home in mounted or (info.st_uid, info.st_gid) == (identity.uid, identity.gid):
        return
    os.lchown(identity.home, identity.uid, identity.gid)
    for directory, names, files in os.walk(identity.home):
        names[:] = [name for name in names if os.path.join(directory, name) not in mounted]
        for name in names + files:
            path = os.path.join(directory, name)
            info = os.lstat(path)
            # A hard link may name a file outside the home; a directory cannot be one.
            if path not in mounted and (stat.S_ISDIR(info.st_mode) or info.st_nlink == 1):
                os.lchown(path, identity.uid, identity.gid)


def provision_account(identity):
    require_tools(identity)
    if os.path.dirname(identity.home) != HOME_PARENT:
        raise BootstrapError(f"home must be a directory directly under {HOME_PARENT}")
    if not os.path.isfile(identity.shell) or not os.access(identity.shell, os.X_OK):
        raise BootstrapError("configured login shell is unavailable")
    holders = [user for user in pwd.getpwall() if user.pw_uid == identity.uid]
    if len(holders) > 1:
        raise BootstrapError("ambiguous existing UID")
    if holders and holders[0].pw_name != ACCOUNT:
        raise BootstrapError(
            f"service UID belongs to a non-{ACCOUNT} account: {holders[0].pw_name}"
        )
    group = lookup(grp.getgrgid, identity.gid)
    if identity.gid == 0 or (group and group.gr_name in REFUSED_GROUPS):
        raise BootstrapError(
            f"service GID belongs to a refused group: {group.gr_name if group else 'root'}"
        )
    if group is None:
        if lookup(grp.getgrnam, ACCOUNT):
            tool("groupmod", "--gid", str(identity.gid), ACCOUNT)
        else:
            tool("groupadd", "--gid", str(identity.gid), ACCOUNT)
    account = holders[0] if holders else lookup(pwd.getpwnam, ACCOUNT)
    if account is None:
        tool(
            "useradd",
            "--uid",
            str(identity.uid),
            "--gid",
            str(identity.gid),
            "--home-dir",
            identity.home,
            "--shell",
            identity.shell,
            "--no-create-home",
            "--no-log-init",
            ACCOUNT,
        )
    else:
        # Re-read: renumbering the account's own group above already moved its primary GID.
        account = pwd.getpwnam(ACCOUNT)
        renumber = (account.pw_uid, account.pw_gid) != (identity.uid, identity.gid)
        if renumber:
            # usermod re-owns every file under the account's current home when the UID or
            # GID changes, mounted or not; a home that does not exist skips that walk.
            tool("usermod", "--home", "/nonexistent", ACCOUNT)
            tool("usermod", "--uid", str(identity.uid), "--gid", str(identity.gid), ACCOUNT)
        if renumber or (account.pw_dir, account.pw_shell) != (identity.home, identity.shell):
            tool("usermod", "--home", identity.home, "--shell", identity.shell, ACCOUNT)
    home = Path(identity.home)
    if home.is_symlink():
        raise BootstrapError("home must not be a symlink")
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not home.is_dir():
        raise BootstrapError("home must be a directory")
    own_unmounted_home(identity)
    account = lookup(pwd.getpwuid, identity.uid)
    if account is None or (
        account.pw_name,
        account.pw_gid,
        account.pw_dir,
        account.pw_shell,
    ) != (ACCOUNT, identity.gid, identity.home, identity.shell):
        raise BootstrapError("account provisioning did not establish the selected environment")
    return ACCOUNT


def provision_sudo(identity, name):
    if not identity.sudo:
        SUDO_GRANT.unlink(missing_ok=True)
        memberships = [group.gr_name for group in grp.getgrall() if name in group.gr_mem]
        if "sudo" in memberships:
            remaining = [group for group in memberships if group != "sudo"]
            tool("usermod", "--groups", ",".join(remaining), name)
        return
    if prctl(PR_GET_NO_NEW_PRIVS):
        raise BootstrapError("selected sudo is blocked by no_new_privs")
    if shutil.which("sudo", path=TOOLS_PATH) is None:
        raise BootstrapError("selected sudo requires sudo in the image")
    if SUDO_GRANT.parent.is_symlink() or not SUDO_GRANT.parent.is_dir():
        raise BootstrapError(f"selected sudo requires the directory {SUDO_GRANT.parent}")
    fd = os.open(SUDO_GRANT, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o440)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise BootstrapError("sudo grant must be a regular file")
        os.fchown(fd, 0, 0)
        os.fchmod(fd, 0o440)
        os.ftruncate(fd, 0)
        write_all(fd, f"{name} ALL=(ALL) NOPASSWD:ALL\n".encode())
        os.fsync(fd)
    finally:
        os.close(fd)


def write_all(fd, payload):
    while payload:
        payload = payload[os.write(fd, payload) :]


def clear_capabilities():
    class Header(ctypes.Structure):
        _fields_ = [("version", ctypes.c_uint32), ("pid", ctypes.c_int)]

    class Data(ctypes.Structure):
        _fields_ = [
            ("effective", ctypes.c_uint32),
            ("permitted", ctypes.c_uint32),
            ("inheritable", ctypes.c_uint32),
        ]

    header, data = Header(0x20080522, 0), (Data * 2)()
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.capset(ctypes.byref(header), ctypes.byref(data)) != 0:
        raise BootstrapError("cannot clear workload capabilities")


def drop_identity(identity):
    prctl(PR_SET_KEEPCAPS, 0)
    prctl(PR_CAP_AMBIENT, PR_CAP_AMBIENT_CLEAR_ALL)
    os.setgroups([])
    os.setgid(identity.gid)
    os.setuid(identity.uid)
    clear_capabilities()
    if not identity.sudo:
        # Apply after root provisioning; inherited image sudo grants cannot bypass this.
        prctl(PR_SET_NO_NEW_PRIVS, 1)
    if (os.getresuid(), os.getresgid(), os.getgroups()) != (
        (identity.uid,) * 3,
        (identity.gid,) * 3,
        [],
    ) or (os.getuid(), os.geteuid(), os.getgid(), os.getegid()) != (
        identity.uid,
        identity.uid,
        identity.gid,
        identity.gid,
    ):
        raise BootstrapError("identity handoff failed")


def write_handoff(path, identity):
    value = {
        "version": 2,
        "launch_id": identity.launch_id,
        "uid": os.getuid(),
        "gid": os.getgid(),
    }
    if (value["uid"], value["gid"], os.geteuid()) != (identity.uid, identity.gid, identity.uid):
        raise BootstrapError("handoff attempted before privilege drop")
    # The Node Daemon reads the inode it mounted: write in place, never replace it.
    fd = os.open(absolute_path(str(path)), os.O_WRONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise BootstrapError("handoff must be a regular mounted file")
        os.ftruncate(fd, 0)
        write_all(fd, json.dumps(value, sort_keys=True).encode() + b"\n")
        os.fsync(fd)
    finally:
        os.close(fd)


def launch(identity_input, handoff, command):
    if os.geteuid() != 0:
        raise BootstrapError("account bootstrap requires selected guest-root launch")
    if (
        not command
        or not command[0]
        or not all(isinstance(arg, str) and "\0" not in arg for arg in command)
    ):
        raise BootstrapError("an explicit workload command is required")
    identity = read_identity(identity_input)
    handoff = Path(absolute_path(str(handoff)))
    if Path(identity_input).resolve() == handoff.resolve():
        raise BootstrapError("identity input and handoff paths must differ")
    name = provision_account(identity)
    provision_sudo(identity, name)
    drop_identity(identity)
    os.environ.update(HOME=identity.home, USER=name, LOGNAME=name, SHELL=identity.shell)
    os.chdir(identity.home)
    if not os.access(identity.home, os.W_OK | os.X_OK):
        raise BootstrapError("selected home is not writable by the workload")
    write_handoff(handoff, identity)
    os.execvpe(command[0], command, os.environ)


class OneLineParser(argparse.ArgumentParser):
    def error(self, message):
        print(f"{self.prog}: {message}", file=sys.stderr)
        raise SystemExit(2)


def main(argv=None):
    parser = OneLineParser(prog="account-bootstrap")
    parser.add_argument("--identity-input", required=True)
    parser.add_argument("--handoff", required=True)
    parser.add_argument("--protocol", choices=("identity-v2",), default="identity-v2")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    try:
        launch(args.identity_input, args.handoff, command)
    except (BootstrapError, OSError, subprocess.SubprocessError) as error:
        print(f"{parser.prog}: {' '.join(str(error).split())}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
