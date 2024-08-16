# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

import sys

from json import dump as jdump, load as jload
from os.path import isdir, isfile, join as pjoin
from os import listdir
from re import compile as rcompile


##########################################################################################
# Constants
##########################################################################################

_sysfs_base = '/sys/devices/system/cpu'
_map_file = '/run/core_map'
_config_file = '/run/cpufreq_config'

_cpu_re = rcompile('^cpu[0-9]+$')

_profiles = {
    'low': {
        'cores': (0, 1, 2, 3),
        'boost': False
    },
    'mid': {
        'cores': (0, 1, 2, 3),
        'boost': True
    },
    'high': {
        'cores': (0, 1, 2, 3, 4, 5, 6, 7),
        'boost': True
    }
}


##########################################################################################
# Internal functions
##########################################################################################

def _usage(app: str) -> None:
    print(f'Usage: {app}', file=sys.stdout)

    print('\t --save|--restore [save/restore cpufreq state]', file=sys.stdout)
    print('\t --init [initialize core map for cpufreq control]', file=sys.stdout)
    print('\t --set {low, mid, high}', file=sys.stdout)

def read_sysfs(path: str) -> str:
    try:
        with open(path, mode='r') as f:
            data = f.read().rstrip()

    except Exception:
        data = None

    return data

def get_cpu_status(path: str) -> str:
    online = read_sysfs(pjoin(path, 'online'))
    if online is None:
        return None

    return online == '1'

def handle_cpu(path: str) -> tuple[bool, int]:
    online = pjoin(path, 'online')
    if not isfile(online):
        return None

    topology = pjoin(path, 'topology/core_id')
    if not isfile(topology):
        return None

    try:
        with open(online, mode='r') as f:
            is_online = f.read().rstrip() == '1'

        with open(topology, mode='r') as f:
            core_id = int(f.read().rstrip())

    except Exception:
        return None

    return (is_online, core_id)

def core_map(args=[]):
    cpu_core_map = dict()

    for arg in listdir(_sysfs_base):
        res = _cpu_re.findall(arg)
        if len(res) == 0:
            continue

        p = pjoin(_sysfs_base, arg)
        if not isdir(p):
            continue

        res = handle_cpu(p)
        if res is None:
            continue

        cpu_core_map[arg] = res

    try:
        with open(_map_file, mode='w') as f:
            jdump(cpu_core_map, fp=f)

    except Exception as exc:
        print(f'error: failed to write core map file: {exc}', file=sys.stderr)

        return 1

    return 0

def save_state(args=[]):
    try:
        with open(_map_file, mode='r') as f:
            cpu_core_map = jload(f)

    except Exception as exc:
        print(f'error: failed to parse core map file: {exc}', file=sys.stderr)

        return 1

    online_status = dict()

    for arg in listdir(_sysfs_base):
        res = _cpu_re.findall(arg)
        if len(res) == 0:
            continue

        if not arg in cpu_core_map:
            continue

        p = pjoin(_sysfs_base, arg)
        if not isdir(p):
            continue

        res = get_cpu_status(p)
        if res == None:
            continue

        online_status[arg] = res

    try:
        with open(pjoin(_sysfs_base, 'cpufreq/boost'), mode='r') as f:
            boost_status = f.read().rstrip() == '1'

    except Exception as exc:
        print(f'error: failed to determine boost status: {exc}', file=sys.stderr)

        return 2

    config = {
        'online_status': online_status,
        'boost_status': boost_status
    }

    try:
        with open(_config_file, mode='w') as f:
            jdump(config, fp=f)

    except Exception as exc:
        print(f'error: failed to write config file: {exc}', file=sys.stderr)

        return 3

    return 0

def restore_state(args=[]) -> int:
    try:
        with open(_map_file, mode='r') as f:
            cpu_core_map = jload(f)

    except Exception as exc:
        print(f'error: failed to parse core map file: {exc}', file=sys.stderr)

        return 1

    try:
        with open(_config_file, mode='r') as f:
            config = jload(f)

    except Exception:
        print(f'error: failed to parse config file: {exc}', file=sys.stderr)

        return 2

    online_status = config['online_status']
    boost_status = config['boost_status']

    for arg in listdir(_sysfs_base):
        res = _cpu_re.findall(arg)
        if len(res) == 0:
            continue

        if not arg in cpu_core_map:
            continue

        if not arg in online_status:
            print(f'warn: CPU {arg} missing in online status', file=sys.stderr)

        status = online_status[arg]

        ret = config_cpu(arg,status)
        if ret != 0:
            print(f'warn: skipping CPU {arg} (failed to config)', file=sys.stderr)

    try:
        with open(pjoin(_sysfs_base, 'cpufreq/boost'), mode='w') as f:
            f.write('1' if boost_status else '0')

    except Exception as exc:
        print(f'error: failed to restore boost status: {exc}', file=sys.stderr)

        return 3

    return 0

def is_valid_profile(p: str) -> bool:
    return p in ('low', 'mid', 'high')

def config_cpu(cpu, online: bool) -> int:
    p = pjoin(_sysfs_base, cpu)
    if not isdir(p):
        return 1

    try:
        with open(pjoin(p, 'online'), mode='w') as f:
            f.write('1' if online else '0')

    except Exception:
        return 2

    return 0

def set_config(core_map, cfg) -> int:
    is_boost = cfg['boost']
    online_cores = cfg['cores']

    for key, arg in core_map.items():
        online = arg[1] in online_cores

        ret = config_cpu(key, online)
        if ret != 0:
            print(f'error: failed to config CPU {key}', file=sys.stderr)

            return 1

    try:
        with open(pjoin(_sysfs_base, 'cpufreq/boost'), mode='w') as f:
            f.write('1' if is_boost else '0')

    except Exception as exc:
        print(f'error: failed to set boost: {exc}', file=sys.stderr)

        return 2

    return 0

def set_state(args: list[str]) -> int:
    try:
        with open(_map_file, mode='r') as f:
            cpu_core_map = jload(f)

    except Exception as exc:
        print(f'error: failed to parse core map file: {exc}', file=sys.stderr)

        return 1

    if len(args) == 0:
        print('error: profile argument missing', file=sys.stderr)

        return 2

    profile = args[0]

    if not is_valid_profile(profile):
        print(f'error: invalid profile selected: {profile}', file=sys.stderr)

        return 3

    core_cfg = _profiles[profile]

    ret = set_config(cpu_core_map, core_cfg)
    if ret != 0:
        print(f'error: failed to set core config: {ret}', file=sys.stderr)

        return 4

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

    switcher = {
        '--init': core_map,
        '--save': save_state,
        '--restore': restore_state,
        '--set': set_state,
    }

    if len(args) < 2:
        _usage(args[0])

        return 0

    command = switcher.get(args[1], None)

    if command == None:
        _usage(args[0])

        return 1

    if command(args[2:]) != 0:
        return 2

    return 0
