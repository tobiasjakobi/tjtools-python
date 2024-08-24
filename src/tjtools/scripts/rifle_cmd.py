# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0

from __future__ import annotations


##########################################################################################
# Imports
##########################################################################################

import sys

from dataclasses import dataclass, asdict
from json.decoder import JSONDecodeError
from json import dumps as jdumps, loads as jloads
from os.path import exists
from os import environ
from socket import socket, AF_UNIX, SOCK_STREAM, error as socket_error
from subprocess import DEVNULL, run as prun
from time import time


##########################################################################################
# Constants
##########################################################################################

rifle_cmdstat = 'RIFLE_CMDSTAT_FIFO'


##########################################################################################
# Dataclass definitions
##########################################################################################

@dataclass(frozen=True)
class CommandResult:
    '''
    Result dataclass for rifle commands.

    cmd    - the command itself
    epoch  - when the command was executed (Epoch value, in seconds)
    retval - return value of the command execution
    stdout - standard output of the command execution
    stderr - standard error of the command execution
    '''

    cmd: list[str]
    epoch: float
    retval: int
    stdout: str
    stderr: str

    def to_json(self) -> str:
        '''
        Convert to JSON string.
        '''

        return jdumps(asdict(self))

    @staticmethod
    def from_json(input_json: str) -> CommandResult:
        '''
        Make a result dataclass from a JSON string.

        Arguments:
            input - the input JSON string
        '''

        try:
            input_dict = jloads(input_json)

        except JSONDecodeError:
            return None

        return CommandResult(**input_dict)


##########################################################################################
# Internal functions
##########################################################################################

def _rifle_cmd(args: list[str]) -> int:
    '''
    Execute a command and feed the command results into the rifle FIFO.

    Arguments:
        args - argument list for the command
    '''

    retry_script = False

    try:
        p = prun(args, stdin=DEVNULL, capture_output=True, encoding='utf-8')

    except FileNotFoundError:
        retry_script = True

    if retry_script:
        p = prun(['exec_script.sh'] + args, stdin=DEVNULL, capture_output=True, encoding='utf-8')

    res = CommandResult(
        cmd    = args,
        epoch  = time(),
        retval = p.returncode,
        stdout = p.stdout,
        stderr = p.stderr
    )

    if rifle_cmdstat in environ:
        socket_name = environ[rifle_cmdstat]

        if exists(socket_name):
            client = socket(AF_UNIX, SOCK_STREAM)

            try:
                client.connect(socket_name)

                payload = res.to_json() + '\n'

                try:
                    client.sendall(payload.encode('utf-8'))

                except socket_error as err:
                    print(f'error: failed to send to socket: {err}', file=sys.stderr)

            except socket_error as err:
                print(f'error: failed to connect to socket: {err}', file=sys.stderr)

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
        return 0

    return _rifle_cmd(args[1:])
