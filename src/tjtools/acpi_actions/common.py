# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


from __future__ import annotations


##########################################################################################
# Imports
##########################################################################################

from ctypes import addressof, c_uint8, c_int32, memmove, sizeof, Structure
from dataclasses import dataclass
from enum import IntEnum
from json import loads as jloads
from pathlib import Path
from socket import socket, AF_UNIX, SOCK_DGRAM


##########################################################################################
# Constants
##########################################################################################

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

class SimpleCommandFrame(Structure):
    _pack_ = 1
    _fields_ = (
        ('type', c_uint8),
        ('len', c_uint8),
    )

    def serialize(self) -> bytearray:
        self_size = sizeof(ModifyStateFrame)
        buf = (c_uint8 * self_size)()

        memmove(addressof(buf), addressof(self), self_size)

        return bytearray(buf)


##########################################################################################
# Dataclass definitions
##########################################################################################

@dataclass(frozen=True)
class ActionConfig:
    '''
    Dataclass encoding the ACPI actions configuration.

    notify_user         - user used to emit notify events
    ac_adapter_sysfs    - sysfs name of the AC adapter
    ac_adapter_device   - ACPI device name of the AC adapter
    battery_device      - ACPI device name of the battery
    wmi_device          - ACPI device name of the WMI
    power_button        - ACPI device name of the power button
    sleep_button        - ACPI device name of the sleep button
    lid_button          - ACPI device name of the lid button
    brightness_modifier - modified value applied when changing display brightness
    '''

    notify_user: str
    ac_adapter_sysfs: str
    ac_adapter_device: str
    battery_device: str
    wmi_device: str
    power_button: str
    sleep_button: str
    lid_button: str
    brightness_modifier: int

    _entries = (
        'notify-user',
        'ac-adapter-sysfs',
        'ac-adapter-device',
        'battery-device',
        'wmi-device',
        'power-button',
        'sleep-button',
        'lid-button',
        'brightness-modifier'
    )

    @staticmethod
    def from_path(path: Path) -> ActionConfig:
        '''
        Create a ACPI actions config from a config path.

        Arguments:
            path - path from where we read the config
        '''

        if not path.is_file():
            raise RuntimeError(f'config path is not a file: {path}')

        config_raw = path.read_text(encoding='utf-8')
        config_data = jloads(config_raw)

        for entry in ActionConfig._entries:
            if not entry in config_data:
                raise RuntimeError(f'config entry missing: {entry}')

        notify_user = config_data['notify-user']
        ac_adapter_sysfs = config_data['ac-adapter-sysfs']
        ac_adapter_device = config_data['ac-adapter-device']
        battery_device = config_data['battery-device']
        wmi_device = config_data['wmi-device']
        power_button = config_data['power-button']
        sleep_button = config_data['sleep-button']
        lid_button = config_data['lid-button']

        for string_val in (notify_user, ac_adapter_sysfs, ac_adapter_device, battery_device, power_button, sleep_button, lid_button):
            if not isinstance(string_val, str) and string_val is not None:
                raise RuntimeError(f'invalid string value: {string_val}')

        brightness_modifier = config_data['brightness-modifier']

        if (not isinstance(brightness_modifier, int) or brightness_modifier <= 0) and brightness_modifier is not None:
            raise RuntimeError(f'invalid modifer value: {brightness_modifier}')

        return ActionConfig(
            notify_user,
            ac_adapter_sysfs,
            ac_adapter_device,
            battery_device,
            power_button,
            sleep_button,
            lid_button,
            brightness_modifier
        )


##########################################################################################
# Class definitions
##########################################################################################

class BrightnessControl:
    def _simple_command(self, cmd_type: CommandType) -> None:
        '''
        Execute a simple brightness control command.

        Arguments:
            cmd_type - type of the command

        Simple commands have a length of zero.
        '''

        if self.client is None:
            return

        frame = SimpleCommandFrame()

        frame.type = cmd_type
        frame.len  = 0

        self.client.sendall(frame.serialize())

    def __init__(self):
        '''
        Constructor.
        '''

        config_data = jloads(_config_path.read_text(encoding='utf8'))

        self.client = None

        socket_path = config_data.get('socket-path')
        if socket_path is None or not Path(socket_path).is_socket():
            return

        self.client = socket(AF_UNIX, SOCK_DGRAM)

        self.client.connect(socket_path)

    def modify_brightness(self, value: int) -> None:
        '''
        Modify the backlight brightness.

        Arguments:
            value - signed value to apply to current brightness
        '''

        if self.client is None:
            return

        frame = ModifyStateFrame()

        frame.type  = CommandType.ModifyState
        frame.len   = 4
        frame.value = value

        self.client.sendall(frame.serialize())

    def save_state(self) -> None:
        self._simple_command(CommandType.SaveState)

    def restore_state(self) -> None:
        self._simple_command(CommandType.RestoreState)

    def set_powersave(self) -> None:
        self._simple_command(CommandType.SetPowersave)
