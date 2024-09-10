# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

from pathlib import Path
from subprocess import DEVNULL, run as prun
from sys import stderr


##########################################################################################
# Constants
##########################################################################################

'''
sysfs path to the clocksource the kernel is currently using.
'''
_current_clocksource = Path('/sys/devices/system/clocksource/clocksource0/current_clocksource')

'''
sysfs path to the ryzen_smu driver information (if this one is loaded).
'''
_ryzen_smu_drv = Path('/sys/kernel/ryzen_smu_drv')


##########################################################################################
# Functions
##########################################################################################

def system_perf() -> None:
    '''
    Initialize system performance configuration.
    '''

    if not _current_clocksource.is_file():
        raise RuntimeError('clocksource node not found')

    clocksource = _current_clocksource.read_text(encoding='utf-8')
    if clocksource.rstrip() != 'tsc':
        print('warn: clock source is not TSC', file=sys.stderr)

    if not _ryzen_smu_drv.is_dir():
        raise RuntimeError('Ryzen SMU driver not available')

    p_args = ('cpu_powerlimit', '--init')

    prun(p_args, check=True, stdin=DEVNULL, stderr=DEVNULL)
