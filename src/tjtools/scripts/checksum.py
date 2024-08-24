# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

from dataclasses import dataclass
from getopt import getopt, GetoptError
from hashlib import file_digest
from multiprocessing import Pool
from os.path import basename, dirname, exists, isdir, isfile, realpath, splitext, join as pjoin
from os import listdir, rename, remove
from re import compile as rcompile
from subprocess import DEVNULL, CalledProcessError, run as prun
from sys import stderr, stdout
from tempfile import NamedTemporaryFile


##########################################################################################
# Class definitions
##########################################################################################

@dataclass(frozen=True)
class _SHATuple:
    filesize: int
    hash: bytes
    filename: str


##########################################################################################
# Internal functions
##########################################################################################

def _usage(app: str):
    print(f'Usage: {app} --sha-scan|--sha-check|--sfv-check|--sfv-migrate', file=stdout)

    msg = '''
\t --sha-scan <directory>
\t --sha-check <SHA checksum file>
\t --sfv-check <SFV checksum file>
\t --sfv-migrate <SFV checksum file>'''

    print(msg, file=stdout)

def _filter(arg: str) -> bool:
    filters = ('.m3u', '.sha', '.sfv', '.md5')

    split_arg = splitext(arg)

    if len(split_arg) < 2:
        return False

    return split_arg[1] in filters

def _locate_m3u(arg: str) -> str:
    for f in listdir(arg):
        split_f = splitext(f)

        if len(split_f) >= 2 and split_f[1] == '.m3u':
            return f

    return None

def _locate_md5(arg: str) -> str:
    for f in listdir(arg):
        split_f = splitext(f)

        if len(split_f) >= 2 and split_f[1] == '.md5':
            return f

    return None

def _get_filebase(arg):
    m3u = _locate_m3u(arg)

    if m3u is None:
        base = basename(arg)
        index = 1

        while True:
            filebase = f'00 {base} ({index}).sha'

            if not exists(pjoin(arg, filebase)):
                break

            index = index + 1

        print(f'info: no M3U found: using filename: {filebase}', file=stdout)
    else:
        filebase = splitext(m3u)[0] + '.sha'

    return filebase

def _get_fileprefix(arg, extension):
    split_arg = splitext(arg)

    if split_arg[1] == extension:
        return split_arg[0]

    return None

def _parse_sfv(arg) -> list:
    checksum_re = rcompile('\s*(.+\S)\s+(\S+)')
    comment_re = rcompile('\s*;.*')

    def match_sfv(arg):
        if len(arg) != 0 and not comment_re.match(arg):
            res = checksum_re.findall(arg)

            if len(res) == 1:
                return res[0]

    with open(arg, encoding='utf-8') as f:
        sfv = [i for i in map(match_sfv, f.read().splitlines()) if i is not None]

    return sfv

def _parse_sha_line(arg: str) -> _SHATuple:
    tmp = arg.strip().split(' ', maxsplit=1)

    if not tmp[0].isdigit():
        raise RuntimeError(f'malformed SHA line: {tmp[0]}')

    filesize = int(tmp[0])

    tmp = tmp[1].strip().split(' ', maxsplit=1)

    try:
        hash_bytes = bytes.fromhex(tmp[0])

    except Exception as exc:
        raise RuntimeError(f'malformed SHA line: {tmp[0]}: {exc}') from exc

    filename = tmp[1].strip()

    return _SHATuple(filesize, hash_bytes, filename)

def _parse_sha(arg: str) -> list[_SHATuple]:
    with open(arg, encoding='utf-8') as f:
        raw_lines = f.read().splitlines()

    return [_parse_sha_line(line) for line in raw_lines]

def _try_singlefile(arg):
    filters = ('.sfv', '.md5')

    working = dirname(arg)

    split_base = splitext(basename(arg))
    if len(split_base) != 2:
        return None

    sfv = _parse_sfv(arg)
    if len(sfv) != 1:
        print('error: singlefile check failed: multiple entries in SFV', file=stderr)

        return None

    ref_split = splitext(sfv[0][0])
    if ref_split[0] != split_base[0]:
        print('error: singlefile check failed: filename mismatch', file=stderr)

        return None

    ref_found = False
    filelist = []

    for f in listdir(working):
        split_f = splitext(f)

        if len(split_f) != 2 or split_f[0] != split_base[0]:
            continue

        if split_f[1] in filters:
            filelist.append(f)
        elif f == sfv[0][0]:
            ref_found = True
            filelist.append(f)

    if not ref_found:
        return None

    return filelist

