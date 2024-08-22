# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


from __future__ import annotations


'''
NOTES:

libmount has a debug mode that can be enabled via environment variable.
Set LIBMOUNT_DEBUG=debug to get a list of debug options.
'''


##########################################################################################
# Imports
##########################################################################################

import sys

from dataclasses import dataclass
from enum import IntFlag
from functools import partial
from json import loads as jloads
from pathlib import Path
from signal import SIGINT, SIGTERM, signal, strsignal, pause as spause
from subprocess import CalledProcessError, run as prun
from time import sleep
from typing import Any

from systemd.daemon import notify as system_notify
from libmount import MS_BIND, MS_REC, MS_SLAVE, Context as MountContext
from tjtools.scripts.openvpn_netns import get_ns_identifier, is_ns_live


##########################################################################################
# Force flush when printing.
##########################################################################################

print = partial(print, flush=True)


##########################################################################################
# Constants
##########################################################################################

'''
Path to config file for the sandbox.
'''
_config_path = Path('/etc/gentoo-sandbox.conf')

'''
Number of retries when unmounting the main chroot filesystem.
'''
_num_retry = 5

_msg = 'Gentoo sandbox chroot environment'


##########################################################################################
# Enumerator definitions
##########################################################################################

class OptsMode(IntFlag):
    '''
    Some of the modes for libmount's mnt_context_set_optsmode().

    The current libmount Python bindings don't expose any enum values for optsmode.

    Ignore - Ignore fstab options (MNT_OMODE_IGNORE)
    NoTab  - Do not read fstab at all (MNT_OMODE_NOTAB)

    See libmount.h for details.
    '''

    Ignore = 1 << 1
    NoTab  = 1 << 12


##########################################################################################
# Dataclass definitions
##########################################################################################

@dataclass(frozen=True)
class SandboxConfig:
    '''
    Dataclass encoding the sandbox configuration.

    mount_point  - path to the directory where the sandbox is mounted
    bind_mounts  - list of paths that are bind-mounted into the sandbox
    rbind_mounts - list of paths that are rbind-mounted into the sandbox
    '''

    mount_point: Path
    bind_mounts: list[Path]
    rbind_mounts: list[Path]

    @staticmethod
    def is_valid_dir(path_string: Any) -> bool:
        '''
        Check for a valid path string pointing to a directory.
        '''

        return isinstance(path_string, str) and Path(path_string).is_dir()

    @staticmethod
    def is_valid_dir_list(path_list: Any) -> bool:
        '''
        Check for a valid list of path strings (each one pointing to a directory).
        '''

        if not isinstance(path_list, list):
            return False

        return all(map(SandboxConfig.is_valid_dir, path_list))

    @staticmethod
    def from_path(path: Path) -> SandboxConfig:
        '''
        Create a sandbox config from a config path.

        Arguments:
            path - path from where we read the config
        '''

        if not path.is_file():
            raise RuntimeError(f'config path is not a file: {path}')

        config_raw = path.read_text(encoding='utf-8')
        config_data = jloads(config_raw)

        for entry in ('mount-point', 'bind-mounts', 'rbind-mounts'):
            if not entry in config_data:
                raise RuntimeError(f'config entry missing: {entry}')

        mount_point = config_data['mount-point']
        if not SandboxConfig.is_valid_dir(mount_point):
            raise RuntimeError(f'invalid mount point: {mount_point}')

        bind_mounts = config_data['bind-mounts']
        if not SandboxConfig.is_valid_dir_list(bind_mounts):
            raise RuntimeError(f'invalid bind mounts: {bind_mounts}')

        rbind_mounts = config_data['rbind-mounts']
        if not SandboxConfig.is_valid_dir_list(rbind_mounts):
            raise RuntimeError(f'invalid rbind mounts: {rbind_mounts}')

        config = SandboxConfig(
            Path(mount_point),
            list(map(Path, bind_mounts)),
            list(map(Path, rbind_mounts)),
        )

        return config


##########################################################################################
# Internal functions
##########################################################################################

def _usage(app: str) -> None:
    print(f'Usage: {app}', file=sys.stdout)

    print('\t --prepare [prepare the chroot for use]', file=sys.stdout)
    print('\t --enter [enter the chroot]', file=sys.stdout)
    print('\t --cleanup [cleanup the chroot (use if prepare fails the cleanup)]', file=sys.stdout)
    print('\t Use --cleanup if --prepare fails during the cleanup step.', file=sys.stdout)

def _signal_handler(signal_no, stack_frame):
    print(f'info: received signal {strsignal(signal_no)}', file=sys.stderr)

