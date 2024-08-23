# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


from __future__ import annotations


##########################################################################################
# Imports
##########################################################################################

from dataclasses import dataclass
from pathlib import Path
from subprocess import DEVNULL, run as prun
from tempfile import TemporaryDirectory

from i3ipc import Connection as I3Connection


##########################################################################################
# Dataclass definitions
##########################################################################################

@dataclass(frozen=True)
class OutputInfo:
    name: str
    resolution: tuple[int, int]

    @staticmethod
    def from_json(input: dict) -> OutputInfo:
        '''
        Create an OutputInfo object from a JSON dictionary.

        Arguments:
            input - the JSON dictionary to use
        '''

        mode = input.get('current_mode')

        return OutputInfo(
            name       = input.get('name'),
            resolution = (mode.get('width'), mode.get('height'))
        )


##########################################################################################
# Internal functions
##########################################################################################

def _get_focused_output() -> OutputInfo:
    '''
    Determine the focused output.

    Returns an OutputInfo object, or None if no focused output was found.
    '''

    conn = I3Connection()

    for output in conn.get_outputs():
        focused = output.ipc_data.get('focused')
        if focused is not None and focused:
            return OutputInfo.from_json(output.ipc_data)

    return None

def _bg(path: Path, output: OutputInfo) -> None:
    p_args = ('grim', path.as_posix()) if output is None else ('grim', '-o', output.name, path.as_posix())

    prun(p_args, check=True, stdin=DEVNULL)

def _bgblur(input_path: Path, output_path: Path) -> None:
    p_args = (
        'convert', input_path.as_posix(),
        '-scale', '25%',
        '-blur', '0x2',
        '-scale', '400%',
        '-fill', 'black',
        '-colorize', '50%',
        output_path.as_posix(),
    )

    prun(p_args, check=True, stdin=DEVNULL)

def _locktext(path: Path, width: int, height: int) -> None:
    pango_markup = """pango:<span foreground='#ffffff' background='#000000' font_desc='Liberation Sans 34'>Type password to unlock</span>"""
    p_args = (
        'convert',
        '-size', f'{width}x{height}',
        '-background', 'black',
        '-gravity', 'center',
        pango_markup,
        path.as_posix(),
    )

    prun(p_args, check=True, stdin=DEVNULL)

def _merge(primary_path: Path, secondary_path: Path, output_path: Path) -> None:
    p_args = (
        'convert',
        primary_path.as_posix(), secondary_path.as_posix(),
        '-gravity', 'center',
        '-composite',
        '-matte',
        output_path.as_posix(),
    )

    prun(p_args, check=True, stdin=DEVNULL)

def _makelock(tmp_path: Path, output_path: Path) -> None:
    bg_path = tmp_path / 'bg.png'
    locktext_path = tmp_path / 'locktext.png'
    bgblur_path = tmp_path / 'bgblur.png'

    output = _get_focused_output()

    if output is None:
        locktext_width = 1920
        locktext_height = 60
    else:
        locktext_width = output.resolution[0]
        locktext_height = int(float(output.resolution[1]) * 0.06)

    _bg(bg_path, output)
    _locktext(locktext_path, locktext_width, locktext_height)
    _bgblur(bg_path, bgblur_path)
    _merge(bgblur_path, locktext_path, output_path)


##########################################################################################
# Functions
##########################################################################################

def fancylock() -> None:
    '''
    Helper to compose a fancy lock screen.
    '''

    with TemporaryDirectory(prefix='/tmp/') as tmp:
        tmp_path = Path(tmp)
        output_path = tmp_path / 'output.png'

        args_base = ('swaylock', '--daemonize')

        try:
            _makelock(tmp_path, output_path)

            p_args = args_base + ('--scaling', 'fill', '--image', output_path.as_posix())

        except Exception:
            p_args = args_base

        prun(p_args, check=True, stdin=DEVNULL)
