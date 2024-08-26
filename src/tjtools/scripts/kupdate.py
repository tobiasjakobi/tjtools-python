# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

import sys

from os.path import exists, join as pjoin
from os import getcwd, lstat, readlink, remove, scandir, symlink
from shutil import copy2, rmtree
from stat import S_ISLNK
from subprocess import run as prun


##########################################################################################
# Constants
##########################################################################################

_linux = 'linux'
_boot = '/boot'
_modules = '/lib/modules'


##########################################################################################
# Internal functions
##########################################################################################

def _kver(raw: str) -> list[int]:
    tmp = raw.split('-', maxsplit=1)
    if tmp[0] != 'linux':
        return None

    tmp = tmp[1].rsplit('-', maxsplit=1)
    if tmp[1] != 'gentoo':
        return None

    tmp = tmp[0].split('-')
    if len(tmp) == 1:
        has_ext = False
    elif len(tmp) == 2:
        has_ext = True
    else:
        return None

    try:
        ret = [int(x) for x in tmp[0].split('.')]

    except Exception:
        ret = None

    if ret and has_ext:
        ret.append(tmp[1])

    return ret

def _ver_str(ver: list[int]) -> str:
    if not len(ver) in (3, 4):
        return None

    ret = '.'.join([str(x) for x in ver[0:3]])
    if len(ver) == 4:
        ret += '-' + ver[3]

    return ret

def _pkg_name(ver: list[int]) -> str:
    tmp = _ver_str(ver)
    if not tmp:
        return None

    return f'gentoo-sources-{tmp}'

def _cnf_name(ver: list[int]) -> str:
    major = ver[0]
    minor = ver[1]

    return f'vanilla-{major}.{minor}.conf'

def _ktree_name(ver: list[int]) -> str:
    tmp = _ver_str(ver)
    if not tmp:
        return None

    return f'linux-{tmp}-gentoo'

def _kimg_name(ver: list) -> str:
    tmp = _ver_str(ver)
    if not tmp:
        return None

    return f'kernel-{tmp}-gentoo'

def _initrd_name(ver: list) -> str:
    tmp = _ver_str(ver)
    if not tmp:
        return None

    return f'initrd-{tmp}-gentoo'

def _mod_name(ver: list) -> str:
    tmp = _ver_str(ver)
    if not tmp:
        return None

    return f'{tmp}-gentoo'


##########################################################################################
# Main
##########################################################################################

def main(args: list[str]) -> int:
    '''
    Main function.

    Arguments:
        args - list of string arguments from the CLI
    '''

    try:
        l = lstat(_linux)

    except Exception:
        l = None

    if l is None or not S_ISLNK(l.st_mode):
        print('error: symlink to kernel sources not found', file=sys.stderr)

        return 1

    link_target = readlink(_linux)
    src_version = _kver(link_target)

    if src_version is None:
        print('error: failed to extract version information', file=sys.stderr)

        return 2

    print(f'info: current kernel version is: {src_version}', file=sys.stdout)

    kernels = list()

    for entry in scandir():
        if not entry.is_dir(follow_symlinks=False):
            continue

        version = _kver(entry.name)
        if not version:
            continue

        kernels.append([entry.name, version])

    latest = None
    cur_rev = src_version[2]

    for arg in kernels:
        version = arg[1]

        if src_version[0:2] != version[0:2]:
            continue

        if cur_rev >= version[2]:
            continue

        cur_rev = version[2]
        latest = arg

    if not latest:
        print('info: kernel is already up-to-date', file=sys.stdout)

        return 0

    print(f'info: switching to latest kernel version: {latest[1]}', file=sys.stdout)

    remove(_linux)
    symlink(latest[0], _linux)
    copy2(pjoin(link_target, '.config'), pjoin(_linux, '.config'))

    prun(('make', 'oldconfig'), check=True, cwd=pjoin(getcwd(), _linux))
    copy2(pjoin(_linux, '.config'), pjoin(getcwd(), _cnf_name(src_version)))

    prun(('exec_script.sh', 'kmake'), check=True, cwd=pjoin(getcwd(), _linux))

    for arg in kernels:
        if arg == latest:
            continue

        prun(('emerge', '--unmerge', '--quiet', f'={_pkg_name(arg[1])}'), check=True)

        if exists(arg[0]):
            rmtree(arg[0])

        try:
            kimg = pjoin(_boot, _kimg_name(arg[1]))
            remove(kimg)

        except Exception:
            pass

        try:
            initrd = pjoin(_boot, _initrd_name(arg[1]))
            remove(initrd)

        except Exception:
            pass

        try:
            modules = pjoin(_modules, _mod_name(arg[1]))
            rmtree(modules)

        except Exception:
            pass

    prun(('grub-mkconfig', '-o', pjoin(_boot, 'grub/grub.cfg')), check=True)

    return 0
