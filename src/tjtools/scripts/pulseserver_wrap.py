# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0

from __future__ import annotations


##########################################################################################
# Imports
##########################################################################################

import sys

from argparse import ArgumentParser
from dataclasses import dataclass
from enum import IntEnum, unique
from json import loads as jloads
from os import environ, sched_setaffinity
from pathlib import Path
from socket import AF_INET, IPPROTO_TCP, SHUT_RDWR, SOCK_STREAM, gaierror, getaddrinfo, socket
from subprocess import run as prun
from time import time


##########################################################################################
# Constants
##########################################################################################

_pulseaudio_tcp_port = 4713
_config_path_template = Path('~/.config/pulseserver_wrap.conf')
_flatpak_args_template = ('flatpak', 'run', '--branch=stable', '--arch=x86_64', '--filesystem=home', '--command={0}')
_logfile_template = Path('~/local/log')
_pulsefake_template = Path('~/local/pulsefake')


##########################################################################################
# Enumerator definitions
##########################################################################################

@unique
class CPUAffinity(IntEnum):
    '''
    CPU affinity enumerator.

    Default       - use default CPU affinity setup (all cores are used)
    SingleCore    - set CPU affinity mask to a single core
    PhysicalCores - set CPU affinity mask physical cores only
    '''

    Default       = 0
    SingleCore    = 1
    PhysicalCores = 2

    @staticmethod
    def from_string(raw: str) -> CPUAffinity:
        '''
        Parse a CPU affinity enumerator from a raw string.

        Arguments:
            raw - the raw string input
        '''

        if raw is None or raw.lower() == 'default':
            return CPUAffinity.Default
        elif raw.lower() == 'single':
            return CPUAffinity.SingleCore
        elif raw.lower() == 'physical':
            return CPUAffinity.PhysicalCores
        else:
            raise RuntimeError(f'invalid affinity string: {raw}')

    def to_mask(self) -> tuple[int]:
        '''
        Convert CPU affinity enumerator to a affinity mask.
        '''

        if self.value == CPUAffinity.Default:
            return None
        elif self.value == CPUAffinity.SingleCore:
            return (0,)
        elif self.value == CPUAffinity.PhysicalCores:
            return (0, 2, 4, 6)
        else:
            raise RuntimeError(f'invalid affinity enum: {self.value}')


##########################################################################################
# Dataclass definitions
##########################################################################################

@dataclass(frozen=True)
class ConfigArguments:
    '''
    Dataclass encoding the configuration supplied via CLI arguments.

    flatpak           - Are we wrapping a FlatPak application?
    prefer_headphones - Should we prefer headphones for audio output?
    quirks            - List of quirks to apply (pulsefake)
    affinity          - CPU affinity setting (see the enumerator for details)
    print_log         - Print the log of the application?
    dxvk_config       - DXVK config alias
    envvar_config     - Environment variable config alias
    args              - arguments passed to subprocess
    '''

    flatpak: bool
    prefer_headphones: bool
    quirks: list[str]
    affinity: CPUAffinity
    print_log: bool
    dxvk_config: str
    envvar_config: str
    args: list[str]


##########################################################################################
# Internal functions
##########################################################################################

def _defer_func(func, *parms, **kwparms):
    def caller():
        func(*parms, **kwparms)

    return caller

def _make_flatpak_args(cmd: str) -> list[str]:
    return [x.format(cmd) for x in _flatpak_args_template]

def _is_pa_device_connected(device_names: list[str]) -> bool:
    '''
    Check if a PulseAudio device is connected.

    Arguments:
        device_name - name of the PulseAudio device
    '''

    p_args = ('/usr/bin/pactl', '--format=json', 'list', 'cards')

    p = prun(p_args, check=True, capture_output=True, encoding='utf-8')

    cards = jloads(p.stdout)

    for card in cards:
        if card.get('name') in device_names:
            return True

    return False

def _is_server_available(server: str) -> bool:
    '''
    Helper to check if a PulseAudio server is available.

    Arguments:
        server - server to check
    '''

    try:
        addr_infos = getaddrinfo(server, _pulseaudio_tcp_port, proto=IPPROTO_TCP)

    except gaierror:
        return False

    sock_addr = None

    for info in addr_infos:
        if info[0] == AF_INET:
            sock_addr = info[4]
            break

    if sock_addr is None:
        return False

    with socket(AF_INET, SOCK_STREAM) as _s:
        _s.settimeout(2.0)

        server_available = False

        try:
            _s.connect(sock_addr)
            _s.shutdown(SHUT_RDWR)

            server_available = True

        except Exception as exc:
            print(f'warn: error while connecting: {exc}', file=sys.stderr)

    return server_available


##########################################################################################
# Functions
##########################################################################################