def _dumb_mountctx() -> MountContext:
    '''
    Helper for creating a dumb mount context.
    '''

    c = MountContext()

    c.disable_helpers(1)
    c.disable_swapmatch(1)
    c.disable_mtab(1)

    c.optsmode = OptsMode.Ignore

    return c

def _mount(source: Path, target: Path, fstype: str) -> None:
    '''
    Simple mount helper.

    Arguments:
        source - path to mount source (optional)
        target - path to mount target
        fstype - filesyste type (optional)
    '''

    if target is None or not target.is_dir():
        raise RuntimeError(f'invalid target: {target}')

    c = MountContext()

    if fstype is not None:
        if fstype == 'proc' and source is None:
            c.source = 'proc'

        c.fstype = fstype

    if source is not None:
        if not source.is_dir():
            raise RuntimeError(f'invalid source: {source}')

        c.source = source.as_posix()

    c.target = target.as_posix()

    c.mount()

    print(f'info: mount finished with status: {c.status}', file=sys.stdout)

def _mbind(source: Path, target: Path, recursive: bool) -> None:
    '''
    Bind and recursive-bind mount helper.

    Arguments:
        source    - path to mount source
        target    - path to mount target
        recursive - should we bind-mount recursively?
    '''

    if target is None or not target.is_dir():
        raise RuntimeError(f'invalid target: {target}')

    if source is None or not source.is_dir():
        raise RuntimeError(f'invalid source: {source}')

    c = _dumb_mountctx()

    c.mflags |= MS_BIND
    if recursive:
        c.mflags |= MS_REC

    c.source = source.as_posix()
    c.target = target.as_posix()

    c.mount()

    print(f'info: bind finished with status: {c.status}', file=sys.stdout)

    if recursive:
        c = _dumb_mountctx()

        c.optsmode |= OptsMode.NoTab

        c.mflags |= (MS_SLAVE | MS_REC)

        c.target = target.as_posix()

        c.mount()

        print(f'info: rslave finished with status: {c.status}', file=sys.stdout)

def _umount(target: Path, check: bool, recursive: bool) -> None:
    '''
    Unmount helper.

    Arguments:
        target    - path to unmount
        check     - should we check if target is a mount point?
        recursive - should we unmount recursively?
    '''

    if check and not target.is_mount():
        return

    if target is None or not target.is_dir():
        raise RuntimeError(f'invalid target: {target}')

    if recursive:
        '''
        If recursive operation is requested, we have to fall back to the umount CLI app, since
        libmount currently doesn't implemented recursive unmounting through the Python
        bindings.
        '''
        p_args = ('/usr/bin/umount', '--recursive', target.as_posix())

        prun(p_args, check=True)
    else:
        c = MountContext()

        c.target = target.as_posix()
        
        c.umount()

        if c.status != 1:
            raise RuntimeError(f'umount failed with status: {c.status}')


##########################################################################################
# Internal functions
##########################################################################################

def sandbox_prepare(config: SandboxConfig) -> None:
    '''
    Prepare a sandbox environment for use.

    Arguments:
        config - sandbox configuration
    '''

    print(f'info: entering {_msg}...', file=sys.stdout)

    if config.mount_point.is_mount():
        raise RuntimeError(f'environment mount point is already in use: {config.mount_point}')

    try:
        _mount(None, config.mount_point, fstype=None)

    except Exception as exc:
        raise RuntimeError(f'failed to mount main chroot filesystem: {exc}') from exc

    try:
        target = config.mount_point / Path('proc')

        _mount(None, target, fstype='proc')

    except Exception as exc:
        raise RuntimeError(f'failed to mount proc filesystem: {exc}') from exc

    for m in config.rbind_mounts:
        source = m
        target = config.mount_point / m.relative_to(Path('/'))

        try:
            _mbind(source, target, recursive=True)

        except Exception as exc:
            raise RuntimeError(f'failed to rbind {source}: {exc}') from exc

    for m in config.bind_mounts:
        source = m
        target = config.mount_point / m.relative_to(Path('/'))

        try:
            _mbind(source, target, recursive=False)

        except Exception as exc:
            raise RuntimeError(f'failed to bind {source}: {exc}') from exc

    try:
        source = Path('/home/liquid')
        target = config.mount_point / Path('home/liquid/HostSystem')

        _mbind(source, target, recursive=False)

    except Exception as exc:
        raise RuntimeError(f'failed to mount/bind host home: {exc}') from exc

    print(f'info: {_msg} is ready', file=sys.stdout)

    system_notify('READY=1')

    signal(SIGTERM, _signal_handler)
    signal(SIGINT, _signal_handler)

    spause()

    print(f'info: exiting {_msg}...', file=sys.stdout)

    system_notify('STOPPING=1')

    try:
        target = config.mount_point / Path('home/liquid/HostSystem')
        _umount(target, check=False, recursive=False)

    except Exception as exc:
        print(f'warn: failed to unmount/unbind host home: {exc}', file=sys.stderr)

    for m in reversed(config.bind_mounts):
        source = m
        target = config.mount_point / m.relative_to(Path('/'))

        try:
            _umount(target, check=False, recursive=False)

        except Exception as exc:
            print(f'warn: failed to unmount/unbind {source}: {exc}', file=sys.stderr)

    for m in reversed(config.rbind_mounts):
        source = m
        target = config.mount_point / m.relative_to(Path('/'))

        try:
            _umount(target, check=False, recursive=True)

        except Exception as exc:
            print(f'warn: failed to unmount rbind {source}: {exc}', file=sys.stderr)

    try:
        target = config.mount_point / Path('proc')
        _umount(target, check=False, recursive=False)

    except Exception as exc:
        print(f'warn: failed to unmount proc filesystem: {exc}', file=sys.stderr)

    retry = 0
    main_umount = False
    while retry != _num_retry:
        try:
            _umount(config.mount_point, check=False, recursive=False)
            main_umount = True
            break

        except Exception as exc:
            print(f'warn: failed to unmount main chroot filesystem, retrying: {exc}'.format(exc), file=sys.stderr)

        sleep(1.0)
        retry += 1

    if not main_umount:
        print('warn: could not unmount main chroot filesystem', file=sys.stderr)

    return 0

