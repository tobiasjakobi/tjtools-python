# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

from multiprocessing import Pool
from pathlib import Path
from shutil import move
from subprocess import DEVNULL, CalledProcessError, run as prun
from sys import stderr, stdout
from tempfile import TemporaryDirectory

from magic import Magic

from ...common_util import StandardOutputProtector, path_walk
from ...audio_compare import audio_compare
from ...flac_md5 import flac_md5
from .flac_encode import flac_encode, is_flac
from .vc_copytags import vc_copytags


##########################################################################################
# Internal functions
##########################################################################################

def _usage(app: str) -> None:
    print(f'Usage: {app} <file or directory item> [<another item>...]', file=stdout)

def _decode_verify(input: Path, output: Path) -> None:
    '''
    Decode a FLAC file with additional verification.

    Arguments:
        input  - the input path
        output - the output path

    This first tries to decode the file with the reference decoder and standard settings.
    If this fails, the it verifies the embedded MD5 signature using the ffmpeg decoder.
    If the signature is valid, it decodes the file again with the reference decode, but this
    time ignoring any errors. The decoding result is then compared with the input file
    using the ffmpeg decoder.
    '''

    decode_fail = False

    try:
        p_args = ('flac', '--decode', '--totally-silent', f'--output-name={output.as_posix()}', input.as_posix())
        prun(p_args, check=True, stdin=DEVNULL, capture_output=True, encoding='utf-8')

    except CalledProcessError:
        decode_fail = True

    if not decode_fail:
        return

    if not flac_md5(input):
        raise RuntimeError(f'MD5 signature invalid: {input}')

    err_msg = None

    try:
        p_args = ('flac', '--decode', '--decode-through-errors', '--totally-silent', f'--output-name={output.as_posix()}', input.as_posix())
        prun(p_args, check=True, stdin=DEVNULL, capture_output=True, encoding='utf-8')

    except CalledProcessError as err:
        err_msg = f'{err}: {err.stderr}'

    if not output.is_file() or not audio_compare(input, output):
        output.unlink(missing_ok=True)

        raise RuntimeError(f'decoding failed: {input}: {err_msg}')

def _re_encode(path: Path, verbose: bool) -> None:
    '''
    Internal recoding helper.

    Arguments:
        path - path to input file
    '''

    if verbose:
        print(f'info: processing: {path.name}', file=stdout)

    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        decoding_output = tmp_path / 'output.wav'
        encoding_output = tmp_path / 'output.flac'

        try:
            _decode_verify(path, decoding_output)
            flac_encode(decoding_output, False)
            vc_copytags(path, encoding_output)

        except Exception as exc:
            raise RuntimeError(f're-encode failed: {path}: {exc}') from exc

        move(encoding_output.as_posix(), path.as_posix())


##########################################################################################
# Functions
##########################################################################################

def reflac(path: Path, verbose: bool) -> None:
    '''
    Recode a single FLAC file.

    Arguments:
        path    - path to file which we want to re-encode
        verbose - enable verbose output?
    '''

    if not path.is_file():
        raise RuntimeError(f'path is not a file: {path}')

    mime = Magic(mime=True)
    if not is_flac(mime, path):
        raise RuntimeError('invalid file content (expected FLAC)')

    if verbose:
        print(f'info: recoding file: {path}', file=stdout)

    _re_encode(path, verbose=True)

def reflac_dir(path: Path, verbose: bool) -> None:
    '''
    Recode all FLAC files in a directory.

    Arguments:
        path    - path to directory which we want to re-encode
        verbose - enable verbose output?
    '''

    if not path.is_dir():
        raise RuntimeError(f'path is not a directory: {path}')

    mime = Magic(mime=True)

    if verbose:
        print(f'info: re-encoding directory: {path}', file=stdout)

    pool_args = [(x, True) for x in path_walk(path) if is_flac(mime, x)]

    with Pool() as pool:
        pool.starmap(_re_encode, pool_args)
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

    recoding_error = False

    with StandardOutputProtector():
        for arg in args[1:]:
            path = Path(arg)

            if not path.exists():
                print(f'warn: skipping non-existing path: {path}', file=stderr)

                continue

            try:
                if path.is_dir():
                    reflac_dir(path, verbose=True)
                elif path.is_file():
                    reflac(path, verbose=True)
                else:
                    raise RuntimeError(f'invalid argument type: {path.stat().st_mode}')

            except Exception as exc:
                print(f'warn: error occured while recoding: {path}: {exc}', file=stderr)

                recoding_error = True

    if recoding_error:
        return 1

    return 0
