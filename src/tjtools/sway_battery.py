# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

import sys
from pathlib import Path

from .sysfs_helper import read_sysfs


##########################################################################################
# Constants
##########################################################################################

_state_file = Path('/run/acpi_acadapter')
_sysfs_base = Path('/sys/class/power_supply/BAT0')


##########################################################################################
# Functions
##########################################################################################

def read_battery() -> str:
    charge_now = _sysfs_base / 'charge_now'
    energy_now = _sysfs_base / 'energy_now'

    if charge_now.is_file():
        try:
            value_now = int(read_sysfs(charge_now))
            value_full = int(read_sysfs(_sysfs_base / 'charge_full'))

        except Exception:
            return None
    elif energy_now.is_file():
        try:
            value_now = int(read_sysfs(energy_now))
            value_full = int(read_sysfs(_sysfs_base / 'energy_full'))

        except Exception:
            return None
    else:
        return None

    try:
        ac_state = int.from_bytes(_state_file.read_bytes(), byteorder='little')

    except Exception:
        return None

    value = (value_now * 100) // value_full
    msg = 'unplugged' if ac_state == 0 else 'plugged in'

    return f'{value}% ({msg})'


##########################################################################################
# Main
##########################################################################################

def main(args: list[str]) -> int:
    '''
    Main function.

    Arguments:
        args - list of string arguments from the CLI
    '''

    ret = read_battery()
    if ret is None:
        print('error: battery not found', file=sys.stderr)

        return 1

    print(f'Battery: {ret}', file=sys.stdout)

    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))
