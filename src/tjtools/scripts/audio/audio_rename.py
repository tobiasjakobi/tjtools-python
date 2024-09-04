# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

from argparse import ArgumentParser
from enum import IntEnum
from pathlib import Path
from sys import stderr
from typing import Any

from magic import Magic
from mutagen import MutagenError
from mutagen.flac import FLAC
from mutagen.mp4 import MP4
from mutagen.oggvorbis import OggVorbis

from ...common_util import path_walk
from ...id3_addtag import is_mp3


##########################################################################################
# Constants
##########################################################################################

'''
Minimum padding we want to have to the track number.
'''
_track_minimum_padding = 2


##########################################################################################
# Enum definitions
##########################################################################################

class PaddingType(IntEnum):
    Track = 0
    Disc  = 1


##########################################################################################
# Internal functions
##########################################################################################

def _is_valid_value(value: Any) -> bool:
    '''
    Check if a Mutagen tag value is valid.

    Arguments:
        value - the value to check
    '''

    if value is None:
        return False

    if not isinstance(value, list):
        return False

    '''
    Disallow multiline tags.
    '''
    if len(value) != 1:
        return False

    return True

def _is_valid_mp4_tuple(value: Any) -> bool:
    '''
    Check if the value is a valid MP4 tuple.

    Arguments:
        value - the value to check

    A valid MP4 tuple is of the form (a, b) with a and b both integers.
    '''

    if not isinstance(value, tuple):
        return False
    
    if len(value) != 0:
        return False
    
    if not all([isinstance(x, int) for x in value]):
        return False

    return True

def _number_padding(input: str, target: str, minimum: int) -> str:
    len_i = len(input)
    len_t = len(target)

    if minimum != 0 and len_t < minimum:
        len_t = minimum

    return '0' * max(0, len_t - len_i)

def _padded_number(number: str, total: str, type: PaddingType) -> str:
    if type == PaddingType.Track:
        ret = _number_padding(number, total, _track_minimum_padding)
    elif type == PaddingType.Disc:
        ret = _number_padding(number, total, 0)
    else:
        raise RuntimeError(f'unknown padding type {type}')

    return ret + number

def _padded_info(info: tuple[int, int], type: PaddingType) -> str:
    number, total = map(str, info)

    if type == PaddingType.Track:
        ret = _number_padding(number, total, _track_minimum_padding)
    elif type == PaddingType.Disc:
        ret = _number_padding(number, total, 0)
    else:
        raise RuntimeError(f'unknown padding type {type}')

    return ret + number


##########################################################################################
# Functions
##########################################################################################

def canonical_flac_ogg(path: Path, is_flac: bool) -> Path:
    '''
    Compute the canonical name of a FLAC / OggVorbis file.

    Arguments:
        path    - path to the file
        is_flac - are we handling a FLAC file?

    Returns a new path with the canonical name.
    '''

    if not path.is_file():
        raise RuntimeError(f'path is not a file: {path}')

    try:
        audio = FLAC(path.as_posix()) if is_flac else OggVorbis(path.as_posix())

    except MutagenError:
        return None

    '''
    The mandatory tag keys are title, tracknumber and tracktotal.
    '''
    title_value = audio.tags.get('title')
    tracknumber_value = audio.get('tracknumber')
    tracktotal_value = audio.get('tracktotal')

    '''
    Optional tag keys are discnumber and disctotal.
    '''
    discnumber_value = audio.tags.get('discnumber')
    disctotal_value = audio.tags.get('disctotal')

    for value in (title_value, tracknumber_value, tracktotal_value):
        if not _is_valid_value(value):
            return None

    tracknumber = _padded_number(tracknumber_value[0], tracktotal_value[0], PaddingType.Track)

    canonical_name = tracknumber + ' ' + title_value[0].replace('/', '~')

    '''
    Prepend discnumber prefix if available.
    '''
    if _is_valid_value(discnumber_value) and _is_valid_value(disctotal_value):
        discnumber = _padded_number(discnumber_value[0], disctotal_value[0], PaddingType.Disc)

        canonical_name = discnumber + canonical_name

    return path.parent / f'{canonical_name}{path.suffix}'