def _sha_check_internal(base_dir: str, t: _SHATuple) -> None:
    with open(pjoin(base_dir, t.filename), mode='rb') as f:
        h = file_digest(f, 'sha256')
        filesize = f.tell()

    if h.digest() != t.hash:
        raise RuntimeError(f'hash mismatch for: {t.filename}')

    if filesize != t.filesize:
        raise RuntimeError(f'filesize mismatch for: {t.filename}')


##########################################################################################
# Functions
##########################################################################################

def sha_scan(arg, out, external_list) -> int:
    input_directory = arg.rstrip('/')

    if not isdir(input_directory):
        print(f'error: directory not found: {input_directory}', file=stderr)

        return 1

    input_path = realpath(input_directory)

    if out is None:
        filebase = _get_filebase(input_path)
        sha = pjoin(input_path, filebase)

        if exists(sha):
            print(f'error: directory already has a checksum: {input_directory}', file=stderr)

            return 2

    filelist = []

    if external_list != None:
        dir_listing = external_list
    else:
        dir_listing = listdir(input_path)

    for f in dir_listing:
        if not _filter(f):
            filelist.append(f)

    if not filelist:
        print('error: no files found to check', file=stderr)

        return 3

    filelist.sort()

    if out is None:
        output = open(sha, mode='w', encoding='utf-8')
    else:
        output = out

    p_args = ['sha256deep', '-b', '-z'] + filelist

    try:
        prun(p_args, cwd=input_path, check=True, stdin=DEVNULL, stdout=output)

    except CalledProcessError as err:
        print(f'error: sha256deep returned with error: {err.returncode}', file=stderr)

        return 4

    finally:
        if out is None:
            output.close()

    return 0

def sha_check(arg) -> int:
    input_file = arg

    if not isfile(input_file):
        print(f'error: sha_check: checksum file not found: {input_file}', file=stderr)

        return 1

    try:
        sha_tuples = _parse_sha(input_file)

    except Exception as exc:
        print(f'error: sha_check: checksum parsing failed: {exc}', file=stderr)

        return 2

    base_directory = dirname(input_file)
    if len(base_directory) == 0:
        base_directory = '.'

    internal_args = [(base_directory, arg) for arg in sha_tuples]

    try:
        with Pool() as pool:
            pool.starmap(_sha_check_internal, internal_args)
            pool.close()
            pool.join()

    except Exception as exc:
        print(f'error: sha_check: check failure: {exc}', file=stderr)

        return 3

    for f in listdir(base_directory):
        if _filter(f):
            continue

        filename_matches = [arg for arg in sha_tuples if arg.filename == f]

        if len(filename_matches) != 1:
            print(f'error: sha_check: file without checksum: {f}', file=stderr)

            return 4

    bytes_total = 0
    for arg in sha_tuples:
        bytes_total += arg.filesize

    print(f'info: successfully checked {len(sha_tuples)} files, {bytes_total} bytes total', file=stdout)

    return 0

def sfv_check(arg) -> int:
    input_file = arg

    if not isfile(input_file):
        print(f'error: sfv_check: checksum file not found: {input_file}', file=stderr)

        return 1

    input_path = realpath(input_file)

    filebase = basename(input_path)
    working = dirname(input_path)

    p_args = ('cksfv', '-q', '-f', filebase)

    try:
        prun(p_args, cwd=working, check=True, stdin=DEVNULL)

    except CalledProcessError as err:
        print(f'error: sfv_check: cksfv returned with error: {err.returncode}', file=stderr)

        return 2

    return 0

def md5_check(arg) -> int:
    input_file = arg

    if not isfile(input_file):
        print(f'error: md5_check: checksum file not found: {input_file}', file=stderr)

        return 1

    input_path = realpath(input_file)

    filebase = basename(input_path)
    working = dirname(input_path)

    filelist = list()
    for f in listdir(working):
        if not _filter(f):
            filelist.append(f)

    if not filelist:
        print('error: md5_check: no files found to check', file=stderr)

        return 2

    filelist.sort()

    p_args = ['md5deep', '-s', '-x', filebase] + filelist

    try:
        prun(p_args, cwd=working, check=True, stdin=DEVNULL)

    except CalledProcessError as err:
        print(f'error: md5_check: process returned with error: {err.returncode}', file=stderr)

        return 3

    return 0

