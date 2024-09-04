# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

from multiprocessing import Pool
from pathlib import Path
from shutil import move
from subprocess import DEVNULL, run as prun
from sys import stderr, stdout
from tempfile import TemporaryDirectory

from magic import Magic

from ...audio_compare import audio_compare
from ...common_util import StandardOutputProtector, path_walk


##########################################################################################
# Constants
##########################################################################################

'''
Distance (in seconds) between seekpoints that are placed in newly encoded FLAC files.
'''
_seekpoint_distance = 25


##########################################################################################
# Internal functions
##########################################################################################

def _usage(app: str) -> None:
    print(f'Usage: {app} <file or directory item> [<another item>...]', file=stdout)

def _encode(path: Path, verbose: bool) -> None:
    '''
    Internal encoding helper.

    Arguments:
        path    - path to input file
        verbose - enable verbose output?
    '''

    path_stem = path.stem
    output_path = path.parent / Path(f'{path_stem}.flac')

    if output_path.exists():
        raise RuntimeError(f'output file already exists: {output_path}')

    if verbose:
        print(f'info: processing: {path.name}', file=stdout)

    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        encoding_output = tmp_path / Path('output.flac')
        reference_output = tmp_path / Path('reference.wav')

        flake_args = ('flake', '-q', '-12', path.as_posix(), '-o', encoding_output.as_posix())
        prun(flake_args, check=True, stdin=DEVNULL, capture_output=True, encoding='utf-8')

        decode_args = ('flac', '--decode', '--silent', f'--output-name={reference_output.as_posix()}', encoding_output.as_posix())
        prun(decode_args, check=True, stdin=DEVNULL, capture_output=True, encoding='utf-8')

        if not audio_compare(path, reference_output):
            raise RuntimeError('mismatch between original source and reference decoding')

        '''
        flake doesn't add a seektable by default, so add one here.
        '''
        seekpoint_args = ('metaflac', f'--add-seekpoint={_seekpoint_distance}s', encoding_output.as_posix())
        prun(seekpoint_args, check=True, stdin=DEVNULL, capture_output=True, encoding='utf-8')

        move(encoding_output.as_posix(), output_path.as_posix())


##########################################################################################
# Functions
##########################################################################################

def is_wav(m: Magic, path: Path) -> bool:
    '''
    Simple helper to check if a file is WAV.

    Arguments:
        m    - magic object to check MIME type
        path - path of the file to check
    '''

    if path.suffix != '.wav':
        return False

    if m.from_file(path.as_posix()) != 'audio/x-wav':
        return False

    return True

def is_flac(m: Magic, path: Path) -> bool:
    '''
    Simple helper to check if a file is FLAC.

    Arguments:
        m         - magic object to check MIME type
        file_path - path of the file to check
    '''

    if path.suffix != '.flac':
        return False

    if m.from_file(path.as_posix()) != 'audio/flac':
        return False

    return True

def flac_encode(path: Path, verbose: bool) -> None:
    '''
    Encode a single WAV file to FLAC.

    Arguments:
        path    - path to file which we want to encode
        verbose - enable verbose output?

    Encoding is done using the flake encoder. After encoding the resulting file is decoded
    with the reference decoder and compared against the original file.
    '''

    if not path.is_file():
        raise RuntimeError(f'path is not a file: {path}')

    mime = Magic(mime=True)
    if not is_wav(mime, path):
        raise RuntimeError('invalid file content (expected WAV)')

    if verbose:
        print(f'info: encoding file: {path}', file=stdout)

    _encode(path, False)

def flac_encode_dir(path: Path, verbose: bool) -> None:
    '''
    Encode all WAV files in a directory to FLAC.

    Arguments:
        path    - path of directory which we want to encode
        verbose - enable verbose output?
    '''

    if not path.is_dir():
        raise RuntimeError(f'path is not a directory: {path}')

    mime = Magic(mime=True)

    if verbose:
        print(f'info: encoding directory: {path}', file=stdout)

    pool_args = [(x, True) for x in path_walk(path) if is_wav(mime, x)]

    with Pool() as pool:
        pool.starmap(_encode, pool_args)
        pool.close()
        pool.join()


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
        _usage(args[0])

        return 0

    encoding_error = False

    with StandardOutputProtector():
        for arg in args[1:]:
            path = Path(arg)

            if not path.exists():
                print(f'warn: skipping non-existing path: {path}', file=stderr)

                continue

            try:
                if path.is_dir():
                    flac_encode_dir(path, True)
                elif path.is_file():
                    flac_encode(path, True)
                else:
                    raise RuntimeError(f'invalid argument type: {path.stat().st_mode}')

            except Exception as exc:
                print(f'warn: error occured while encoding: {path}: {exc}', file=stderr)

                encoding_error = True

    if encoding_error:
        return 1
    
    return 0
