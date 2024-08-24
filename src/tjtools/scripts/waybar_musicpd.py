# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0

from __future__ import annotations


##########################################################################################
# Imports
##########################################################################################

import socket
import sys

from dataclasses import dataclass
from enum import IntEnum, unique
from html import escape as html_escape
from json import dumps as jdumps
from os import environ as os_environ
from subprocess import CalledProcessError, run as prun
from time import sleep
from typing import Optional


##########################################################################################
# Constants
##########################################################################################

_mpd_default_host = 'localhost'
_mpd_default_port = 6600


##########################################################################################
# Enumerator definitions
##########################################################################################

@unique
class MPDErrorType(IntEnum):
    Generic         = 0
    Empty           = 1
    Malformed       = 2
    HostUnavailable = 3
    Unknown         = 4

    def is_critical(self) -> bool:
        return self.value not in (MPDErrorType.Empty, MPDErrorType.HostUnavailable)


##########################################################################################
# Dataclass definitions
##########################################################################################

@dataclass(frozen=True)
class MPDConfig:
    host: str
    port: int

    @staticmethod
    def read_environ() -> MPDConfig:
        mpd_host = os_environ.get('MPD_HOST')
        if mpd_host is None:
            mpd_host = _mpd_default_host

        mpd_port = os_environ.get('MPD_PORT')
        if mpd_port is None:
            mpd_port = _mpd_default_port

        return MPDConfig(mpd_host, mpd_port)


##########################################################################################
# Class definitions
##########################################################################################

class MPDException(Exception):
    def __init__(self, type: MPDErrorType):
        self._type = type

    def get_type(self) -> MPDErrorType:
        return self._type


##########################################################################################
# Internal functions
##########################################################################################

def _html_escape2(input: Optional[str]) -> str:
    if input is None:
        return None

    return html_escape(input, quote=False)

def _is_host_available(cfg: MPDConfig) -> bool:
    '''
    Helper to check if a MPD host is available.

    Arguments:
        cfg - MPD configuration
    '''

    try:
        addr_infos = socket.getaddrinfo(cfg.host, cfg.port, proto=socket.IPPROTO_TCP)

    except socket.gaierror:
        return False

    sock_addr = None

    for info in addr_infos:
        if info[0] == socket.AF_INET:
            sock_addr = info[4]
            break

    if sock_addr is None:
        return False

    _s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _s.settimeout(2.0)

    server_available = False

    try:
        _s.connect(sock_addr)
        _s.shutdown(socket.SHUT_RDWR)

        server_available = True

    except TimeoutError:
        pass

    except Exception as exc:
        print(f'warn: error while connecting: {exc}', file=sys.stderr)

    finally:
        _s.close()

    return server_available

def _callmpc(args: tuple[str]) -> str:
    p_args =('mpc',) + args

    try:
        p = prun(p_args, capture_output=True, check=True, encoding='utf-8')

    except CalledProcessError as exc:
        type = MPDErrorType.Unknown

        stderr = exc.stderr.splitlines()
        if len(stderr) >= 1 and stderr[0].rstrip().startswith('MPD error:'):
            type = MPDErrorType.Generic

        raise MPDException(type)

    stdout = p.stdout.splitlines()

    if len(stdout) == 0:
        raise MPDException(MPDErrorType.Empty)

    if len(stdout) != 1:
        raise MPDException(MPDErrorType.Malformed)

    return stdout[0].rstrip()


##########################################################################################
# Functions
##########################################################################################

def musicpd_refresh(cfg: MPDConfig):
    status = {
        'text': None,
        'tooltip': None,
        'class': 'MusicPD',
        'percentage': 0,
    }

    delay = 10

    artist_args = ('--format=%artist%', 'current')
    title_args = ('--format=%title%', 'current')
    album_args = ('--format=%album%', 'current')

    album = None

    try:
        if not _is_host_available(cfg):
            raise MPDException(MPDErrorType.HostUnavailable)

        artist = _callmpc(artist_args)

        try:
            title = _callmpc(title_args)
            album = _callmpc(album_args)

        except:
            pass

    except MPDException as exc:
        etype = exc.get_type()

        if etype.is_critical():
            print(f'error: critical MPD exception: {etype.name}', file=sys.stderr)

        '''
        An MPD exception is most likely due to missing network connectivity to the
        server, so increase the delay here.
        '''
        delay *= 5

    except Exception as exc:
        print(f'error: unexpected exception during artist info fetch: {exc}', file=sys.stderr)

    try:
        if album != None:
            mpc_long = f'{artist} - [{album}] {title}'
        else:
            mpc_long = None

        mpc_short = f'{artist} - {title}'

    except:
        mpc_short = 'silence'

    status['text'] = _html_escape2(mpc_short)
    status['tooltip'] = _html_escape2(mpc_long)

    pipe_lost = False

    try:
        print(jdumps(status), file=sys.stdout, flush=True)

    except Exception as exc:
        print(f'error: failed to dump JSON to stdout: {exc}', file=sys.stderr)
        pipe_lost = True

    return pipe_lost, delay


##########################################################################################
# Main
##########################################################################################

def main(args: list[str]) -> int:
    '''
    Main function.

    Arguments:
        args - list of string arguments from the CLI
    '''

    config = MPDConfig.read_environ()

    while True:
        pipe_lost, delay = musicpd_refresh(config)

        if pipe_lost:
            break

        sleep(delay)

    return 0
