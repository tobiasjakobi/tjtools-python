# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

from pathlib import Path
from typing import Mapping

from logging.handlers import SysLogHandler
from logging import getLogger

from .acpi_actions.common import ActionConfig
from .acpi_actions.ac_adapter import handle_init as ac_handle_init


##########################################################################################
# Constants
##########################################################################################

_acpi_wakeup = Path('/proc/acpi/wakeup')

'''
Path to config file for ACPI actions configuration.
'''
_config_path = Path('/etc/acpi-actions.conf')


##########################################################################################
# Functions
##########################################################################################

def acpi_init(wakeup_sources: Mapping[str, bool]) -> None:
    '''
    Initialize ACPI configuration.
    '''

    cur_wakeup = _acpi_wakeup.read_text(encoding='utf-8')

    for key, value in wakeup_sources.items():
        if not value:
            continue

        for line in cur_wakeup.splitlines():
            fields = line.split()
            if len(fields) == 0:
                continue

            if fields[0] == key:
                if fields[2] == '*enabled':
                    _acpi_wakeup.write_text(key, encoding='utf-8')
                elif fields[2] == '*disabled':
                    pass
                else:
                    raise RuntimeError(f'invalid enable state: {fields[2]}')

                break

    lg = getLogger()
    lg.addHandler(SysLogHandler('/dev/log'))

    config = ActionConfig.from_path(_config_path)

    ac_handle_init(lg, config)
