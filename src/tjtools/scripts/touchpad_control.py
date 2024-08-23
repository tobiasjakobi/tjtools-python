# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


from __future__ import annotations


##########################################################################################
# Imports
##########################################################################################

import sys

from argparse import ArgumentParser
from dataclasses import dataclass
from json import loads as jloads
from os import environ as os_environ
from pathlib import Path
from subprocess import run as prun

from ..common_helpers import get_active_user, get_sway_ipc

from i3ipc import Connection as I3Connection


##########################################################################################
# Constants
##########################################################################################

'''
Path to config file for touchpad control configuration.
'''
_config_path = Path('/etc/touchpad-control.conf')

'''
Template to construct input device nodes.
'''
_input_node_template = '/dev/input/by-id/usb-{0}-event-mouse'


##########################################################################################
# Dataclass definitions
##########################################################################################

@dataclass(frozen=True)
class TouchpadConfig:
    '''
    Dataclass encoding the touchpad control configuration.

    touchpad_identifier   - Identifier of the touchpad device in Sway
    usb_mouse_identifiers - USB mouse identifiers that trigger a touchpad disable
    '''

    touchpad_identifier: str
    usb_mouse_identifiers: list[str]

    @staticmethod
    def from_path(path: Path) -> TouchpadConfig:
        '''
        Create a touchpad config from a config path.

        Arguments:
            path - path from where we read the config
        '''

        if not path.is_file():
            raise RuntimeError(f'config path is not a file: {path}')

        config_raw = path.read_text(encoding='utf-8')
        config_data = jloads(config_raw)

        for entry in ('touchpad-identifier', 'usb-mouse-identifiers'):
            if not entry in config_data:
                raise RuntimeError(f'config entry missing: {entry}')

        touchpad_identifier = config_data['touchpad-identifier']
        if not isinstance(touchpad_identifier, str) and touchpad_identifier is not None:
            raise RuntimeError(f'invalid touchpad identifier type: {type(touchpad_identifier)}')

        usb_mouse_identifiers = config_data['usb-mouse-identifiers']
        if not isinstance(usb_mouse_identifiers, list):
            raise RuntimeError(f'invalid USB mouse identifiers type: {type(usb_mouse_identifiers)}')

        for ident in usb_mouse_identifiers:
            if not isinstance(ident, str):
                raise RuntimeError(f'invalid identifier entry type: {type(ident)}')

        return TouchpadConfig(touchpad_identifier, usb_mouse_identifiers)


##########################################################################################
# Internal functions
##########################################################################################

def _internal_ctrl(cfg: TouchpadConfig, command: str) -> None:
    '''
    Internal control helper.

    Arguments:
        command - command to execute
    '''

    if cfg.touchpad_identifier is None:
        return

    user_id = get_active_user()
    if user_id is None:
        return

    ipc_socket = get_sway_ipc(user_id)
    if ipc_socket is None:
        return

    conn = I3Connection(socket_path=ipc_socket.as_posix())

    replies = conn.command(f'input {cfg.touchpad_identifier} events {command}')
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

def touchpad_auto(cfg: TouchpadConfig) -> None:
    '''
    Perform auto-configuration of touchpad.
    '''

    command = 'enabled'

    for id in cfg.usb_mouse_identifiers:
        path = Path(_input_node_template.format(id))

        if path.exists():
            command = 'disabled'
            break

    _internal_ctrl(cfg, command)

def touchpad_udev(cfg: TouchpadConfig, usb_interface: str) -> None:
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

    _internal_ctrl(cfg, command)


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

    parser.add_argument('-m', '--mode', required=True, choices=('auto', 'udev'), help='Operation mode')
    parser.add_argument('-u', '--usb-interface', help='USB interface number for UDev mode')

    parsed_args = parser.parse_args(args[1:])

    if parsed_args.mode is None:
        print('error: missing mode argument', file=sys.stderr)

        return 1

    try:
        config = TouchpadConfig.from_path(_config_path)

    except Exception as exc:
        print(f'error: valid to read config from path: {_config_path}: {exc}', file=sys.stderr)

        return 2

    if parsed_args.mode == 'auto':
        try:
            touchpad_auto(config)

        except Exception as exc:
            print(f'error: failed to auto-configure touchpad: {exc}', file=sys.stderr)

            return 3

    elif parsed_args.mode == 'udev':
        if parsed_args.usb_interface is None:
            print('error: missing USB interface argument', file=sys.stderr)

            return 4

        try:
            touchpad_udev(config, parsed_args.usb_interface)

        except Exception as exc:
            print(f'error: failed to handle touchpad UDev event: {exc}', file=sys.stderr)

            return 5

    return 0