def canonical_mp3(path: Path) -> Path:
    '''
    Compute the canonical name of a MP3 file.

    Arguments:
        path - path to the MP3 file

    Returns a new path with the canonical name.
    '''

    raise RuntimeError('TODO: canonical_mp3 not implemented')

def canonical_m4a(path: Path) -> Path:
    '''
    Compute the canonical name of a M4A file.

    Arguments:
        path - path to the M4A file

    Returns a new path with the canonical name.
    '''

    if not path.is_file():
        raise RuntimeError(f'path is not a file: {path}')

    try:
        audio = MP4(path.as_posix())

    except MutagenError:
        return None

    '''
    The mandatory tag keys contain the information about track title, track number
    and total number of tracks.

    The track number of total are mebers of the trackinfo value.
    '''
    titles_value = audio.tags.get('\xa9nam')
    trackinfo_value = audio.tags.get('trkn')

    '''
    Optional tag keys contain the information about disc number and total number
    of discs.
    '''
    discinfo_value = audio.tags.get('disk')
    if discinfo_value is None:
        discinfo_value = audio.tags.get('disknumber')

    for value in (titles_value, trackinfo_value):
        if not _is_valid_value(value):
            return None

    if not _is_valid_mp4_tuple(trackinfo_value[0]):
        return None

    tracknumber = _padded_info(trackinfo_value[0], PaddingType.Track)

    canonical_name = tracknumber + ' ' + titles_value[0].replace('/', '~')

    '''
    Prepend discnumber prefix if available.
    '''
    if _is_valid_mp4_tuple(discinfo_value):
        discnumber = _padded_info(discinfo_value[0], PaddingType.Disc)

        canonical_name = discnumber + canonical_name

    return path.parent / f'{canonical_name}{path.suffix}'

def audio_rename(path: Path) -> int:
    '''
    Rename all audio files in a directory path to canonical form.

    Arguments:
        path - path to directory
    '''

    if not path.is_dir():
        raise RuntimeError(f'path is not a directory: {path}')

    mime = Magic(mime=True)

    rename_errors = 0

    for entry in path_walk(path):
        if not entry.is_file():
            continue

        entry_type = mime.from_file(entry.as_posix())
        if len(entry.suffix) == 0:
            print(f'error: entry without suffix: {entry}', file=stderr)

            rename_errors += 1

            continue

        if entry_type == 'audio/ogg':
            canonical_entry = canonical_flac_ogg(entry, is_flac=False)
        elif entry_type == 'audio/flac':
            canonical_entry = canonical_flac_ogg(entry, is_flac=True)
        elif entry_type in ('audio/x-m4a', 'video/mp4'):
            canonical_entry = canonical_m4a(entry)
        elif entry_type == 'audio/mpeg' or is_mp3(entry):
            canonical_entry = canonical_mp3(entry)
        else:
            continue

        if canonical_entry is None:
            print(f'error: failed to find canonical form: {entry}', file=stderr)

            rename_errors += 1

            continue

        '''
        Check if the input path is already canonical.
        '''
        if entry.name == canonical_entry.name:
            continue

        '''
        Avoid overwriting existing files.
        '''
        if canonical_entry.exists():
            print(f'error: canonical entry already exists: {canonical_entry}', file=stderr)

            rename_errors += 1

            continue

        try:
            entry.rename(canonical_entry)

        except Exception:
            print(f'error: failed to rename: {entry}', file=stderr)

            rename_errors += 1

    if rename_errors != 0:
        raise RuntimeError(f'error during rename: {rename_errors}')


##########################################################################################
# Main
##########################################################################################

def main(args: list[str]) -> int:
    '''
    Main function.

    Arguments:
        args - list of string arguments from the CLI
    '''

    parser = ArgumentParser(description='Rename all audio files in a directory path to canonical form.')

    parser.add_argument('-d', '--directory', required=True, help='Directory where we look for audio files')

    parsed_args = parser.parse_args(args[1:])

    if parsed_args.directory is not None:
        directory = Path(parsed_args.directory)

        try:
            audio_rename(directory)

        except Exception as exc:
            print(f'error: failed to rename audio: {directory}: {exc}', file=stderr)

            return 1

    return 0
