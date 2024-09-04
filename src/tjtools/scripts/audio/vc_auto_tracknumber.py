# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

from pathlib import Path
from sys import stderr, stdout

from ...vc_addtag import TagEntry, vc_addtag


##########################################################################################
# Internal functions
##########################################################################################

def _pad_tracknumber(i: int, t: int) -> str:
    '''
    Construct tracknumber string with padding.
    '''

    assert(i <= 999 and t <= 999)
    assert(i <= t)

    if t >= 100:
        targetlen = 3
    elif t >= 10:
        targetlen = 2
    else:
        targetlen = 1

    if i >= 100:
        padding = targetlen - 3
    elif i >= 10:
        padding = targetlen - 2
    else:
        padding = targetlen - 1

    return padding * '0' + str(i)


##########################################################################################
# Functions
##########################################################################################

def vc_auto_tracknumber(path: Path) -> None:
    '''
    Auto tracknumber FLAC files in a given directory.

    Arguments:
        path - path to the directory which we should process
    '''

    if not path.is_dir():
        raise RuntimeError(f'path is not a directory: {path}')

    candidates = list(path.glob('*.flac'))

    tracktotal = len(candidates)
    tracknumbers = [_pad_tracknumber(x, tracktotal) for x in range(1, 1 + tracktotal)]

    tt_tag = TagEntry('tracktotal', str(tracktotal))

    [vc_addtag(cand, [TagEntry('tracknumber', tn), tt_tag]) for cand, tn in zip(sorted(candidates), tracknumbers)]


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
        vc_auto_tracknumber(work_dir)

    except Exception as exc:
        print(f'error: failed to auto tracknumber: {work_dir.name}: {exc}', file=stderr)

        return 1

    return 0
