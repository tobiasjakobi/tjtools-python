# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0

from __future__ import annotations


##########################################################################################
# Imports
##########################################################################################

import sys

from html import escape as html_escape
from json import dumps as jdumps
from os.path import exists
from os import environ, remove
from socket import socket, AF_UNIX, SOCK_STREAM
from time import asctime, localtime, time

from .rifle_cmd import CommandResult, rifle_cmdstat


##########################################################################################
# Constants
##########################################################################################

_green = '0FB520'
_red = 'FF0000'
_orange = 'FFAF00'

_dummy_res = CommandResult(
    cmd    = ['initialization'],
    epoch  = time(),
    retval = 0,
    stdout = 'welcome to rifle monitor',
    stderr = None,
)


##########################################################################################
# Internal functions
##########################################################################################

def _mkspan(color: str, text: str) -> str:
    '''
    Make a pango span using color and text.

    Arguments:
        color - the color hex string
        text  - the text string to color
    '''

    return f'<span color=\"#{color}\">{text}</span>'

def _handle_res(res: CommandResult) -> bool:
    '''
    Handle a rifle command result.

    Arguments:
        res - the rifle command result

    Returns True if the pipe was lost, and False otherwise.
    '''

    cmd_string = html_escape(' '.join(res.cmd))
    time_sting = asctime(localtime(res.epoch))

    cmd_stat = _mkspan(_green if res.retval == 0 else _red, f'[{time_sting}]\n{cmd_string} returned {res.retval}')

    tooltip = list()

    if res.stdout:
        tooltip.append(html_escape(res.stdout))

    if res.stderr:
        tooltip.append(_mkspan(_orange, html_escape(res.stderr)))

    tooltip.append(cmd_stat)

    status = {
        'text': str(res.retval),
        'tooltip': '\n'.join(tooltip),
        'class': 'rifle',
        'percentage': 0,
    }

    pipe_lost = False

    try:
        print(jdumps(status), file=sys.stdout, flush=True)

    except Exception as exc:
        print(f'error: failed to dump JSON to stdout: {exc}', file=sys.stderr)

        pipe_lost = True

    return pipe_lost


##########################################################################################
# Main
##########################################################################################

def main(args: list[str]) -> int:
    '''
    Main function.

    Arguments:
        args - list of string arguments from the CLI
    '''

    socket_name = None

    if rifle_cmdstat in environ:
        socket_name = environ[rifle_cmdstat]

    if socket_name is None:
        return 1

    if exists(socket_name):
        remove(socket_name)

    server = socket(AF_UNIX, SOCK_STREAM)
    server.bind(socket_name)

    _handle_res(_dummy_res)

    '''
    Loop here until we encounter any kind of exception.
    As accepting a connection on the socket is a blocking
    call, we sleep here most of the time.
    '''
    try:
        while True:
            server.listen(1)
            conn, addr = server.accept()

            datagram = str()

            while True:
                datagram_fragment = conn.recv(1024)
                if datagram_fragment is None:
                    break

                datagram += datagram_fragment.decode(encoding='utf-8')

                if datagram.endswith('\n'):
                    break

            if '\n' not in datagram:
                continue

            lines = datagram.splitlines()

            pipe_lost = False

            for l in lines:
                try:
                    res = CommandResult.from_json(l)

                except TypeError as exc:
                    continue

                if res is None:
                    continue

                if _handle_res(res):
                    pipe_lost = True
                    break

            if pipe_lost:
                break

    finally:
        remove(socket_name)

    return 0
