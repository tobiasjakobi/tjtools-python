# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0

'''
Fill some standard tags via a template.
Apply this to a FLAC encoded EAC rip.
'''


##########################################################################################
# Imports
##########################################################################################

from pathlib import Path
from shutil import copy2
from subprocess import DEVNULL, run as prun
from sys import stderr, stdout
from tempfile import TemporaryDirectory

from ...vc_addtag import TagEntry, vc_addtag


##########################################################################################
# Constants
##########################################################################################

_template = Path('~/local/tagging.template')

_editor = '/usr/bin/featherpad'


##########################################################################################
# Functions
##########################################################################################

def eac_pretag(path: Path) -> None:
    '''
    Pretag an Exact Audio copy rip.

    Arguments:
        path - path to the rip directory
    '''

    if not path.is_dir():
        raise RuntimeError(f'path is not a directory: {path}')

    candidates = list(path.glob('*.flac'))

    with TemporaryDirectory(prefix='/tmp/') as tmp:
        input_path = Path(tmp) / Path('input.txt')

        copy2(_template.expanduser().as_posix(), input_path.as_posix())

        p_args = (_editor, '--standalone', input_path.as_posix())

        prun(p_args, check=True, stdin=DEVNULL, capture_output=True, encoding='utf-8')

        input_lines = input_path.read_text(encoding='utf-8').splitlines()

    tag_entries: list[TagEntry] = list()

    for line in input_lines:
        try:
            key_raw, value_raw = line.split('=', maxsplit=1)

        except ValueError:
            print(f'warn: skipping malformed line: {line}', file=stderr)

            continue

        entry = TagEntry(key_raw.rstrip(' '), value_raw.lstrip(' '))
        if len(entry.key) == 0:
            print(f'warn: skipping malformed tag key: {entry.key}', file=stderr)

            continue

        if not entry.is_empty():
            tag_entries.append(entry)

    if len(tag_entries) != 0:
        [vc_addtag(cand, tag_entries) for cand in candidates]


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
        eac_pretag(work_dir)

    except Exception as exc:
        print(f'error: failed to EAC pretag: {work_dir.name}: {exc}', file=stderr)

        return 1

    return 0
