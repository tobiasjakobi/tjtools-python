# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

from ctypes import addressof, c_uint8, c_int32, memmove, sizeof, Structure
from enum import IntEnum
from json import loads as jloads
from logging import Logger
from pathlib import Path
from socket import socket, AF_UNIX, SOCK_DGRAM

from .common import ActionConfig


##########################################################################################
# Constants
##########################################################################################

_subsystem = 'video'
_log_prefix = f'ACPI: {_subsystem}: '

_config_path = Path('/etc/brightness-daemon.conf')


##########################################################################################
# Enumerator definitions
##########################################################################################

class CommandType(IntEnum):
    SetState     = 0
    ModifyState  = 1
    SaveState    = 2
    RestoreState = 3
    SetPowersave = 4


##########################################################################################
# C-structs
##########################################################################################

class ModifyStateFrame(Structure):
    _pack_ = 1
    _fields_ = (
        ('type', c_uint8),
        ('len', c_uint8),
        ('value', c_int32),
    )

    def serialize(self) -> bytearray:
        self_size = sizeof(ModifyStateFrame)
        buf = (c_uint8 * self_size)()

        memmove(addressof(buf), addressof(self), self_size)

        return bytearray(buf)


##########################################################################################
# Internal functions
##########################################################################################

def _modify_brightness(value: int) -> None:
    '''
    Modify the backlight brightness.

    Arguments:
        value - signed value to apply to current brightness
    '''

    config_data = jloads(_config_path.read_text(encoding='utf8'))

    client = socket(AF_UNIX, SOCK_DGRAM)

    socket_path = config_data.get('socket-path')
    if socket_path is None or not Path(socket_path).is_socket():
        return

    client.connect(socket_path)

    frame = ModifyStateFrame()

    frame.type  = CommandType.ModifyState
    frame.len   = 4
    frame.value = value

    client.sendall(frame.serialize())


##########################################################################################
# Functions
##########################################################################################

def handle_event(lg: Logger, cfg: ActionConfig, action: str, device: str) -> int:
    '''
    Generic video handling function.

    Arguments:
        lg     - system logger
        action - action of video event
        device - device of video event
    '''

    if action == 'brightnessdown' and device == 'BRTDN':
        value = -cfg.brightness_modifier
    elif action == 'brightnessup' and device == 'BRTUP':
        value = cfg.brightness_modifier
    else:
        lg.error(_log_prefix + f'unknown action/device: {action}/{device}')

        return 1

    try:
        _modify_brightness(value)

    except Exception as exc:
        lg.error(_log_prefix + f'failed to modify brightness: {exc}')

        return 2

    return 0
