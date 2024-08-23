# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0

'''
If the file has a UTF-8 byte order mark (BOM), then strip the BOM.
'''


##########################################################################################
# Imports
##########################################################################################

import sys

from pathlib import Path


##########################################################################################
# Internal functions
##########################################################################################

def _usage(app: str):
    print(f'Usage: {app} <input> [<output>]', file=sys.stdout)

def _is_bom(header: bytes) -> bool:
    return header == b'\xef\xbb\xbf'


##########################################################################################
# Functions
##########################################################################################

def strip_utf8bom(input_path: Path, output_path: Path) -> None:
    '''
    Strip the UTF8 BOM.

    Arguments:
        input_path  - path to input file
        output_path - optional path to output file (can be None)

    If the input has no BOM, then the input is just copied.
    '''

    if not input_path.is_file():
        raise RuntimeError(f'input path is not a file: {input_path}')

    if output_path is None:
        output_path = input_path.parent / Path(f'{input_path.name}.noBOM')

    if output_path.exists():
        raise RuntimeError(f'output path already exists: {output_path}')

    input_data = input_path.read_bytes()

    strip = False
    if len(input_data) >= 3:
        strip = _is_bom(input_data[0:3])
        if not strip:
            print('warn: no UTF8 byte order mark found', file=sys.stderr)

    output_path.write_bytes(input_data[3:] if strip else input_data)


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
        print('error: missing input argument', file=sys.stderr)
        _usage(args[0])

        return 1

    try:
        input_path = Path(args[1])
        output_path = None if len(args) < 3 else Path(args[2])

        strip_utf8bom(input_path, output_path)

    except Exception as exc:
        print(f'error: failed to strip UTF8 BOM: {exc}', file=sys.stderr)

        return 1

    return 0
