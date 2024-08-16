#!/usr/bin/env python3
# -*- coding: utf-8 -*-


##########################################################################################
# Imports
##########################################################################################

import sys

from dataclasses import dataclass
from logging.handlers import SysLogHandler
from logging import Logger, getLogger
from pathlib import Path

from .sysfs_helper import get_parent_device, read_sysfs, write_sysfs


##########################################################################################
# Dataclass definitions
##########################################################################################

@dataclass(frozen=True)
class _BacklightIdentifier:
    prefix: str
    vendor_id: int
    device_id: int


##########################################################################################
# Constants
##########################################################################################

_subsystem = 'backlight'
_log_prefix = f'ACPI: {_subsystem}: '

_sysfs_base = Path('/sys/class/backlight/')
_amd_bl = _BacklightIdentifier(prefix = 'amdgpu_bl', vendor_id = 0x1002, device_id = 0x15bf)

_state_file = Path('/run/acpi_backlight')
_powersave_value = 112


##########################################################################################
# Internal functions
##########################################################################################

def _usage(app: str) -> None:
    print(f'Usage: {app}', file=sys.stdout)
    print('\t --save|--restore [save/restore brightness state]', file=sys.stdout)
    print('\t --modify <value> [modify brightness state by applying value]', file=sys.stdout)
    print('\t --powersave [set powersave brighness state]', file=sys.stdout)

def _identify_backlight(path: Path, ident: _BacklightIdentifier) -> bool:
    '''
    Identify the backlight device.

    Arguments:
        path  - sysfs path to the backlight node
        ident - backlight identfier

    Returns True if the information from the sysfs path matches
    the identifier, and False if not.
    '''

    try:
        device_id = int(read_sysfs(path / 'device'), 16)
        vendor_id = int(read_sysfs(path / 'vendor'), 16)

    except Exception:
        return False

    return vendor_id == ident.vendor_id and device_id == ident.device_id

def _lookup_backlight_node(ident: _BacklightIdentifier) -> Path:
    '''
    Lookup the sysfs path to the backlight node.

    Arguments:
        ident - backlight identfier

    Returns the sysfs path to the node, or None if nothing was found.
    '''

    if not _sysfs_base.is_dir():
        return None

    for p in _sysfs_base.iterdir():
        if not p.name.startswith(ident.prefix):
            continue

        if not p.is_symlink():
            continue

        parent = get_parent_device(p)
        if parent is None:
            continue

        if _identify_backlight(parent, ident):
            return p

    return None


##########################################################################################
# Functions
##########################################################################################

def modify_state(lg: Logger, value: str) -> int:
    '''
    Modify the backlight brightness state by applying a (signed) integer value.

    Arguments:
        lg    - system logger
        value - the integer value encoded as string
    '''

    try:
        modifier = int(value)

    except Exception as exc:
        lg.error(_log_prefix + f'failed to parse modifier argument: {exc}')

        return 1

    backlight_node = _lookup_backlight_node(_amd_bl)
    if backlight_node is None:
        lg.error(_log_prefix + 'failed to lookup backlight node')

        return 2

    sysfs_brightness = backlight_node / 'brightness'

    try:
        state = int(read_sysfs(sysfs_brightness))

    except Exception as exc:
        lg.error(_log_prefix + f'failed to query brightness state: {exc}')

        return 3

    try:
        max_state = int(read_sysfs(backlight_node / 'max_brightness'))

    except Exception as exc:
        lg.error(_log_prefix + f'failed to query maximum brightness: {exc}')

        return 4

    state += modifier

    if state > max_state:
        state = max_state
    elif state < 0:
        state = 0

    ret = write_sysfs(sysfs_brightness, state)
    if ret != 0:
        lg.error(_log_prefix + f'failed to write new brightness state: {ret}')

        return 5

    return 0

def save_state(lg: Logger) -> int:
    '''
    Save the backlight brightness to the save file.

    Arguments:
        lg - system logger
    '''

    backlight_node = _lookup_backlight_node(_amd_bl)
    if backlight_node is None:
        lg.error(_log_prefix + 'failed to lookup backlight node')

        return 1

    try:
        state = int(read_sysfs(backlight_node / 'brightness'))

    except Exception as exc:
        lg.error(_log_prefix + f'failed to query brightness state: {exc}')

        return 2

    try:
        state_bytes = state.to_bytes((state.bit_length() + 7) // 8, byteorder='little')
        _state_file.write_bytes(state_bytes)

    except Exception as exc:
        lg.error(_log_prefix + f'failed to save brightness state: {exc}')

        return 3

    return 0

def restore_state(lg: Logger) -> int:
    '''
    Restore the backlight brightness from the save file.

    Arguments:
        lg - system logger
    '''

    backlight_node = _lookup_backlight_node(_amd_bl)
    if backlight_node is None:
        lg.error(_log_prefix + 'failed to lookup backlight node')

        return 1

    sysfs_brightness = backlight_node / 'brightness'
    sysfs_max_brightness = backlight_node / 'max_brightness'

    if not _state_file.is_file():
        return 0

    try:
        state = int.from_bytes(_state_file.read_bytes(), byteorder='little')
        _state_file.unlink()

    except Exception as exc:
        lg.error(_log_prefix + f'failed to read brightness save: {exc}')

        return 2

    try:
        max_state = int(read_sysfs(sysfs_max_brightness))

    except Exception as exc:
        lg.error(_log_prefix + f'failed to query maximum brightness: {exc}')

        return 3

    if state > max_state:
        state = max_state
    elif state < 0:
        state = 0

    ret = write_sysfs(sysfs_brightness, state)
    if ret != 0:
        lg.error(_log_prefix + f'failed to restore brightness state: {ret}')

        return 4

    return 0

def set_powersave(lg: Logger) -> int:
    '''
    Set backlight brightness to powersave state.

    Arguments:
        lg - system logger
    '''

    backlight_node = _lookup_backlight_node(_amd_bl)
    if backlight_node is None:
        lg.error(_log_prefix + 'failed to lookup backlight node')

        return 1

    ret = write_sysfs(backlight_node / 'brightness', _powersave_value)
    if ret != 0:
        lg.error(_log_prefix + f'failed to set powersave state: {ret}')

        return 2

    return 0


##########################################################################################
# Main
##########################################################################################

def main(args: list[str]) -> int:
    '''
    Main function.

    Arguments:
        args - list of string arguments from the CLI
    '''

    switcher = {
        '--modify': modify_state,
        '--save': save_state,
        '--restore': restore_state,
        '--powersave': set_powersave,
    }

    if len(args) < 2:
        _usage(args[0])

        return 0

    op = args[1]

    lg = getLogger()
    lg.addHandler(SysLogHandler('/dev/log'))

    command = switcher.get(op)

    if command is None:
        lg.error(_log_prefix + f'unknown operation {op} requested')

        return 1

    ret = command(lg, *args[2:])
    if ret != 0:
        lg.error(_log_prefix + f'operation {op} failed with error: {ret}')

        return 2

    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))
