# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

import sys

from pathlib import Path

from ..common_util import path_walk


##########################################################################################
# Constants
##########################################################################################

'''
Tuple of characters that are not allowed in VFAT filenames.
'''
_reserved_chars = ('<', '>', ':', '"', '/', '\\', '|', '?', '*')

'''
Character used to replace non-allowed chars.
'''
_replacement_char = '_'


##########################################################################################
# Internal functions
##########################################################################################

def _usage(app: str):
    print(f'Usage: {app} <directory> [<another directory>...]', file=sys.stdout)


##########################################################################################
# Functions
##########################################################################################

def sanitize_vfat(name: str) -> str:
    '''
    Sanitize a name for a VFAT filesystem.

    Arguments:
        name - name to sanitize
    '''

    for r in _reserved_chars:
        name = name.replace(r, _replacement_char)

    return name

def rename_vfat(path: Path) -> None:
    '''
    Rename a file so it becomes suitable for a VFAT filesystem.

    Arguments:
        file_path - path to file which should be renamed
    '''

    if not path.is_file():
        raise RuntimeError(f'path is not a file: {path}')

    name_original = path.name

    name_sanitized = sanitize_vfat(name_original)
    if name_original == name_sanitized:
        return

    sanitized_path = path.parent / Path(name_sanitized)
    if sanitized_path.exists():
        print(f'warn: sanitized version exists: {name_original}', file=sys.stdout)
        return

    print(f'info: sanitizing: {name_original} -> {name_sanitized}')

    path.rename(sanitized_path)

def rename_vfat_dir(path: Path) -> None:
    '''
    Rename the file contents of a directory, so that they
    become suitable for a VFAT filesystem.

    Arguments:
        directory_path - path to directory which should be processed
    '''

    if not path.is_dir():
        raise RuntimeError(f'path is not a directory: {path}')

    list(map(rename_vfat, path_walk(path)))


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
        _usage(args[0])

        return 0

    rename_error = False

    for arg in args[1:]:
        path = Path(arg)

        try:
            rename_vfat_dir(path)

        except Exception as exc:
            print(f'warn: error occured while renaming: {path}: {exc}', file=sys.stderr)

            rename_error = True

    if rename_error:
        return 1

    return 0
