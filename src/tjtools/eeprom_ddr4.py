# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

from collections.abc import Iterable
from pathlib import Path
from re import compile as rcompile

from .sysfs_helper import read_sysfs, write_sysfs


##########################################################################################
# Variables
##########################################################################################

_sysfs_base = Path('/sys/bus/i2c/devices')
_identifier = 'SMBus PIIX4 adapter port 0 at 0b00'

_i2c_re = rcompile('^i2c-[0-9]+$')


##########################################################################################
# Internal functions
##########################################################################################

def _identify_i2c_dev(path: Path, identifier: str) -> bool:
    '''
    Identify an I2C device.

    Arguments:
        path       - sysfs base path of the I2C device
        identifier - identifier to check against
    '''

    return read_sysfs(path / 'name') == identifier


##########################################################################################
# Functions
##########################################################################################

def eeprom_ddr4(i2c_addresses: Iterable[int]) -> None:
    '''
    Configure access to the EEPROM of the DDR4 modules.
    '''

    if not isinstance(i2c_addresses, Iterable):
        raise RuntimeError(f'invalid I2C addresses: {i2c_addresses}')

    if not _sysfs_base.is_dir():
        raise RuntimeError(f'sysfs base not found: {_sysfs_base}')

    i2c_dev = None

    for child in _sysfs_base.iterdir():
        if not _i2c_re.findall(child.name):
            continue

        if not child.is_symlink():
            continue

        if _identify_i2c_dev(child, _identifier):
            i2c_dev = child
            break

    if i2c_dev is None:
        raise RuntimeError('I2C device not found')

    for addr in i2c_addresses:
        addr_hex = hex(addr)

        ret = write_sysfs(child / 'new_device', f'ee1004 {addr_hex}')
        if ret != 0:
            raise RuntimeError(f'failed to bind device to ee1004: {addr_hex}: {ret}')
