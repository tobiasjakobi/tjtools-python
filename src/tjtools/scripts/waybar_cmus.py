# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

import sys

from json import dumps as jdumps
from re import compile as rcompile
from subprocess import run as prun
from time import sleep


##########################################################################################
# Constants
##########################################################################################

_status_re = rcompile(r'^status ')
_artist_re = rcompile(r'^tag artist ')
_title_re = rcompile(r'^tag title ')
_album_re = rcompile(r'^tag album ')


##########################################################################################
# Functions
##########################################################################################

def _tag_parse(tag: str):
    tmp = tag.rstrip()
    pos = tmp.find(' ', 4)

    if pos < 0:
        return tmp
    else:
        return tmp[pos + 1:]

def _status_parse(status: str):
    tmp = status.rstrip()
    pos = tmp.find(' ', 6)

    if pos < 0:
        return tmp
    else:
        return tmp[pos + 1:]

def _cmus_query():
    cmus_args = ('cmus-remote', '-Q')
    p = prun(cmus_args, capture_output=True, encoding='utf-8')

    out = p.stdout.splitlines()

    if p.returncode != 0 or not out:
        return None

    return out

def _cmus_format():
    query = _cmus_query()
    if query is None:
        return 'offline', 'offline'

    status = None
    artist = None
    title = None
    album = None

    for arg in query:
        line = arg.rstrip()

        if _status_re.match(line) is not None:
            status = _status_parse(line)
        elif _artist_re.match(line) is not None:
            artist = _tag_parse(line)
        elif _title_re.match(line) is not None:
            title = _tag_parse(line)
        elif _album_re.match(line) is not None:
            album = _tag_parse(line)

    if status is None:
        return 'offline', 'offline'
    elif status == 'paused':
        return 'silence', 'silence'

    if title is None or artist is None:
        return 'unknown', 'unknown'

    if album is not None:
        cmus_long = f'{artist} - [{album}] {title}'
    else:
        cmus_long = None

    cmus_short = f'{artist} - {title}'

    return cmus_short, cmus_long

def cmus_refresh():
    status = {
        'text': None,
        'tooltip': None,
        'class': 'CMus',
        'percentage': 0
    }

    status['text'], status['tooltip'] = _cmus_format()

    pipe_lost = False

    try:
        print(jdumps(status), file=sys.stdout, flush=True)

    except Exception as exc:
        print(f'error: failed to dump JSON to stdout: {exc}'.format(exc), file=sys.stderr)

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

    while True:
        if cmus_refresh():
            break

        sleep(10.0)

    return 0
