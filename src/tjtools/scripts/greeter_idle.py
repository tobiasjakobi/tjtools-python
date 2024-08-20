#!/usr/bin/env python3
# -*- coding: utf-8 -*-


##########################################################################################
# Imports
##########################################################################################

import sys

from pathlib import Path

from i3ipc import Connection as I3Connection


##########################################################################################
# Internal functions
##########################################################################################

def _usage(app: str) -> None:
    print(f'Usage: {app} --display-on|--display-off', file=sys.stdout)
    print('Wrapper script for swayidle operations.', file=sys.stdout)

def _output_power(state: bool) -> None:
    conn = I3Connection()

    output_names: list[str] = list()

    for output in conn.get_outputs():
        name = output.ipc_data.get('name')
        if name is not None:
            output_names.append(name)

    for name in output_names:
        cmd = 'output {0} power {1}'.format(name, 'on' if state else 'off')

        response = conn.command(cmd)
        if len(response) != 1 or not response[0].success:
            raise RuntimeError('failed to change output power')


##########################################################################################
# Main
##########################################################################################

def main(args: list[str]) -> int:
    if len(args) < 2:
        _usage(args[0])
        return 1

    cmd = args[1]

    try:
        if cmd == '--display-on':
            _output_power(True)
        elif cmd == '--display-off':
            _output_power(False)
        else:
            print(f'error: invalid command: {cmd}', file=sys.stderr)

            return 1

    except Exception as exc:
        print(f'error: failed to perform command: {cmd}: {exc}', file=sys.stderr)

        return 2

    return 0
