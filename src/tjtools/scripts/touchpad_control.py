#!/usr/bin/env python3
# -*- coding: utf-8 -*-


##########################################################################################
# Imports
##########################################################################################

import sys

from argparse import ArgumentParser
from os import environ as os_environ
from pathlib import Path
from subprocess import run as prun

from i3ipc import Connection as I3Connection

from tjtools.common_helpers import get_active_user, get_sway_ipc


##########################################################################################
# Constants
##########################################################################################

'''
Identifier of the touchpad device in Sway.
'''
_touch_identifier = '1155:21156:usb_AYANEO_USB_MOUSE'

'''
USB mouse identifiers that trigger a touchpad disable.
'''
_usb_mouse_identifiers = (
    'Logitech_USB_Laser_Mouse',
    'Razer_Razer_DeathAdder_V2',
)

'''
Template to construct input device nodes.
'''
_input_node_template = '/dev/input/by-id/usb-{0}-event-mouse'


##########################################################################################
# Internal functions
##########################################################################################

def _internal_ctrl(command: str) -> None:
    '''
    Internal control helper.

    Arguments:
        command - command to execute
    '''

    user_id = get_active_user()
    if user_id is None:
        return

    ipc_socket = get_sway_ipc(user_id)
    if ipc_socket is None:
        return

    conn = I3Connection(socket_path=ipc_socket.as_posix())

    replies = conn.command(f'input {_touch_identifier} events {command}')
    if len(replies) != 1:
        raise RuntimeError('malformed IPC reply')

    if not replies[0].success:
        raise RuntimeError(f'IPC command failed: {replies[0].ipc_data}')

    p_args = (
        'notify_wrapper',
        'Touchpad',
        f'Status: {command}',
        'Adwaita/symbolic/devices/input-touchpad-symbolic.svg',
    )

    prun(p_args, check=True)


##########################################################################################
# Functions
##########################################################################################

def touchpad_auto() -> None:
    '''
    Perform auto-configuration of touchpad.
    '''

    command = 'enabled'

    for id in _usb_mouse_identifiers:
        path = Path(_input_node_template.format(id))

        if path.exists():
            command = 'disabled'
            break

    _internal_ctrl(command)

def touchpad_udev(usb_interface: str) -> None:
    '''
    Handle a UDev event of the touchpad.

    Arguments:
        usb_interface - number of the USB interface that triggered the event
    '''

    action = os_environ.get('ACTION')
    if action is None:
        raise RuntimeError('UDev action missing')

    if action == 'add':
        command = 'disabled'
    elif action == 'remove':
        command = 'enabled'
    else:
        raise RuntimeError(f'unknown UDev action: {action}')

    if command == 'enabled':
        try:
            iface = int(usb_interface, 16)

        except ValueError:
            raise RuntimeError('malformed USB interface number')

        '''
        Only react to events on the main interface.
        '''
        if iface != 0:
            return

    _internal_ctrl(command)


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

    parser.add_argument('-m', '--mode', choices=('auto', 'udev'), help='Operation mode')
    parser.add_argument('-u', '--usb-interface', help='USB interface number for UDev mode')

    parsed_args = parser.parse_args(args[1:])

    if parsed_args.mode is None:
        print('error: missing mode argument', file=sys.stderr)

        return 1

    if parsed_args.mode == 'auto':
        try:
            touchpad_auto()

        except Exception as exc:
            print(f'error: failed to auto-configure touchpad: {exc}', file=sys.stderr)

            return 2

    elif parsed_args.mode == 'udev':
        if parsed_args.usb_interface is None:
            print('error: missing USB interface argument', file=sys.stderr)

            return 3

        try:
            touchpad_udev(parsed_args.usb_interface)

        except Exception as exc:
            print(f'error: failed to handle touchpad UDev event: {exc}', file=sys.stderr)

            return 4

    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))