def sfv_migrate(arg) -> int:
    input_file = arg

    retval = sfv_check(input_file)
    if retval != 0:
        print(f'error: sfv_migrate: initial check failed: {input_file}', file=stderr)

        return 1

    input_path = realpath(input_file)

    filebase = basename(input_path)
    working = dirname(input_path)

    fileprefix = _get_fileprefix(filebase, '.sfv')
    if fileprefix is None:
        print(f'error: sfv_migrate: failed to find file prefix: {input_file}', file=stderr)

        return 2

    m3u_path = pjoin(working, fileprefix + '.m3u')
    if not isfile(m3u_path):
        filelist = _try_singlefile(input_path)

        if filelist is None:
            print(f'error: sfv_migrate: no M3U could be located: {working}', file=stderr)

            return 3
    else:
        filelist = None

    md5_path = pjoin(working, fileprefix + '.md5')
    has_md5 = False
    if isfile(md5_path):
        has_md5 = True
        retval = md5_check(md5_path)
        if retval != 0:
            print(f'error: sfv_migrate: MD5 check failed for: {md5_path}', file=stderr)

            return 4

    sha_path = pjoin(working, fileprefix + '.sha')
    if exists(sha_path):
        print(f'error: directory already has a SHA checksum: {working}', file=stderr)

        return 5

    sha_temp = NamedTemporaryFile(mode='w+', prefix='/tmp/', delete=True)

    retval = sha_scan(working, sha_temp, filelist)
    if retval != 0:
        print(f'error: aborting migration since SHA scan failed: {working}', file=stderr)

        return 6

    sha_temp.seek(0)

    try:
        with open(input_file, mode='w', encoding='utf-8') as output:
            output.write(sha_temp.read())

    except OSError as msg:
        print(f'error: failed to write the SHA result: {input_file}: {msg}', file=stderr)

        return 7

    sha_temp.close()

    try:
        rename(input_path, sha_path)
        if has_md5:
            remove(md5_path)

    except OSError as msg:
        print(f'error: failed to rename: {input_file}: {msg}', file=stderr)

        return 8

    return 0


##########################################################################################
# Main
##########################################################################################

def main(args: list[str]) -> int:
    '''
    Main function.

    Arguments:
        args - list of string arguments from the CLI
    '''

    getopt_largs = ('help', 'sha-scan', 'sha-check', 'sfv-migrate', 'sfv-check')

    try:
        opts, oargs = getopt(args[1:], 'hscmf', getopt_largs)

    except GetoptError as err:
        print(f'error: getopt parsing failed: {err}', file=stderr)
        _usage(args[0])

        return 1

    checksum_mode = None

    for o, a in opts:
        if checksum_mode != None:
            print('error: multiple modes selected', file=stderr)

            return 2

        if o in ('-h', '--help'):
            _usage(args[0])

            return 0
        elif o in ('-s', '--sha-scan'):
            checksum_mode = 'scan'
        elif o in ('-c', '--sha-check'):
            checksum_mode = 'check'
        elif o in ('-f', '--sfv-check'):
            checksum_mode = 'sfv'
        elif o in ('-m', '--sfv-migrate'):
            checksum_mode = 'migrate'
        else:
            raise RuntimeError('unhandled option')

    if checksum_mode is None:
        print('error: unknown or no mode selected', file=stderr)

        return 3

    if len(oargs) != 1:
        print('error: checksum file / directory argument invalid or missing', file=stderr)

        return 4

    if checksum_mode == 'scan':
        retval = sha_scan(oargs[0], None, None)
    elif checksum_mode == 'check':
        retval = sha_check(oargs[0])
    elif checksum_mode == 'sfv':
        retval = sfv_check(oargs[0])
    elif checksum_mode == 'migrate':
        retval = sfv_migrate(oargs[0])

    if retval != 0:
        print(f'error: checksum {checksum_mode} failed with return value {retval}', file=stderr)

        return 5

    return 0
