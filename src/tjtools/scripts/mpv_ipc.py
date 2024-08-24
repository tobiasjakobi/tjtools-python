# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

from io import StringIO
from json import loads as jloads, dumps as jdumps
from pathlib import Path
from random import seed, randint
from socket import AF_UNIX, SOCK_STREAM, SHUT_WR, SHUT_RD, socket
from sys import stderr, stdout


##########################################################################################
# Constants
##########################################################################################

_mpv_ctrl = Path('/tmp/mpv.control')


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
        print('error: missing command argument', file=stderr)

        return 1

    seed()

    if not _mpv_ctrl.exists():
        print(f'error: mpv control socket not found: {_mpv_ctrl}', file=stderr)

        return 2

    sock = socket(AF_UNIX, SOCK_STREAM)

    try:
        sock.connect(_mpv_ctrl.as_posix())

    except OSError as msg:
        sock.close()
        print(f'error: failed to connect to socket: {msg}', file=stderr)

        return 3

    req_id = randint(0, 1024)

    mpv_cmd = {
        'command': args[1:],
        'request_id': req_id,
    }

    json_out = jdumps(mpv_cmd) + '\n'

    try:
        sock.sendall(json_out.encode('utf-8'))

    except OSError as msg:
        sock.close()
        print(f'error: failed to send data to socket: {msg}', file=stderr)

        return 4

    sock.shutdown(SHUT_WR)

    try:
        bytes = sock.recv(2048)

    except OSError as msg:
        sock.close()
        print(f'error: failed to receive data from socket: {msg}', file=stderr)

        return 5

    sock.shutdown(SHUT_RD)
    sock.close()

    reply = StringIO(bytes.decode('utf-8'))

    for arg in reply.read().splitlines():
        json_in = jloads(arg)

        if json_in.get('request_id') == req_id:
            print('reply: {0}'.format(json_in['error']), file=stdout)

    reply.close()

    return 0