def pulseserver_wrap(config_args: ConfigArguments) -> None:
    '''
    Wrapper to launch a process with modified environment if a given
    PulseAudio server is online.

    The server and the cookie are extracted from a config file.
    '''

    if len(config_args.args) == 0:
        raise RuntimeError('missing arguments')

    real_args = config_args.args.copy()
    if real_args[0] == '--':
        real_args = real_args[1:]

    try:
        config = jloads(_config_path_template.expanduser().read_text(encoding='utf-8'))

    except Exception as exc:
        raise RuntimeError(f'failed to load config: {exc}') from exc

    pulse_server = config.get('pulseserver')
    if pulse_server is None or not isinstance(pulse_server, str):
        raise RuntimeError('invalid config: missing server')

    pulse_cookie = config.get('pulsecookie')
    if pulse_cookie is None or not isinstance(pulse_cookie, str):
        raise RuntimeError('invalid config: missing cookie')

    dxvk_map = config.get('dxvkmap')
    if dxvk_map is None or not isinstance(dxvk_map, dict):
        raise RuntimeError('invalid config: missing DXVK map')

    envvar_map = config.get('envvarmap')
    if envvar_map is None or not isinstance(envvar_map, dict):
        raise RuntimeError('invalid config: missing envvar map')

    headphones = config.get('headphones')
    if headphones is None or not isinstance(headphones, list):
        raise RuntimeError('invalid config: missing headphones')

    # TODO: can we validate this some more?

    p_env = None

    if config_args.quirks is not None:
        if 'pulsefake' in config_args.quirks:
            '''
            Apply the PulseAudio fake quirks that is needed for
            older versions of the FMOD library.
            '''
            if p_env is None:
                p_env = environ.copy()

            pulsefake = _pulsefake_template.expanduser()
            if pulsefake.is_dir():
                p_env['PATH'] = pulsefake.as_posix() + ':' + p_env['PATH']

    use_headphones = False
    if config_args.prefer_headphones:
        use_headphones = _is_pa_device_connected(headphones)

    if not use_headphones and _is_server_available(pulse_server):
        print(f'info: pulse server available: {pulse_server}', file=sys.stdout)

        if p_env is None:
            p_env = environ.copy()

        key_server = 'PULSE_SERVER'
        key_cookie = 'PULSE_COOKIE'

        if config_args.flatpak:
            key_server = 'ENV_' + key_server
            key_cookie = 'ENV_' + key_cookie

        p_env[key_server] = f'tcp:{pulse_server}'
        p_env[key_cookie] = Path(pulse_cookie).expanduser().as_posix()

    if config_args.dxvk_config is not None:
        print(f'info: DXVK config selected: {config_args.dxvk_config}', file=sys.stdout)

        if p_env is None:
            p_env = environ.copy()

        dxvk_config = dxvk_map.get(config_args.dxvk_config)
        if dxvk_config is None:
            raise RuntimeError(f'unknown DXVK config')

        p_env['DXVK_CONFIG_FILE'] = Path(dxvk_config).expanduser()

    if config_args.envvar_config is not None:
        print(f'info: Environment variable config selected: {config_args.envvar_config}', file=sys.stdout)

        if p_env is None:
            p_env = environ.copy()

        envvar_config = envvar_map.get(config_args.envvar_config)
        if envvar_config is None or not isinstance(envvar_config, dict):
            raise RuntimeError(f'unknown envvar config')

        p_env.update(envvar_config)

    if config_args.flatpak:
        print('info: flatpak mode enabled', file=sys.stdout)

        logfile_base = 'flatpak'
        real_args = _make_flatpak_args('flatpak_env_helper.sh') + real_args

    else:
        logfile_base = Path(real_args[0]).name

    affinity_mask = config_args.affinity.to_mask()
    if affinity_mask is not None:
        print(f'info: using CPU affinity mask: {affinity_mask}', file=sys.stdout)

        affinity_func = _defer_func(sched_setaffinity, 0, affinity_mask)
    else:
        affinity_func = None

    logfile_path = _logfile_template.expanduser() / Path(f'{logfile_base}.{int(time())}.log')

    p_named_args = {'env': p_env, 'check': False, 'preexec_fn': affinity_func}

    if not config_args.print_log:
        p_named_args.update({'capture_output': True, 'encoding': 'utf-8'})

    _p = prun(real_args, **p_named_args)

    if not config_args.print_log:
        with open(logfile_path, mode='w', encoding='utf-8') as _f:
            if len(_p.stdout) != 0:
                print(f'info: stdout for: {real_args}', file=_f)
                _f.write(_p.stdout)

            if len(_p.stderr) != 0:
                print(f'info: stderr for: {real_args}', file=_f)
                _f.write(_p.stderr)

    if _p.returncode != 0:
        raise RuntimeError(f'wrapped application failed: {_p.returncode}')


##########################################################################################
# Main
##########################################################################################

def main(args: list[str]) -> int:
    '''
    Main function.

    Arguments:
        args - list of string arguments from the CLI
    '''

    parser = ArgumentParser()

    parser.add_argument('-f', '--flatpak', action='store_true', help='Are we wrapping a flatpak application?')
    parser.add_argument('-x', '--prefer-headphones', action='store_true', help='Should we prefer headphones for audio output?')
    parser.add_argument('-q', '--quirks', help='Apply any quirks? Quirks are comma-separated (pulsefake)')
    parser.add_argument('-a', '--affinity', choices=('single', 'physical'), help='Should we set the CPU affinity when launching the application?')
    parser.add_argument('-p', '--print-log', action='store_true', help='Should we print the log of the application?')
    parser.add_argument('-d', '--dxvk-config', help='DXVK config which should be used')
    parser.add_argument('-e', '--envvar-config', help='Environment variable config which should be used')

    parsed_args, additional_args = parser.parse_known_args(args[1:])

    config = ConfigArguments(
        parsed_args.flatpak,
        parsed_args.prefer_headphones,
        None if parsed_args.quirks is None else parsed_args.quirks.split(','),
        CPUAffinity.from_string(parsed_args.affinity),
        parsed_args.print_log,
        parsed_args.dxvk_config,
        parsed_args.envvar_config,
        additional_args,
    )

    try:
        pulseserver_wrap(config)

    except Exception as exc:
        print(f'error: pulseserver wrap failed: {exc}', file=sys.stderr)

        return 1

    return 0
