# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0

from __future__ import annotations


##########################################################################################
# Imports
##########################################################################################

from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path
from sys import exit, stderr, stdout, argv as sys_argv

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

_replaygain_keys = (
    'replaygain_algorithm',
    'replaygain_reference_loudness',
    'replaygain_track_gain',
    'replaygain_track_peak',
    'replaygain_track_range',
    'replaygain_album_gain',
    'replaygain_album_peak',
    'replaygain_album_range',
)


##########################################################################################
# Dataclass definitions
##########################################################################################

@dataclass(frozen=True)
class TagEntry:
    key: str
    value: str

    def is_replaygain(self) -> bool:
        '''
        Check if this is ReplayGain tag.
        '''

        return self.key in _replaygain_keys

    def is_empty(self) -> bool:
        '''
        Check if the entry is empty.
        '''

        return self.value is None or len(self.value) == 0

    @staticmethod
    def from_arg(arg: str) -> TagEntry:
        '''
        Parse a tag entry from a CLI argument.

        Arguments:
            arg - the CLI argument string
        '''

        key, value = arg.split(':', maxsplit=1)

        return TagEntry(key, value)


##########################################################################################
# Functions
##########################################################################################

def vc_addtag(path: Path, entries: list[TagEntry]) -> None:
    '''
    Add a list of tag entries as VorbisComment.

    Arguments:
        path    - path to the file which we add the tags to
        entries - list of tag entries that we use
    '''

    if not path.is_file():
        raise RuntimeError(f'path is not a file: {path}')

    input_type = Magic(mime=True).from_file(path.as_posix())

    audiotype = _switcher.get(input_type)
    if audiotype is None:
        raise RuntimeError(f'input has unsupported type: {input_type}')

    audio_file = audiotype(path.as_posix())

    if entries is None or len(entries) == 0:
        if not audio_file.tags:
            print(f'info: no tags found: {path}', file=stdout)
        else:
            print(f'info: printing all tags: {path}', file=stdout)

            for tag_key, tag_value in audio_file.tags:
                print(f'{tag_key.lower()} = {tag_value}', file=stdout)

    else:
        for entry in entries:
            if len(entry.value) == 0:
                if entry.key in audio_file:
                    del audio_file[entry.key]
            else:
                audio_file[entry.key] = entry.value

        audio_file.save()


##########################################################################################
# Main
##########################################################################################

def main(args: list[str]) -> int:
    '''
    Main function.

    Arguments:
        args - list of string arguments from the CLI
    '''

    parser = ArgumentParser(description='Add VorbisComment tags to a file.')

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
            vc_addtag(file, tags)

        except Exception as exc:
            print(f'error: failed to add VorbisComment tags: {file}: {exc}', file=stderr)

            return 2

    return 0

if __name__ == '__main__':
    exit(main(sys_argv))