def sandbox_enter(config: SandboxConfig) -> None:
    '''
    Enter a prepared sandbox environment.

    Arguments:
        config - sandbox configuration
    '''

    if not config.mount_point.is_mount():
        raise RuntimeError(f'environment mount point is not ready: {config.mount_point}')

    network_namespace = get_ns_identifier()

    p_args = ('/usr/bin/chroot', config.mount_point.as_posix(), '/usr/local/bin/setup_chroot.sh', '--none')

    if is_ns_live(network_namespace):
        print(f'info: spawning chroot in network namespace: {network_namespace}', file=sys.stdout)
        p_args = ('ip', 'netns', 'exec', network_namespace) + p_args

    try:
        prun(p_args, check=True)

    except CalledProcessError as err:
        raise RuntimeError(f'failed to enter {_msg}: {err}') from err

def sandbox_cleanup(config: SandboxConfig) -> None:
    '''
    Cleanup a sandbox environment that failed to shutdown properly.

    Arguments:
        config - sandbox configuration
    '''

    try:
        target = config.mount_point / Path('home/liquid/HostSystem')
        _umount(target, check=True, recursive=False)

    except Exception as exc:
        print(f'warn: failed to unmount/unbind host home: {exc}', file=sys.stderr)

    for m in reversed(config.bind_mounts):
        source = m
        target = config.mount_point / m.relative_to(Path('/'))

        try:
            _umount(target, check=True, recursive=False)

        except Exception as exc:
            print(f'warn: failed to unmount/unbind {source}: {exc}', file=sys.stderr)

    for m in reversed(config.rbind_mounts):
        source = m
        target = config.mount_point / m.relative_to(Path('/'))

        try:
            _umount(target, check=True, recursive=True)

        except Exception as exc:
            print(f'warn: failed to unmount rbind {source}: {exc}', file=sys.stderr)

    try:
        target = config.mount_point / Path('proc')
        _umount(target, check=True, recursive=False)

    except Exception as exc:
        print(f'warn: failed to unmount proc filesystem: {exc}', file=sys.stderr)

    try:
        _umount(config.mount_point, check=True, recursive=False)

    except Exception as exc:
        print(f'warn: failed to unmount main chroot filesystem: {exc}', file=sys.stderr)


##########################################################################################
# Main
##########################################################################################

def main(args: list[str]) -> int:
    '''
    Main function.

    Arguments:
        args - list of string arguments from the CLI
    '''

    switcher = {
        '--prepare': sandbox_prepare,
        '--enter': sandbox_enter,
        '--cleanup': sandbox_cleanup,
    }

    if len(args) < 2:
        _usage(args[0])

        return 0

    command = switcher.get(args[1], None)
    if command is None:
        _usage(args[0])

        return 1

    try:
        sandbox_config = SandboxConfig.from_path(_config_path)

    except Exception as exc:
        print(f'error: failed to read config from path: {_config_path}: {exc}', file=sys.stderr)

        return 2

    try:
        command(sandbox_config)

    except Exception as exc:
        print(f'error: failed to execute command: {args[1]}, {exc}', file=sys.stderr)

        return 3

    return 0
