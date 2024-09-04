# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


from __future__ import annotations


##########################################################################################
# Imports
##########################################################################################

from dataclasses import dataclass
from enum import IntEnum
from getopt import GetoptError, getopt
from json import JSONDecodeError, loads as jloads
from multiprocessing import Pool
from pathlib import Path
from sys import stderr, stdout
from time import sleep
from urllib.request import HTTPError, Request, urlopen

from vc_addtag import TagEntry, vc_addtag
from vc_helper import gettag


##########################################################################################
# Constants
##########################################################################################

_ALBUM_URL_TEMPLATE = 'https://vgmdb.info/album/{0}?format=json'


##########################################################################################
# Internal functions
##########################################################################################

def _usage(app: str):
    print(f'Usage: {app} --album-id=<album ID> [--language=<language>] \
[--check-mode=<check mode>] [--verbose] [--help]', file=stdout)

    _msg = '''
Fetches tracklist data for a specific album ID from VGMdb and applies this data to the FLAC files in
the current directory.

\t--album-id|-a {VGMdb album ID}
\t--language|-l {Language of the tracklist, default is English}
\t--check-mode|-c {Checking mode used when applying tags to files, default is no-check}
\t--verbose|-v {Enable verbose output}
\t--help|-h {Display this help and exit}

We always check if the size of the tracklist matches the number of FLAC files found.

Available checking modes are:
- no-check {No further checks are done}
- file-prefix {the discnumber and tracknumber are derived from the prefix of the filename, the prefix
  needs to be NMM with N the discnumber, and MM the tracknumber}
- tag {the discnumber and tracknumber are extracted from the VorbisComment tags of the FLAC file}'''

    print(_msg, file=stdout)

def _parse_length(input_string: str) -> int:
    if input_string == 'Unknown':
        return None

    tmp = input_string.split(':', maxsplit=1)

    return int(tmp[0]) * 60 + int(tmp[1])

def _get_meta_from_filetags(path: Path) -> tuple[int, int]:
    '''
    Extract metadata from the tags associated with a Path object.

    Arguments:
        path - the Path object to inspect

    For further details see _get_meta_from_filename().
    '''

    try:
        values = gettag(path, ['discnumber', 'tracknumber'])

    except RuntimeError:
        return None

    if len(values) != 2:
        return None

    try:
        discnumber = None if values[0] is None else int(values[0])
        tracknumber = int(values[1])

    except (ValueError, TypeError):
        return None

    return (discnumber, tracknumber)

def _get_meta_from_filename(path: Path) -> tuple[int, int]:
    '''
    Extract metadata from the filename associated with a Path object.

    Arguments:
        path - the Path object to inspect

    The metadata is the disc and track number, which are returned as a tuple
    of integers. If the extraction fails, None is returned. If the metadata
    does not include the disc number, this entry is None.
    '''

    if len(path.name) < 4:
        return None

    tmp = path.name[0:4]

    if tmp[2] == ' ':
        has_disc = False
    elif tmp[3] == ' ':
        has_disc = True
    else:
        return None

    if has_disc:
        if not tmp[0:3].isdigit():
            return None

        return (int(tmp[0]), int(tmp[1:3]))

    if not tmp[0:2].isdigit():
        return None

    return (None, int(tmp[0:2]))


#########################################################################################
# Dataclass definitions
##########################################################################################

@dataclass(frozen=True)
class InternalName:
    '''
    Internal dataclass encoding a VGMdb (track) name object.
    '''

    language: str
    value: str

@dataclass(frozen=True)
class InternalTrack:
    '''
    Internal dataclass encoding a VGMdb track object.
    '''

    names: list[InternalName]
    length: int

    def get_name(self, language: str) -> str:
        '''
        Get the name for a given language.

        Arguments:
            language - the language to use

        Raises an exception if the language is not available.
        '''

        for name in self.names:
            if name.language == language:
                return name.value

        raise RuntimeError('name not found')

    @staticmethod
    def from_json(input_json: dict) -> InternalTrack:
        '''
        Create an internal track object from an JSON dictionary.

        Arguments:
            input_json - the input JSON dictionary
        '''

        names= [InternalName(k, v) for k, v in input_json['names'].items()]
        length = _parse_length(input_json['track_length'])

        return InternalTrack(names, length)

