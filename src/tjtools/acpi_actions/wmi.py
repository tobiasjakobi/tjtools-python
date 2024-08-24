# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

from logging import Logger

from .common import ActionConfig


##########################################################################################
# Constants
##########################################################################################

_subsystem = 'WMI'
_log_prefix = f'ACPI: {_subsystem}: '


##########################################################################################
# Functions
##########################################################################################

def handle_event(lg: Logger, cfg: ActionConfig, action: str, device: str, identifier: str, value: str) -> int:
    '''
    Generic thermal zone handling function.

    Arguments:
        log  - system logger
        args - arguments encoding the thermal zone event
    '''

    ident = int(identifier, base=16)
    val = int(value, base=16)

    if cfg.wmi_device != device:
        lg.error(_log_prefix + f'invalid battery: {device}')

        return 1

    if action is not None or ident != 0xd0 or val != 0:
        lg.error(_log_prefix + f'invalid battery arguments: {action}:{ident}:{val}')

        return 2

    return 0
