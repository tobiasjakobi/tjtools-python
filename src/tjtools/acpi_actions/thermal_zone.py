#!/usr/bin/env python3
# -*- coding: utf-8 -*-


##########################################################################################
# Imports
##########################################################################################

from logging import Logger


##########################################################################################
# Constants
##########################################################################################

_subsystem = 'thermal zone'
_log_prefix = f'ACPI: {_subsystem}: '


##########################################################################################
# Functions
##########################################################################################

def handle_event(lg: Logger, action: str, device: str, identifier: str, value: str) -> int:
    '''
    Generic thermal zone handling function.

    Arguments:
        log  - system logger
        args - arguments encoding the thermal zone event
    '''

    lg.info(_log_prefix + f'event received')
    lg.info(_log_prefix + f'event description: action={action}, device={device}, identifier={identifier}, value={value}')

    return 0
