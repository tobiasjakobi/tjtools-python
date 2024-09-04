# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

from argparse import ArgumentParser
from pathlib import Path
from sys import exit, stderr, stdout, argv as sys_argv
from typing import Any

from magic import Magic
from mutagen.mp4 import MP4, MP4FreeForm, MP4Tags, AtomDataType as MP4Atom

from .vc_addtag import TagEntry


##########################################################################################
# Constants
##########################################################################################

_canonical_switcher = {
    '\xa9alb': 'album',
    '\xa9nam': 'title',
    '\xa9ART': 'artist',
    'aART': 'album artist',
    '\xa9wrt': 'composer',
    '\xa9day': 'year',
    '\xa9cmt': 'comment',
    '\xa9gen': 'genre',
    '\xa9des': 'description',
    '\xa9too': 'encoded by',
    'disk': 'disknumber',
    'trkn': 'tracknumber',
    'pgap': 'part of gapless album',
    'tmpo': 'tempo/BPM',
    'cpil': 'part of a compilation',
}

_unprintable_tags = [
    'covr',
]


##########################################################################################
# Internal functions
##########################################################################################

def _is_valid_canonical(entry: TagEntry) -> bool:
    '''
    Test if the canonical name is valid (for adding/removal).
    '''

    return entry.is_replaygain()

def _is_printable(tag_key: str) -> bool:
    '''
    Test if the content of a MP4 tag is printable.
    '''

    return tag_key not in _unprintable_tags

def _freeform_to_canonical(tag_key: str) -> str:
    '''
    Translates a MP4 freeform tag key.
    '''

    if len(tag_key) < 4 or not tag_key.startswith('----'):
        raise RuntimeError('malformed freeform key')

    freeform = tag_key.split(':', maxsplit=2)

    if len(freeform) == 3 and freeform[1] == 'com.apple.iTunes':
        return freeform[2]

    return f'unknown freeform key: {tag_key}'

def _key_to_canonical(tag_key: str) -> str:
    '''
    Translates a MP4 tag key to a canonical form.
    '''

    if len(tag_key) >= 4 and tag_key.startswith('----'):
        return _freeform_to_canonical(tag_key)

    can = _canonical_switcher.get(tag_key, None)
    if can is None:
        return f'unknown tag key: {tag_key}'

    return can

def _remove_tag_canonical(tags: MP4Tags, entry: TagEntry) -> None:
    '''
    Remove a tag via its canonical name.
    '''

    real_key = f'----:com.apple.iTunes:{entry.key}'
    if real_key in tags:
        del tags[real_key]

def _add_tag_canonical(tags: MP4Tags, entry: TagEntry) -> None:
    '''
    Add a tag via its canonical name.

    TODO/FIXME: currently only freeform tags are supported
    '''

    real_key = f'----:com.apple.iTunes:{entry.key}'

    tags[real_key] = MP4FreeForm(entry.value.encode('utf-8'), dataformat=MP4Atom.UTF8)

def _freeform_to_string(ff: MP4FreeForm) -> str:
    '''
    Convert a MP4 freeform object to a regular string.
    '''

    if ff.dataformat == MP4Atom.IMPLICIT:
        return format(ff)
    elif ff.dataformat == MP4Atom.UTF8:
        return bytes(ff).decode('utf-8')
    elif ff.dataformat == MP4Atom.UTF16:
        return bytes(ff).decode('utf-16')

    raise RuntimeError('unsupported freeform format')

def _printable_to_string(p: Any) -> str:
    '''
    Convert the value of a printable MP4 tag to a regular string.
    '''

    if isinstance(p, bool):
        return str(p)

    if not isinstance(p, list) or len(p) != 1:
        raise RuntimeError('malformed tag')

    data = p[0]

    if isinstance(data, tuple):
        if len(data) != 2:
            raise RuntimeError('unhandled tuple size')

        return '{0}/{1}'.format(*data)

    if isinstance(data, MP4FreeForm):
        return _freeform_to_string(data)

    if isinstance(data, int):
        return str(data)

    if isinstance(data, str):
        return data

    raise RuntimeError('unhandled tag type')

def _value_to_string(tag_key: str, tag_value: Any) -> str:
    '''
    Convert a MP4 tag value to a regular string.
    '''

    if tag_key == 'tmpo':
        ret = str(tag_value[0])
    elif tag_key == '----:com.apple.iTunes:Encoding Params':
        ret = bytes(tag_value[0]).decode('utf-8') # FIXME: wrong encoding
    elif _is_printable(tag_key):
        ret = _printable_to_string(tag_value)
    else:
        ret = None

    return ret


##########################################################################################
# Functions
##########################################################################################

def mp4_addtag(path: Path, entries: list[TagEntry]) -> None:
    '''
    Add a list of tag entries as MP4.

    Arguments:
        path    - path to the file which we add the tags to
        entries - list of tag entries that we use
    '''

    if not path.is_file():
        raise RuntimeError(f'path is not a file: {path}')

    mime = Magic(mime=True)


    input_type = mime.from_file(path.as_posix())
    if input_type not in ('video/mp4', 'audio/x-m4a'):
        raise RuntimeError(f'input file has unsupported type: {input_type}')

    audio_file = MP4(path.as_posix())

    if entries is None or len(entries) == 0:
        if not audio_file.tags:
            print(f'info: no tags found: {path}', file=stdout)
        else:
            print(f'info: printing all tags: {path}', file=stdout)

            for key, value in audio_file.tags.items():
                content = _value_to_string(key, value)

                if content is None:
                    print(f'warn: skipping tag with key: {key}', file=stderr)
                else:
                    print(f'{_key_to_canonical(key)} = {content}', file=stdout)

    else:
        for entry in entries:
            if not _is_valid_canonical(entry):
                print(f'warn: skipping invalid entry: {entry}', file=stderr)
            elif entry.is_empty():
                _remove_tag_canonical(audio_file.tags, entry)
            else:
                _add_tag_canonical(audio_file.tags, entry)

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

    parser = ArgumentParser(description='Add MP4 tags to a file.')

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
            mp4_addtag(file, tags)

        except Exception as exc:
            print(f'error: failed to add MP4 tags: {file}: {exc}', file=stderr)

            return 2

    return 0

if __name__ == '__main__':
    exit(main(sys_argv))
