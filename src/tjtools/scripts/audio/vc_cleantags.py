# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

from pathlib import Path
from sys import stderr, stdout

from magic import Magic
from mutagen.flac import FLAC
from mutagen.oggvorbis import OggVorbis


##########################################################################################
# Constants
##########################################################################################

_switcher = {
    'audio/ogg': OggVorbis,
    'audio/flac': FLAC,
}


##########################################################################################
# Internal functions
##########################################################################################

def _usage(app: str) -> None:
    print(f'Usage: {app} <filename> [tag1name] [tag2name] ...', file=stdout)


##########################################################################################
# Functions
##########################################################################################

def vc_cleantags(path: Path, tag_keys: list[str]) -> None:
    '''
    Clean VorbisComment tags from a file.

    Arguments:
        path     - path to file
        tag_keys - list of keys to clean
    '''

    mime = Magic(mime=True)

    if not path.is_file():
        raise RuntimeError(f'path is not a file: {path}')

    input_type = mime.from_file(path.as_posix())

    audiotype = _switcher.get(input_type)
    if audiotype is None:
        raise RuntimeError(f'input has unsupported type: {input_type}')

    if len(tag_keys) == 0:
        return

    audio = audiotype(path.as_posix())

    for key in tag_keys:
        key_lower = key.lower()
        if key_lower in audio:
            del audio[key_lower]

    audio.save()


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
        print('error: missing filename argument', file=stderr)
        _usage(args[0])

        return 1

    try:
        path = Path(args[1])

        vc_cleantags(path, args[2:])

    except Exception as exc:
        print(f'error: failed clean VorbisComment tags: {path}: {exc}', file=stderr)

        return 1

    return 0