@dataclass(frozen=True)
class InternalDisc:
    '''
    Internal dataclass encoding a VGMdb disc object.
    '''

    length: int
    name: str
    tracks: list[InternalTrack]

    @staticmethod
    def from_json(input_json: dict) -> InternalDisc:
        '''
        Create an internal disc object from an JSON dictionary.

        Arguments:
            input_json - the input JSON dictionary
        '''

        length = _parse_length(input_json['disc_length'])
        name = input_json['name']
        tracks = [InternalTrack.from_json(arg) for arg in input_json['tracks']]

        return InternalDisc(length, name, tracks)

@dataclass
class TagDescriptor:
    '''
    Tag descriptor dataclass.

    Is derived from the VGMdb metadata and contains disc number, track number
    and the track title.

    Also has a link to the Path object to which the track title metadata
    should be applied. The disc number and track number are not applied, and
    only used to validate that we apply to the correct Path object.
    '''

    discnumber: int
    tracknumber: int
    title: str

    path: Path = None

    def pool_func(self) -> None:
        '''
        Internal function to apply the track title metadata.

        Is called by a multiprocessing pool object.
        '''

        if self.path is None:
            return

        print(f'info: Applying title to: {self.path}: {self.title}')
        vc_addtag(self.path, entries=[TagEntry('title', self.title)])


##########################################################################################
# Enumerator definitions
##########################################################################################

class CheckMode(IntEnum):
    '''
    Helper enumerator for the check mode.
    '''

    NoCheck    = 0
    FilePrefix = 1
    Tag        = 2

    @staticmethod
    def from_string(label: str) -> CheckMode:
        '''
        Create an enumerator from a string.
        '''

        if label == 'no-check':
            return CheckMode.NoCheck
        elif label == 'file-prefix':
            return CheckMode.FilePrefix
        elif label == 'tag':
            return CheckMode.Tag
        else:
            raise NotImplementedError


##########################################################################################
# Internal functions
##########################################################################################

def _read_url(url: str) -> str:
    '''
    Read an URL an return the content as string.
    '''

    req_retries = 20
    req_data = None

    while req_data is None and req_retries != 0:
        try:
            req = Request(url)
            with urlopen(req) as response:
                req_data = response.read()

        except HTTPError as err:
            if err.code != 503:
                raise RuntimeError(f'failed to read URL: {err}')

        req_retries -= 1
        sleep(0.5)

    if req_data is None:
        raise RuntimeError('timeout while reading URL')

    return req_data


##########################################################################################
# Main
##########################################################################################

