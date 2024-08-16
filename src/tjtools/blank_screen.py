# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

from pwd import getpwnam

from i3ipc import Connection as I3Connection
from .common_helpers import get_active_user, get_sway_ipc


##########################################################################################
# Constants
##########################################################################################

'''
The default output which we blank.
'''
_default_output = 'eDP-1'


##########################################################################################
# Internal functions
##########################################################################################

def _blank_intern(uid: int) -> None:
    '''
    Internal blanking function.

    Arguments:
        uid - the numerical user ID
    '''

    ipc_socket = get_sway_ipc(uid)
    if ipc_socket is None:
        return

    conn = I3Connection(socket_path=ipc_socket.as_posix())

    replies = conn.command(f'output {_default_output} power off')

    if len(replies) != 1:
        raise RuntimeError('malformed IPC reply')

    if not replies[0].success:
        raise RuntimeError(f'IPC command failed: {replies[0].ipc_data}')


##########################################################################################
# Functions
##########################################################################################

def blank_screen(username: str) -> None:
    '''
    Blank screen for a given user.

    Arguments:
        username - the name of the user
    '''

    if username is None:
        uid = get_active_user()
    else:
        try:
            uid = getpwnam(username).pw_uid

        except KeyError as err:
            raise RuntimeError('failed to lookup username: {err}') from err

    if uid is not None:
        _blank_intern(uid)
