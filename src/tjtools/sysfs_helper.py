#!/usr/bin/env python3
# -*- coding: utf-8 -*-


##########################################################################################
# Imports
##########################################################################################

from os.path import isfile, islink, join as pjoin


##########################################################################################
# Internal functions
##########################################################################################

def _is_parent_device(path: str) -> bool:
    '''
    Check if a device path belongs to a parent device.

    Arguments:
        path - the device path to check
    '''

    if not isfile(pjoin(path, 'class')):
        return False

    if not isfile(pjoin(path, 'vendor')):
        return False

    if not isfile(pjoin(path, 'device')):
        return False

    return True


##########################################################################################
# Functions
##########################################################################################

def get_parent_device(path: str) -> str:
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

        next_path = pjoin(current_path, 'device')
        if not islink(next_path):
            break

        current_path = next_path

    return parent_device

def read_sysfs(path: str) -> str:
    '''
    Read from a sysfs path.

    Returns the read result as a string, or None if the read failed.

    Arguments:
        path - the path from which to read
    '''
    try:
        with open(path, mode='r', encoding='utf-8') as f:
            data = f.read().rstrip()

    except Exception:
        data = None

    return data

def write_sysfs(path: str, value: int) -> int:
    '''
    Write to a sysfs path.

    Returns zero on success, or a positive error code on failure.

    Arguments:
        path  - the path to which to write
        value - the (integer) value to write
    '''

    try:
        with open(path, mode='w', encoding='utf-8') as f:
            f.write(str(value))

    except Exception:
        return 1

    return 0
