# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

from subprocess import run as prun
from sys import stderr, stdout


##########################################################################################
# Constants
##########################################################################################

_mpc_args_base = ('mpc', '--quiet')


##########################################################################################
# Internal functions
##########################################################################################

def _usage(app: str) -> None:
    print(f'Usage: {app} --play|--next|--prev', file=stdout)
    print('Wrapper script for multimedia keys.', file=stdout)

def _multimedia_play() -> None:
    p_args = _mpc_args_base + ('toggle',)

    prun(p_args, check=True, capture_output=True)

def _multimedia_next() -> None:
    p_args = _mpc_args_base + ('next',)

    prun(p_args, check=True, capture_output=True)

def _multimedia_prev() -> None:
    p_args = _mpc_args_base + ('prev',)

    prun(p_args, check=True, capture_output=True)


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

        return 1

    cmd = args[1]

    try:

        if cmd == '--play':
            _multimedia_play()
        elif cmd == '--next':
            _multimedia_next()
        elif cmd == '--prev':
            _multimedia_prev()
        else:
            print(f'error: invalid command: {cmd}', file=stderr)

            return 2

    except Exception as exc:
        print(f'error: failed to perform command: {cmd}: {exc}', file=sys.stderr)

        return 3

    return 0
