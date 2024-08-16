# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

from pathlib import Path


##########################################################################################
# Internal functions
##########################################################################################

def _is_parent_device(path: Path) -> bool:
    '''
    Check if a device path belongs to a parent device.

    Arguments:
        path - the device path to check
    '''

    for arg in ('class', 'vendor', 'device'):
        if not (path / arg).is_file():
            return False

    return True


##########################################################################################
# Functions
##########################################################################################

def get_parent_device(path: Path) -> Path:
    '''
    Get the parent device path for a device.

    Arguments:
        path - the device path to use
    '''

    parent_device = None
    current_path = path

    while True:
        if _is_parent_device(current_path):
            parent_device = current_path
            break

        next_path = current_path / 'device'
        if not next_path.is_symlink():
            break

        current_path = next_path

    return parent_device

def read_sysfs(path: Path) -> str:
    '''
    Read from a sysfs path.

    Returns the read result as a string, or None if the read failed.

    Arguments:
        path - the path from which to read
    '''
    try:
        data = path.read_text(encoding='utf-8').rstrip()

    except Exception:
        data = None

    return data

def write_sysfs(path: Path, value: int) -> int:
    '''
    Write to a sysfs path.

    Returns zero on success, or a positive error code on failure.

    Arguments:
        path  - the path to which to write
        value - the (integer) value to write
    '''

    try:
        path.write_text(str(value), encoding='utf-8')

    except Exception:
        return 1

    return 0
