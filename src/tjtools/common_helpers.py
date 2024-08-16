# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

from ctypes import CDLL, POINTER, c_uint32
from pathlib import Path


##########################################################################################
# Constants
##########################################################################################

'''
Load shared library containing get_active_user().
'''
_active_user = CDLL('libactive_user.so')
_active_user.get_active_user.argtypes = [POINTER(c_uint32)]

'''
Template for the user's run directory.
'''
_run_template = '/run/user/{0}'

'''
Template to figure out the Sway socket to use.
'''
_socket_prefix_template = 'sway-ipc.{0}'
_socket_name_template = '{0}.*.sock'.format(_socket_prefix_template)


##########################################################################################
# Function
##########################################################################################

def get_active_user() -> int:
    '''
    Get the currently active user.

    Returns a Unix user ID if a user is active, or None if no user is active.

    Active here means that the user is logged in locally and
    has a graphical session open.
    '''

    user_id = c_uint32()

    ret = _active_user.get_active_user(user_id)
    if ret < 0:
        raise RuntimeError(f'failed to get active user: {ret}')

    if ret == 0:
        return None

    return user_id.value


def get_sway_ipc(uid: int) -> Path:
    '''
    Get path to the Sway IPC socket of a given user.

    Arguments:
        uid - the numerical user ID

    Returns a valid socket path, or None if the user has no active
    Sway session running.
    '''

    runpath = Path(_run_template.format(uid))
    sockets = list(runpath.glob(_socket_name_template.format(uid)))

    if len(sockets) == 0:
        return None

    if len(sockets) == 1:
        return sockets[0]

    socket_prefix = _socket_prefix_template.format(uid) + '.'

    def key_func(p: Path) -> int:
        ret, _ = p.name.removeprefix(socket_prefix).split('.', maxsplit=1)
        return ret

    return sorted(sockets, key=key_func)[0]
