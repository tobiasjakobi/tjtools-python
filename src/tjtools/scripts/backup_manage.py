# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


'''
TODOs:
- prevent certain actions when user is not root
- expire backups when older than some treshold
'''


##########################################################################################
# Imports
##########################################################################################

import sys

from json import dump as jdump, load as jload
from os.path import abspath, exists, expanduser, isfile, join as pjoin
from os import listdir, remove, umask
from re import compile as rcompile
from socket import gethostname
from subprocess import run as prun
from tempfile import NamedTemporaryFile
from time import asctime, localtime, time


##########################################################################################
# Constants
##########################################################################################

_backup_prefix = expanduser('~/local/backup/')
_gdrive_prefix = expanduser('~/local/gdrive/')
_config_path = _backup_prefix + 'config.json'

_default_config = {
    'files': [],
    'prefix': '',
    'timestamp': 0,
    'includes': []
}


##########################################################################################
# Internal functions
##########################################################################################

def _usage(app: str):
    print(f'Usage: {app}', file=sys.stdout)

    print('\t --add-file|--remove-file <file>', file=sys.stdout)
    print('\t --status <file>', file=sys.stdout)
    print('\t --dump-files|--clean-files', file=sys.stdout)
    print('\t --backup-files', file=sys.stdout)
    print('\t --backup-status', file=sys.stdout)
    print('\t --backup-clean <days>', file=sys.stdout)
    print('\t --sync', file=sys.stdout)

def _make_default_config():
    print('info: writing (empty) standard config', file=sys.stdout)

    with open(_config_path, mode='w') as f:
        jdump(_default_config, fp=f, indent=4)

def _verify_config(cfg: dict) -> bool:
    for k in ('files', 'prefix', 'timestamp', 'includes'):
        if k not in cfg:
            return False

    return True

def _verify_include(cfg: dict) -> bool:
    for k in ('files', 'prefix'):
        if k not in cfg:
            return False

    return True

def _read_config(path) -> dict:
    with open(path, mode='r') as f:
        cfg = jload(f)

    return cfg

def _read_includes(cfg: dict) -> list:
    inc_data = []

    for inc in cfg.get('includes'):
        inc_cfg = _read_config(pjoin(inc, 'local/backup/config.json'))

        if not _verify_include(inc_cfg):
            print('error: read-includes: config verify failed', file=sys.stderr)

            return None

        prefix = inc_cfg.get('prefix')

        for file in inc_cfg.get('files'):
            inc_data.append(f'{prefix}/{file}')

    return inc_data

def write_config(path: str, cfg: dict):
    with open(path, mode='w') as f:
        jdump(cfg, fp=f, indent=4)


##########################################################################################
# Functions
##########################################################################################

def add_file(args: list) -> int:
    if len(args) != 1:
        print('error: add-file: wrong number of arguments', file=sys.stderr)

        return 1

    path = abspath(args[0])

    if not isfile(path):
        print('error: add-file: file not found', file=sys.stderr)

        return 2

    cfg = _read_config(_config_path)

    if not _verify_config(cfg):
        print('error: add-file: config verify failed', file=sys.stderr)

        return 3

    prefix = cfg.get('prefix')

    if prefix != '/':
        prefix += '/'

    if not path.startswith(prefix):
        print('error: add-file: file not in prefix', file=sys.stderr)

        return 4

    trackpath = path[len(prefix):]

    if trackpath in cfg['files']:
        print('error: add-file: file already tracked', file=sys.stderr)

        return 5

    cfg.get('files').append(trackpath)
    write_config(_config_path, cfg)

    print(f'info: add-file: now tracking: {trackpath}', file=sys.stdout)

    return 0

def remove_file(args: list) -> int:
    if len(args) != 1:
        print('error: remove-file: wrong number of arguments', file=sys.stderr)

        return 1

    path = abspath(args[0])

    cfg = _read_config(_config_path)

    if not _verify_config(cfg):
        print('error: remove-file: config verify failed', file=sys.stderr)

        return 2

    prefix = cfg.get('prefix')

    if prefix != '/':
        prefix += '/'

    if not path.startswith(prefix):
        print('error: status: file not in prefix', file=sys.stderr)

        return 3

    trackpath = path[len(prefix):]

    if not trackpath in cfg.get('files'):
        print('error: remove-file: file not tracked', file=sys.stderr)

        return 4

    cfg.get('files').remove(trackpath)
    write_config(_config_path, cfg)

    print(f'info: remove-file: stopped tracking: {trackpath}', file=sys.stdout)

    return 0

def do_status(args: list) -> int:
    if len(args) != 1:
        print('error: status: wrong number of arguments', file=sys.stderr)

        return 1

    path = abspath(args[0])

    cfg = _read_config(_config_path)

    if not _verify_config(cfg):
        print('error: status: config verify failed', file=sys.stderr)

        return 2

    prefix = cfg.get('prefix')

    if prefix != '/':
        prefix += '/'

    if not path.startswith(prefix):
        print('error: status: file not in prefix', file=sys.stderr)

        return 4

    trackpath = path[len(prefix):]
    trackstat = 'is' if trackpath in cfg.get('files') else 'is not'

    print(f'info: status: file {trackstat} tracked', file=sys.stdout)

    return 0

