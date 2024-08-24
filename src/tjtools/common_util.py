# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

from pathlib import Path
from sys import stdout
from termios import TCSADRAIN, tcgetattr, tcsetattr, error as termios_err
from typing import Generator


##########################################################################################
# Class definitions
##########################################################################################

class StandardOutputProtector:
    '''
    Context manager that protects the standard output from changes.
    '''

    def __init__(self):
        self._stdout_fd = stdout.fileno()

        try:
            self._stdout_attr = tcgetattr(self._stdout_fd)

        except termios_err:
            self._stdout_attr = None

    def __enter__(self):
        return None

    def __exit__(self, type, value, traceback):
        if self._stdout_attr is not None:
            tcsetattr(self._stdout_fd, TCSADRAIN, self._stdout_attr)


##########################################################################################
# Functions
##########################################################################################

def path_walk(path: Path) -> Generator[Path, None, None]:
    '''
    Walk a directory hierarchy and return the files found.

    Arguments:
        path - directory path where to start the walk

    This is a simplified replacement for os.walk().
    '''

    if not path.is_dir():
        raise RuntimeError('invalid directory path')

    for p in path.iterdir():
        if p.is_dir():
            yield from path_walk(p)
            continue

        yield p.resolve()
