# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

from argparse import ArgumentParser
from pathlib import Path
from sys import stderr

from magic import Magic
from mutagen.flac import FLAC


##########################################################################################
# Functions
##########################################################################################

def vc_copytags(src_path: Path, dst_path: Path) -> None:
    '''
    Copy VorbisComment tags from one file to another.

    Arguments:
        src_path - path to the source file
        dst_path - path to the destination file
    '''

    if not src_path.is_file():
        raise RuntimeError(f'source path is not a file: {src_path}')

    if not dst_path.is_file():
        raise RuntimeError(f'destination path is not a file: {dst_path}')

    mime = Magic(mime=True)
    src_type = mime.from_file(src_path.as_posix())
    dst_type = mime.from_file(dst_path.as_posix())

    if src_type != 'audio/flac':
        raise RuntimeError(f'source has unsupported type: {src_type}')

    if dst_type != 'audio/flac':
        raise RuntimeError(f'destination has unsupported type: {dst_type}')

    try:
        '''
        Mutagen does not provide context management.
        '''
        s = FLAC(src_path.as_posix())
        d = FLAC(dst_path.as_posix())

        if s.tags:
            d.tags += s.tags

        for p in s.pictures:
            d.add_picture(p)

        d.save()

    except Exception as exc:
        raise RuntimeError(f'transfer of tags failed: {exc}') from exc


##########################################################################################
# Main
##########################################################################################

def main(args: list[str]) -> int:
    '''
    Main function.

    Arguments:
        args - list of string arguments from the CLI
    '''

    parser = ArgumentParser(description='Copy VorbisComment and picture metadata.')

    parser.add_argument('-s', '--source', help='Source path', required=True)
    parser.add_argument('-d', '--destination', help='Destination path', required=True)

    parsed_args = parser.parse_args(args[1:])

    try:
        source = Path(parsed_args.source)
        destination = Path(parsed_args.destination)

        vc_copytags(source, destination)

    except Exception as exc:
        print(f'error: failed to copy VorbisComment tags: {source}: {exc}', file=stderr)

        return 1

    return 0
