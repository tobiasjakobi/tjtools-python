# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

from pathlib import Path
from sys import stderr, stdout

from magic import Magic

from ...common_util import path_walk
from ...vc_addtag import TagEntry, vc_addtag
from .flac_encode import is_flac
from .vc_auto_tracknumber import vc_auto_tracknumber


##########################################################################################
# Constants
##########################################################################################

_directory_prefix = 'disc'


##########################################################################################
# Functions
##########################################################################################

def vc_auto_albumprepare(path: Path) -> None:
    '''
    Auto tracknumber FLAC files in a given directory.

    Arguments:
        path - path to the directory which we should process
    '''

    if not path.is_dir():
        raise RuntimeError(f'path is not a directory: {path}')

    mime = Magic(mime=True)

    for entry in path.iterdir():
        if not entry.is_dir():
            continue

        entry_name = entry.name

        if not entry_name.startswith(_directory_prefix):
            continue

        print(f'info: processing directory: {entry_name}', file=stdout)

        entry_suffix = entry_name.removeprefix(_directory_prefix)
        if not entry_suffix.isdigit():
            continue

        print(f'info: apply discnumber tag: {entry_suffix}', file=stdout)

        vc_auto_tracknumber(entry)

        entries = [TagEntry(key='discnumber', value=entry_suffix)]

        for file in path_walk(entry):
            if is_flac(mime, file):
                vc_addtag(file, entries)


##########################################################################################
# Main
##########################################################################################

def main(args: list[str]) -> int:
    '''
    Main function.

    Arguments:
        args - list of string arguments from the CLI
    '''

    if len(args) < 2:
        work_dir = Path.cwd()

        print(f'info: using current directory: {work_dir.name}', file=stdout)
    else:
        work_dir = Path(args[1])

    try:
        vc_auto_albumprepare(work_dir)

    except Exception as exc:
        print(f'error: failed to auto albumprepare: {work_dir.name}: {exc}', file=stderr)

        return 1

    return 0
