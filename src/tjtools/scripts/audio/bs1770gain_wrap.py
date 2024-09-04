# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


from __future__ import annotations


##########################################################################################
# Imports
##########################################################################################

from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path
from subprocess import DEVNULL, CalledProcessError, run as prun
from sys import stderr
from xml.dom.minidom import Element as XMLElement, parseString as xml_parse

from magic import Magic

from ...id3_addtag import is_mp3, id3_addtag
from ...mp4_addtag import mp4_addtag
from ...vc_addtag import TagEntry, vc_addtag


##########################################################################################
# Constants
##########################################################################################

_bs1770_template = (
    'bs1770gain',
    '--integrated',
    '--range',
    '--truepeak',
    '--ebu',
    '--suppress-progress',
    '--xml'
)


##########################################################################################
# Class definitions
##########################################################################################

@dataclass(frozen=True)
class R128Tuple:
    gain: str
    peak: str
    range: str

    @staticmethod
    def from_track(track: XMLElement) -> R128Tuple:
        '''
        Create a R128 tuple from a track XML element.

        Arguments:
            track - the track XML element to use
        '''

        for arg in track.childNodes:
            if arg.nodeName == 'integrated':
                _i = arg
            elif arg.nodeName == 'range':
                _r = arg
            elif arg.nodeName == 'true-peak':
                _t = arg

        try:
            return R128Tuple(
                _i.getAttribute('lu'),
                _t.getAttribute('amplitude'),
                _r.getAttribute('lra')
            )

        except NameError:
            return None


##########################################################################################
# Functions
##########################################################################################

def bs1770gain(path: Path) -> None:
    '''
    Perform a bs1770gain scan of the audio files in a given directory.

    Arguments:
        path - path to the directory which we should process
    '''

    if not path.is_dir():
        raise RuntimeError(f'path is not a directory: {path}')

    mime = Magic(mime=True)

    p_args = _bs1770_template + (path.as_posix(),)

    try:
        p = prun(p_args, check=True, stdin=DEVNULL, capture_output=True, encoding='utf-8')

    except CalledProcessError as err:
        raise RuntimeError(f'bs1770gain CLI failed: {err}') from err

    try:
        dom_tree = xml_parse(p.stdout)
        for n in dom_tree.childNodes:
            if n.nodeName == 'bs1770gain':
                main_node = n

        for n in main_node.childNodes:
            if n.nodeName == 'album' and n.getAttribute('folder') == path.name:
                album_node = n

        tracks = album_node.getElementsByTagName('track')
        summary = main_node

    except Exception as exc:
        raise RuntimeError(f'bs1770gain XML parsing failed: {exc}') from exc

    album_info = R128Tuple.from_track(summary)
    if album_info is None:
        raise RuntimeError('bs1770gain album summary missing')

    for track in tracks:
        if not track.hasAttribute('file'):
            print(f'warn: skipping track with missing file attribute: {track}', file=stderr)

            continue

        track_info = R128Tuple.from_track(track)
        if track_info is None:
            print(f'warn: skipping track with invalid track info: {track}', file=stderr)

            continue
 
        track_path = path / Path(track.getAttribute('file'))
        if not track_path.is_file():
            print(f'warn: skipping non-existing file: {track_path.name}', file=stderr)

            continue

        file_type = mime.from_file(track_path.as_posix())
        if file_type in ('video/mp4', 'audio/x-m4a'):
            addtag_func = mp4_addtag
        elif file_type in ('audio/ogg', 'audio/flac'):
            addtag_func = vc_addtag
        elif file_type == 'audio/mpeg' or is_mp3(track_path):
            addtag_func = id3_addtag
        else:
            print(f'warn: skipping file with unsupported type: {track_path.name}: {file_type}', file=stderr)

            continue

        tag_entries = [
            TagEntry('replaygain_algorithm', 'EBU R128'),
            TagEntry('replaygain_reference_loudness', '-23.00 LUFS'),
            TagEntry('replaygain_track_gain', f'{track_info.gain} dB'),
            TagEntry('replaygain_track_peak', f'{track_info.peak}'),
            TagEntry('replaygain_track_range', f'{track_info.range} dB'),
            TagEntry('replaygain_album_gain', f'{album_info.gain} dB'),
            TagEntry('replaygain_album_peak', f'{album_info.peak}'),
            TagEntry('replaygain_album_range', f'{album_info.range} dB'),
        ]

        try:
            addtag_func(track_path, tag_entries)

        except Exception as exc:
            print(f'error: failed to write tags: {track_path.name}: {exc}', file=stderr)

            continue


##########################################################################################
# Main
##########################################################################################

def main(args: list[str]) -> int:
    '''
    Main function.

    Arguments:
        args - list of string arguments from the CLI
    '''

    parser = ArgumentParser(description='bs1770gain wrapper for scanning and tagging audio files in a directory.')

    parser.add_argument('-d', '--directory', required=True, help='Directory where we want to scan')

    parsed_args = parser.parse_args(args[1:])

    if parsed_args.directory is not None:
        work_dir = Path(parsed_args.directory)

        try:
            bs1770gain(work_dir)

        except Exception as exc:
            print(f'error: failed to perform bs1770gain scan: {work_dir.name}: {exc}', file=stderr)

            return 1

    return 0
