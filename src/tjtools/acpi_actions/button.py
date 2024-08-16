# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

from logging import Logger
from pathlib import Path
from time import time

from ..blank_screen import blank_screen

from dbus import SystemBus, Interface as DBusInterface


##########################################################################################
# Constants
##########################################################################################

_subsystem = 'button'
_log_prefix = f'ACPI: {_subsystem}: '

'''
Maximum delay between two button presses (in milliseconds).
'''
_max_delay = 2400.0

_state_power_button = Path('/run/acpi_powerbutton')
_state_sleep_button = Path('/run/acpi_sleepbutton')

'''
System has three powerbutton ACPI devices (PBTN, LNXPWRBN:00 and PNP0C0C:00).
Also PBTN creates two ACPI events each time the button is pressed.
So we only react to LNXPWRBN:00.
'''
_valid_power_button = 'PBTN'
_valid_sleep_button = 'SBTN'
_valid_lid_button = 'LID'


##########################################################################################
# Internal functions
##########################################################################################

def _poweroff_system() -> None:
    '''
    Helper for powering off the system.
    '''

    bus = SystemBus()
    login1 = bus.get_object(bus_name='org.freedesktop.login1', object_path='/org/freedesktop/login1')
    iface = DBusInterface(login1, dbus_interface='org.freedesktop.login1.Manager')

    iface.PowerOff(False)

def _suspend_system() -> None:
    '''
    Helper for suspending the system.
    '''

    bus = SystemBus()
    login1 = bus.get_object(bus_name='org.freedesktop.login1', object_path='/org/freedesktop/login1')
    iface = DBusInterface(login1, dbus_interface='org.freedesktop.login1.Manager')

    iface.Suspend(False)

def _lid_button(device: str, identifier: str) -> None:
    '''
    Handling of lid button event.

    Arguments:
        device     - device of event
        identifier - identifier of event
    '''

    if device != _valid_lid_button:
        raise RuntimeError(f'invalid lid button: {device}')

    if identifier not in ('open', 'close'):
        raise RuntimeError(f'unknown lid state: {identifier}')

def _sleep_button(device: str) -> None:
    '''
    Handling of sleep button event.

    Arguments:
        device - device of event
    '''

    if device != _valid_sleep_button:
        return

    try:
        last_time = int.from_bytes(_state_sleep_button.read_bytes(), byteorder='little')

    except Exception:
        last_time = None

    cur_time = int(time() * 1000.0)

    state_bytes = cur_time.to_bytes((cur_time.bit_length() + 7) // 8, byteorder='little')
    _state_sleep_button.write_bytes(state_bytes)

    if last_time is None:
        return

    if abs(cur_time - last_time) < _max_delay:
        _suspend_system()

def _power_button(device: str) -> None:
    '''
    Handling of power button event.

    Arguments:
        device - device of event
    '''

    if device != _valid_power_button:
        return

    try:
        last_time = int.from_bytes(_state_power_button.read_bytes(), byteorder='little')

    except Exception:
        last_time = None

    cur_time = int(time() * 1000.0)

    state_bytes = cur_time.to_bytes((cur_time.bit_length() + 7) // 8, byteorder='little')
    _state_power_button.write_bytes(state_bytes)

    if last_time is None:
        blank_screen(None)
    else:
        if abs(cur_time - last_time) < _max_delay:
            _poweroff_system()
        else:
             blank_screen(None)

def _volume_button(device: str, identifier: str) -> None:
    '''
    Handling of volume button event.

    Arguments:
        device     - device of event
        identifier - identifier of event
    '''

    if device != '00000080':
        raise RuntimeError(f'unknown volume button: {device}')

def _direction_pad(device: str) -> None:
    '''
    Handling of direction pad event.

    Arguments:
        device - device of event
    '''

    if device.lower() in ('up', 'down', 'left', 'right'):
        return

    if device != '00000080':
        raise RuntimeError(f'unknown direction pad: {device}')


##########################################################################################
# Functions
##########################################################################################

def handle_event(lg: Logger, action: str, device: str, identifier: str) -> int:
    '''
    Generic button handling function.

    Arguments:
        lg         - system logger
        action     - action of button event
        device     - device of button event
        identifier - identifier of button event
    '''

    try:
        if action == 'power':
            _power_button(device)
        elif action == 'sleep':
            _sleep_button(device)
        elif action == 'lid':
            _lid_button(device, identifier)
        elif action in ('volumedown', 'volumeup'):
            _volume_button(device, identifier)
        elif action in ('up', 'down', 'left', 'right'):
            _direction_pad(device)
        else:
            lg.error(_log_prefix + f'unknown action: {action}')

            return 2

    except RuntimeError as err:
        lg.error(_log_prefix + f'error handling button: {err}')

        return 3

    return 0