def dump_files(args: list) -> int:
    print('info: dump-files: tracking the following files:', file=sys.stdout)

    cfg = _read_config(_config_path)

    if not _verify_config(cfg):
        print('error: dump-files: config verify failed', file=sys.stderr)

        return 1

    for file in cfg.get('files'):
        print(f'  {file}', file=sys.stdout)

    return 0

def clean_files(args: list) -> int:
    print('info: clean-files: cleaning non-existing files:', file=sys.stdout)

    cfg = _read_config(_config_path)

    if not _verify_config(cfg):
        print('error: clean-files: config verify failed', file=sys.stderr)

        return 1

    prefix = cfg.get('prefix')

    cfg_remove = [file for file in cfg.get('files') if not exists(f'{prefix}/{file}')]

    for f in cfg_remove:
        cfg.get('files').remove(f)
        print(f'info: clean-files: removing: {f}', file=sys.stdout)

    write_config(_config_path, cfg)

    return 0

def backup_files(args: list) -> int:
    hostname = gethostname()
    cfg = _read_config(_config_path)

    if not _verify_config(cfg):
        print('error: backup-files: config verify failed', file=sys.stderr)

        return 1

    prefix = cfg.get('prefix')
    timestamp = int(time())

    print(f'info: backup-files: timestamp = {timestamp}', file=sys.stdout)

    backup_tar = pjoin(_gdrive_prefix, f'{hostname}_{timestamp}-data.tar.xz.gpg')

    with NamedTemporaryFile(mode='w') as tmp:
        for file in cfg.get('files'):
            print(f'{prefix}/{file}', file=tmp)

        for inc in _read_includes(cfg):
            print(inc, file=tmp)

        tmp.flush()

        with open(backup_tar, mode='wb') as f:
            p_args = [_backup_prefix + 'tar_and_encrypt.sh', tmp.name]

            try:
                prun(p_args, check=True, stdout=f)

            except Exception as exc:
                print(f'error: backup-files: failed to tar+encrypt: {exc}', file=sys.stderr)

                return 2

    cfg.update({'timestamp': timestamp})
    write_config(_config_path, cfg)

    return 0

def backup_status(arg):
    hostname = gethostname()

    matchre = rcompile(f'{hostname}_[0-9]+-data.tar.xz.gpg')
    splitre = rcompile('[_-]')

    entries = []

    for arg in listdir(_gdrive_prefix):
        if matchre.fullmatch(arg) is None:
            continue

        hn, ts, _ = splitre.split(arg)
        if hn != hostname:
            continue

        entries.append(int(ts))

    if not entries:
        print('warn: backup-status: no backups present', file=sys.stderr)

        return 0

    print('info: backup-status: listing backup dates:', file=sys.stdout)

    cur_time = int(time())

    for ts in entries:
        age = int((cur_time - ts) / 86400)
        ts_local = localtime(ts)

        print(f'\t{asctime(ts_local)} ({age} days ago)', file=sys.stdout)

    return 0

def backup_clean(args: list) -> int:
    if len(args) != 1:
        print('error: backup-clean: wrong number of arguments', file=sys.stderr)

        return 1

    max_age = int(args[0])

    if max_age < 5:
        print('error: backup-clean: age has to be 5 or greater', file=sys.stderr)

        return 2

    hostname = gethostname()

    matchre = rcompile(f'{hostname}_[0-9]+-data.tar.xz.gpg')
    splitre = rcompile('[_-]')

    entries = []

    for arg in listdir(_gdrive_prefix):
        if matchre.fullmatch(arg) is None:
            continue

        hn, ts, _ = splitre.split(arg)
        if hn != hostname:
            continue

        entries.append((arg, int(ts)))

    cur_time = int(time())

    sorted_entries = sorted(entries, key=lambda entry: cur_time - entry[1])

    if len(sorted_entries) <= 1:
        print('warn: backup-clean: only one backup (or less) available', file=sys.stderr)

        return 3

    print('info: backup-clean: removing following backups:', file=sys.stdout)

    for path, ts in sorted_entries[1:]:
        age = int((cur_time - ts) / 86400)
        if age <= max_age:
            continue

        ts_local = localtime(ts)
        print(f'\t{asctime(ts_local)} ({age} days ago)', file=sys.stdout)

        remove(pjoin(_gdrive_prefix, path))

    return 0

def do_sync(args: list) -> int:
    print('info: sync: syncing with Google Drive', file=sys.stdout)

    p_args = ['grive', '--path', _gdrive_prefix]
    p = prun(p_args)

    return p.returncode


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

    '''
    Set restrictive umask so that the backup archives are only
    readable by root itself.
    '''
    umask(0o27)

    switcher = {
        '--add-file': add_file,
        '--remove-file': remove_file,
        '--status': do_status,
        '--dump-files': dump_files,
        '--clean-files': clean_files,
        '--backup-files': backup_files,
        '--backup-status': backup_status,
        '--backup-clean': backup_clean,
        '--sync': do_sync,
    }

    command = switcher.get(args[1], None)

    if command is None:
        _usage(args[0])

        return 1

    if command(args[2:]) != 0:
        return 2
