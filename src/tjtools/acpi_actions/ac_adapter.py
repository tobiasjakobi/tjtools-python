# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

from logging import Logger
from pathlib import Path
from stat import S_IMODE, S_IROTH
from subprocess import run as prun

from ..sysfs_helper import read_sysfs
from .common import ActionConfig, BrightnessControl


##########################################################################################
# Constants
##########################################################################################

_state_file = Path('/run/acpi_acadapter')
_sysfs_base = Path('/sys/class/power_supply')

_subsystem = 'AC adapter'
_log_prefix = f'ACPI: {_subsystem}: '

_iconbase = 'Adwaita/symbolic/devices'


##########################################################################################
# Internal functions
##########################################################################################

def _mod_permissions(path: Path, perms: int) -> None:
    '''
    Modify the permissions of a filesystem path.

    Arguments:
        path  - the filesystem to modify
        perms - the additional permission to apply
    '''

    current = S_IMODE(path.lstat().st_mode)

    path.chmod(current | perms)

def _write_state(path: Path, state: int) -> None:
    '''
    Write an integer state to a file.

    Arguments:
        path  - path to file
        state - the integer state to wrrite
    '''

    state_bytes = state.to_bytes((state.bit_length() + 7) // 8, byteorder='little')

    path.write_bytes(state_bytes)

def _exec_notify(cfg: ActionConfig, msg: str) -> None:
    '''
    Helper to notify the user about AC adapter events.

    Arguments:
        msg - message string
    '''

    full_msg = f'Status: {msg}'
    icon = f'{_iconbase}/ac-adapter-symbolic.svg'

    p_args = ('sudo', f'--user={cfg.notify_user}', 'notify_wrapper', _subsystem, full_msg, icon)

    prun(p_args, check=True)


##########################################################################################
# Functions
##########################################################################################

def handle_init(lg: Logger, cfg: ActionConfig) -> int:
    '''
    Initialization of AC adapter handling.

    Arguments:
        lg - system logger
    '''

    ac_state = read_sysfs(_sysfs_base / cfg.ac_adapter_sysfs / 'online')

    if ac_state is None or not ac_state.isdigit():
        lg.warning(_log_prefix + 'invalid AC state (assuming offline)')
        state = 0
    else:
        state = int(ac_state)

    try:
        _write_state(_state_file, state)
        _mod_permissions(_state_file, S_IROTH)

    except Exception as exc:
        lg.error(_log_prefix + f'state file initialization failed: {exc}')

        return 1

    return 0

def handle_event(lg: Logger, cfg: ActionConfig, device: str, identifier: str) -> int:
    '''
    Generic AC adapter handling function.

    Arguments:
        log        - system logger
        device     - device of AC adapter event
        identifier - identifier of AC adapter event
    '''

    if device != cfg.ac_adapter_device:
        lg.error(_log_prefix + f'invalid AC adapter: {device}')

        return 1

    try:
        state = int(identifier)

    except ValueError as err:
        lg.error(_log_prefix + f'invalid identifier: {err}')

        return 2

    if state == 0:
        msg = 'unplugged'

        try:
            brctl = BrightnessControl()
            brctl.save_state()
            brctl.set_powersave()

        except Exception as exc:
            lg.error(_log_prefix + f'failed to save and set powersave: {exc}')
    elif state == 1:
        msg = 'plugged in'

        try:
            brctl = BrightnessControl()
            brctl.restore_state()

        except Exception as exc:
            lg.error(_log_prefix + f'failed to restore: {exc}')
    else:
        lg.error(_log_prefix + f'unknown adapter state: {state}')

        return 3

    try:
        _write_state(_state_file, state)

    except Exception as exc:
        lg.error(_log_prefix + f'state file updae failed: {exc}')

        return 4

    try:
        _exec_notify(msg)

    except Exception as exc:
        lg.error(_log_prefix + f'notify failed: {exc}')

        return 5

    return 0
