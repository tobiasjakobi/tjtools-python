# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

from argparse import ArgumentParser
from pathlib import Path
from subprocess import DEVNULL, run as prun
from sys import exit, stderr, argv as sys_argv

from mutagen import File as AudioFile


##########################################################################################
# Constants
##########################################################################################

_args_template = ('ffmpeg', '-hide_banner', '-nostdin', '-loglevel', 'quiet')


##########################################################################################
# Internal functions
##########################################################################################

def _hash(path: Path, hash_func: str) -> bytes:
    audio_file = AudioFile(path.as_posix())

    bps = audio_file.info.bits_per_sample

    if bps in (16, 32):
        codec_args = tuple()
    elif bps == 24:
        codec_args = ('-acodec', 'pcm_s24le')
    else:
        raise RuntimeError('invalid bits-per-sample')

    p_args = _args_template + ('-i', path.as_posix()) + codec_args + ('-f', 'hash', '-hash', hash_func, '-')

    p = prun(p_args, check=True, stdin=DEVNULL, capture_output=True, encoding='utf-8')

    output_lines = p.stdout.splitlines()
    if len(output_lines) != 1:
        raise RuntimeError('unexpected ffmpeg output')

    key, value = p.stdout.rstrip().split('=')
    if key != hash_func:
        raise RuntimeError('malformed ffmpeg output')

    return bytes.fromhex(value)


##########################################################################################
# Functions
##########################################################################################

def audio_compare(path_a: Path, path_b: Path) -> bool:
    '''
    Compare two audio files.
    
    Arguments:
        first_path  - path to audio file A
        second_path - path to audio file B

    Returns True if A and B match, and False otherwise.
    '''

    return _hash(path_a, hash_func='SHA512') == _hash(path_b, hash_func='SHA512')

def audio_md5(path: Path) -> bytes:
    '''
    Compute the MD5 of an audio file.

    Arguments:
        path - path to the audio file

    The computation of the MD5 is done over the raw sample data, i.e.
    without considering any file header, etc.
    '''

    return _hash(path, hash_func='MD5')


##########################################################################################
# Main
##########################################################################################

def main(args: list[str]) -> int:
    '''
    Main function.

    Arguments:
        args - list of string arguments from the CLI
    '''

    parser = ArgumentParser(description='Helper to compare and check audio files.')

    parser.add_argument('-m', '--mode', choices=('compare', 'md5'), help='Mode of operation', required=True)
    parser.add_argument('-f', '--file', help='File which we operate on', required=True)
    parser.add_argument('-o', '--other-file', help='Other file which we compare against')

    parsed_args = parser.parse_args(args[1:])

    if parsed_args.mode is not None and parsed_args.file is not None:
        file = Path(parsed_args.file)

        if not file.is_file():
            print(f'error: invalid input file: {file}', file=stderr)

            return 1

        if parsed_args.other_file is not None:
            other_file = Path(parsed_args.other_file)

            if not other_file.is_file():
                print(f'error: invalid other file: {other_file}', file=stderr)

                return 2
        else:
            other_file = None

        if parsed_args.mode == 'compare':
            if other_file is None:
                print('error: other file missing', file=stderr)

                return 3

            try:
                result = audio_compare(file, other_file)

            except Exception as exc:
                print(f'error: error comparing audio: {exc}', file=stderr)

                return 4
            
            if not result:
                print('error: audio does not match', file=stderr)

                return 5

        elif parsed_args.mode == 'md5':
            try:
                result = audio_md5(file)

            except Exception as exc:
                print(f'error: error computing MD5: {exc}', file=stderr)

                return 2

            print(f'info: audio MD5: {result.hex()}', file=stderr)

        else:
            print(f'error: invalid mode select: {parsed_args.mode}', file=stderr)

            return 1

    return 0

if __name__ == '__main__':
    exit(main(sys_argv))
