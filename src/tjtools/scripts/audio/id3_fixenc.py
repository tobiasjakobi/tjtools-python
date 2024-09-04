# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

from argparse import ArgumentParser
from pathlib import Path
from sys import stderr, stdout

from eyed3.core import load as id3_load
from eyed3.id3 import ID3_V2_4


##########################################################################################
# Internal functions
##########################################################################################

def _print_tag(tag: str, name: str, src_encoding: str) -> None:
    if tag is None or not tag:
        return

    fixed_tag = tag.encode('latin1').decode(src_encoding)

    print(f'{name}: {fixed_tag}', file=stdout)


##########################################################################################
# Main
##########################################################################################

def main(args: list[str]) -> int:
    '''
    Main function.

    Arguments:
        args - list of string arguments from the CLI
    '''

    parser = ArgumentParser(description='Helper to fix tag encoding issues.')

    parser.add_argument('-e', '--encoding', type=str, help='Soucrce character encoding', required=True)
    parser.add_argument('-f', '--file', type=str, help='Input file', required=True)

    parsed_args = parser.parse_args(args[1:])

    encoding = parsed_args.encoding
    file = Path(parsed_args.file)

    if not file.is_file():
        print(f'error: input file not found: {file}', file=stderr)

        return 1

    try:
        audio = id3_load(path=file.as_posix(), tag_version=ID3_V2_4)

    except Exception as exc:
        print(f'error: failed to open input: {exc}', file=stderr)

        return 2

    if not audio:
        print(f'error: input does not contain ID3v2: {file}', file=stderr)

        return 3

    t = audio.tag

    if not t:
        print(f'info: no tags found in input: {file}', file=stdout)

        return 0

    _print_tag(t.title, 'title', encoding)
    _print_tag(t.album, 'album', encoding)
    _print_tag(t.artist, 'artist', encoding)
    _print_tag(t.album_artist, 'album artist', encoding)

    return 0
