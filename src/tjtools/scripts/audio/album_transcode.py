# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

from multiprocessing import Pool
from pathlib import Path
from subprocess import DEVNULL, CalledProcessError, run as prun
from sys import stderr, stdout

from magic import Magic

from ...common_util import StandardOutputProtector, path_walk
from ..rename_vfat import sanitize_vfat
from .flac_encode import is_flac


##########################################################################################
# Constants
##########################################################################################

_default_output = Path('/mnt/storage/transfer/fiio')


##########################################################################################
# Internal functions
##########################################################################################

def _usage(app: str) -> None:
    print(f'Usage: {app} [--tmpfs] <album directory> [<more album dirs>...]', file=stdout)


##########################################################################################
# Constants
##########################################################################################

'''
Ogg Vorbis encoding quality.
'''
_quality = 5.0


##########################################################################################
# Internal functions
##########################################################################################

def _transcode(input_path: Path, output_path: Path) -> None:
    '''
    Internal transcode helper.

    Arguments:
        input_path  - path of the input file
        output_path - path of the output file
    '''

    print(f'info: processing: {input_path.name}', file=stdout)

    p_args = (
        'oggenc',
        '--quiet',
        f'--quality={_quality}',
        f'--output={output_path.as_posix()}',
        input_path.as_posix()
    )

    try:
        p = prun(p_args, check=True, stdin=DEVNULL, capture_output=True, encoding='utf-8')

    except CalledProcessError as err:
        print(f'warn: transcoding failed: {input_path.name}: {err}')
        print(err.stdout)

def _mk_output_directory(base_path: Path, album_path: Path) -> Path:
    '''
    Make and create output directory.

    Arguments:
        base_path  - base path where directories are created
        album_path - path of the album
    '''

    name_sanitized = sanitize_vfat(album_path.name)

    output_dir = base_path / Path(name_sanitized.replace('(FLAC)', '(Vorbis)'))

    output_dir.mkdir(parents=True)

    return output_dir

def _mk_output_path(base_path: Path, entry_path: Path) -> Path:
    '''
    Make output path for an album file.

    Arguments:
        base_path  - base path where files are created
        name   - name of the album file
    '''

    entry_stem = entry_path.stem

    return base_path / Path(f'{sanitize_vfat(entry_stem)}.ogg')


##########################################################################################
# Functions
##########################################################################################

def album_transcode(tmpfs: bool, album_path: Path) -> None:
    '''
    Transcode FLAC album to Ogg Vorbis.

    Arguments:
        tmpfs      - use tmpfs as output
        album_path - path of the album
    '''

    if not album_path.is_dir():
        raise RuntimeError('album path is not a directory')

    mime = Magic(mime=True)

    output_dir = _mk_output_directory(Path('/tmp') if tmpfs else _default_output, album_path)

    print(f'info: transcoding album: {album_path} -> {output_dir}', file=stdout)

    pool_args = [(x, _mk_output_path(output_dir, x)) for x in path_walk(album_path) if is_flac(mime, x)]

    with Pool() as pool:
        pool.starmap(_transcode, pool_args)
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

    use_tmpfs = False

    if args[1] == '--tmpfs':
        if len(args) < 3:
            _usage(args[0])

            return 0

        use_tmpfs = True
        albums = args[2:]
    else:
        albums = args[1:]

    transcode_error = False

    with StandardOutputProtector():
        for album in albums:
            try:
                album_transcode(use_tmpfs, Path(album))

            except Exception as exc:
                print(f'warn: error occured while transcoding: {album}: {exc}', file=stderr)

                transcode_error = True

        if transcode_error:
            return 1

    return 0
