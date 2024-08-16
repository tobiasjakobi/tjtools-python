# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

from logging import Logger


##########################################################################################
# Constants
##########################################################################################

_subsystem = 'battery'
_log_prefix = f'ACPI: {_subsystem}: '

_valid_battery = 'PNP0C0A:00'


##########################################################################################
# Functions
##########################################################################################

def handle_event(lg: Logger, device: str, identifier: str, value: str) -> int:
    '''
    Generic battery handling function.

    Arguments:
        lg         - system logger
        device     - device of battery event
        identifier - identifier of battery event
        value      - value of battery event
    '''

    if device != _valid_battery:
        lg.error(_log_prefix + f'invalid battery: {device}')

        return 1

    lg.info(_log_prefix + f'event received')
    lg.info(_log_prefix + f'event description: device={device}, identifier={identifier}, value={value}')

    return 0