def main(args: list[str]) -> int:
    '''
    Main function.
    '''

    getopt_largs = ('help', 'verbose', 'album-id', 'language', 'check-mode')

    try:
        opts, oargs = getopt(args[1:], "hva:l:c:", getopt_largs)

    except GetoptError as err:
        print(err, file=stderr)
        _usage(args[0])

        return 1

    verbose = False
    album_id = None
    language = None
    check_mode = None

    for _o, _a in opts:
        if _o in ('-h', '--help'):
            _usage(args[0])
            return 0
        elif _o in ('-v', '--verbose'):
            verbose = True
        elif _o in ('-a', '--album-id'):
            try:
                album_id = int(_a)

            except ValueError as err:
                print(f'error: invalid album ID: {_a}: {err}', file=stderr)

                return 2
        elif _o in ('-l', '--language'):
            if len(_a) <= 1:
                print(f'error: invalid language: {_a}', file=stderr)

                return 3

            language = _a
        elif _o in ('-c', '--check-mode'):
            if _a not in ('no-check', 'file-prefix', 'tag'):
                print(f'error: invalid check mode: {_a}', file=stderr)

                return 4

            check_mode = CheckMode.from_string(_a)

    if len(oargs) != 0:
        print(f'error: excessive arguments found: {oargs}', file=stderr)

        return 5

    if album_id is None:
        print('error: album ID argument missing', file=stderr)

        return 6

    if language is None:
        language = 'English'

        print(f'info: using default language: {language}', file=stdout)

    if check_mode is None:
        check_mode = CheckMode.NoCheck

        print(f'info: using default check mode: {check_mode.name}', file=stdout)

    album_url = _ALBUM_URL_TEMPLATE.format(album_id)

    try:
        raw = _read_url(album_url)

    except Exception as exc:
        print(f'error: failed to fetch album URL: {exc}', file=stderr)

        return 7

    try:
        album = jloads(raw)

    except JSONDecodeError as err:
        print(f'error: failed to decode album JSON: {err}', file=stderr)

        return 8

    if not 'discs' in album:
        print('error: no discs found in album', file=stderr)

        return 9

    if 'name' in album and verbose:
        album_name = album['name']
        print(f'info: album ID {album_id} has name: {album_name}', file=stdout)

    try:
        discs = [InternalDisc.from_json(arg) for arg in album['discs']]

    except (KeyError, ValueError) as err:
        print(f'error: failed to parse discs: {err}', file=stderr)

        return 10

    first_disc = discs[0]

    language_available = False

    print('info: available languages:', file=stdout)
    for name in first_disc.tracks[0].names:
        if language == name.language:
            language_available = True

        print(f'\t{name.language}', file=stdout)

    if not language_available:
        print(f'error: requested language not available: {language}', file=stderr)

        return 11

    '''
    Compute the total number of tracks over all discs. We need this value for
    some validation.
    '''
    total_tracks = sum([len(arg.tracks) for arg in discs])

    if verbose:
        print('info: statistics:',  file=stdout)
        print(f'\tnumber of discs: {len(discs)}')
        print(f'\tnumber of tracks: {total_tracks}')

    available_files = [arg for arg in Path().iterdir() if arg.is_file() and arg.suffix == '.flac']

    if len(available_files) != total_tracks:
        print(f'error: total number of tracks does not match available files {total_tracks}: {len(available_files)}', file=stderr)

        return 12

    tag_descriptors: list[TagDescriptor] = list()

    try:
        for discnumber, disc in enumerate(discs):
            for tracknumber, track in enumerate(disc.tracks):
                desc = TagDescriptor(
                    discnumber + 1,
                    tracknumber + 1,
                    track.get_name(language),
                )

                tag_descriptors.append(desc)

    except RuntimeError as err:
        print(f'error: failed to create tag descriptors: {err}', file=stderr)

        return 13

    if check_mode == CheckMode.NoCheck:
        for _t, _f in zip(tag_descriptors, sorted(available_files)):
            _t.path = _f

    elif check_mode in (CheckMode.FilePrefix, CheckMode.Tag):
        is_multi_disc = len(discs) != 1

        if verbose:
            print('info: handling {} album'.format('multi-disc' if is_multi_disc else 'single-disc'), file=stdout)

        get_meta = _get_meta_from_filename if check_mode == CheckMode.FilePrefix else _get_meta_from_filetags

        for arg in available_files:
            _m = get_meta(arg)
            if _m is None:
                print(f'warn: skipping file with unknown prefix: {arg}', file=stdout)
                continue

            if _m[0] is None and is_multi_disc:
                print(f'warn: skipping file without disc prefix: {arg}', file=stdout)
                continue

            if is_multi_disc:
                found_desc = False
                for _t in tag_descriptors:
                    if _t.discnumber == _m[0] and _t.tracknumber == _m[1]:
                        _t.path = arg
                        found_desc = True
                        break

                if not found_desc:
                    print(f'warn: skipping file without descriptor: {arg}', file=stdout)
            else:
                found_desc = False
                for _t in tag_descriptors:
                    if _t.tracknumber == _m[1]:
                        _t.path = arg
                        found_desc = True
                        break

                if not found_desc:
                    print(f'warn: skipping file without descriptor: {arg}', file=stdout)

    else:
        assert False, 'not implemented'

    with Pool() as pool:
        pool.map(TagDescriptor.pool_func, tag_descriptors)
        pool.close()
        pool.join()

    return 0
