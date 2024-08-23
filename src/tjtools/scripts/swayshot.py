# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

import sys

from datetime import datetime
from pathlib import Path
from subprocess import DEVNULL, run as prun

from i3ipc import Connection as I3Connection


##########################################################################################
# Internal functions
##########################################################################################

def _usage(app: str) -> None:
    print(f'Usage: {app} --full|--select', file=sys.stdout)

def _save_path() -> Path:
    now = datetime.now()

    return Path(now.strftime('~/screenshot_%Y-%m-%d-%H%M%S.png')).expanduser()

def _full_shot(path: Path) -> None:
    conn = I3Connection()

    focused_output = None
    for output in conn.get_outputs():
        focused = output.ipc_data.get('focused')
        if focused is not None and focused:
            focused_output = output.ipc_data.get('name')
            break

    if focused_output is None:
        grim_args = ('grim', path.as_posix())
    else:
        grim_args = ('grim', '-o', focused_output, path.as_posix())

    prun(grim_args, check=True, stdin=DEVNULL, capture_output=True, encoding='utf-8')

def _select_shot(path: Path) -> None:
    p = prun('slurp', check=True, stdin=DEVNULL, capture_output=True, encoding='utf-8')

    slurp_out = p.stdout.splitlines()
    if len(slurp_out) != 1:
        raise RuntimeError('malformed slurp result')

    area = slurp_out[0].rstrip()

    grim_args = ('grim', '-g', area, path.as_posix())
    prun(grim_args, check=True, stdin=DEVNULL, capture_output=True, encoding='utf-8')


##########################################################################################
# Main
##########################################################################################

def main(args: list[str]) -> int:
    '''
    Main function.

    Arguments:
        args - list of string arguments from the CLI
    '''

    if len(args) != 2:
        _usage(args[0])

        return 0

    mode = args[1]
    outname = _save_path()

    try:
        if mode == '--full':
            _full_shot(outname)
        elif mode == '--select':
            _select_shot(outname)
        else:
            return 1

    except Exception as exc:
        print(f'error: swayshot {mode} failed: {exc}', file=sys.stderr)

        return 2

    return 0
