# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

from argparse import ArgumentParser
from pathlib import Path
from sys import exit, stderr, stdout, argv as sys_argv

from eyed3.core import load as id3_load
from eyed3.id3 import ID3_V2_4
from eyed3.mp3 import MIME_TYPES, Mp3AudioFile
from eyed3.utils import guessMimetype

from .vc_addtag import TagEntry


##########################################################################################
# Functions
##########################################################################################

def is_mp3(path: Path) -> bool:
    if not path.is_file():
        raise RuntimeError(f'path is not a file: {path}')

    mimetype = guessMimetype(path)

    if mimetype == 'application/octet-stream':
        object = id3_load(path)
        return isinstance(object, Mp3AudioFile)

    return mimetype in MIME_TYPES

def id3_addtag(path: Path, entries: list[TagEntry]) -> None:
    '''
    Add a list of tag entries as ID3v2.

    Arguments:
        path    - path to the file which we add the tags to
        entries - list of tag entries that we use
    '''

    if not path.is_file():
        raise RuntimeError(f'path is not a file: {path}')

    audio_file = id3_load(path.as_posix(), tag_version=ID3_V2_4)

    if not audio_file:
        raise RuntimeError(f'file is not of type MP3: {path}')

    if entries is None or len(entries) == 0:
        if not audio_file.tags:
            print(f'info: no tags found: {path}', file=stdout)
        else:
            print(f'info: printing all user text frames: {path}', file=stdout)
            for arg in audio_file.tag.user_text_frames:
                print(f'{arg.description} = {arg.text}', file=stdout)

    else:
        if not audio_file.tag:
            audio_file.initTag()

        for entry in entries:
            if entry.is_replaygain():
                audio_file.tag.user_text_frames.set(description=entry.key, text=entry.value)
            else:
                print(f'warn: skipping invalid tag: {entry.key}', file=stderr)

        audio_file.tag.save(version=ID3_V2_4)


##########################################################################################
# Main
##########################################################################################

def main(args: list[str]) -> int:
    '''
    Main function.

    Arguments:
        args - list of string arguments from the CLI
    '''

    parser = ArgumentParser(description='Add IDv2 tags to a file.')

    parser.add_argument('-f', '--file', help='Path to file which we want to edit', required=True)
    parser.add_argument('-t', '--tag', action='append', help='A tag key/value pair on the format key:value')

    parsed_args = parser.parse_args(args[1:])

    if parsed_args.file is not None:
        file = Path(parsed_args.file)

        tags = None

        try:
            if parsed_args.tag is not None:
                tags = [TagEntry.from_arg(x) for x in parsed_args.tag]

        except Exception as exc:
            print(f'error: invalid tag argument given: {file}: {exc}', file=stderr)

            return 1

        try:
            id3_addtag(file, tags)

        except Exception as exc:
            print(f'error: failed to add ID3v2 tags: {file}: {exc}', file=stderr)

            return 2

    return 0

if __name__ == '__main__':
    exit(main(sys_argv))
