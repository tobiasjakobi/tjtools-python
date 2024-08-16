# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

from logging import Logger

from ..brightness import modify_state as modify_brightness
from .common import ActionConfig


##########################################################################################
# Constants
##########################################################################################

_subsystem = 'video'
_log_prefix = f'ACPI: {_subsystem}: '


##########################################################################################
# Functions
##########################################################################################

def handle_event(lg: Logger, cfg: ActionConfig, action: str, device: str) -> int:
    '''
    Generic video handling function.

    Arguments:
        lg     - system logger
        action - action of video event
        device - device of video event
    '''

    if action == 'brightnessdown' and device == 'BRTDN':
        value = str(-cfg.brightness_modifier)
    elif action == 'brightnessup' and device == 'BRTUP':
        value = str(cfg.brightness_modifier)
    else:
        lg.error(_log_prefix + f'unknown action/device: {action}/{device}')

        return 1

    ret = modify_brightness(lg, value)
    if ret != 0:
        lg.error(_log_prefix + f'failed to modify brightness: {ret}')

        return 2

    return 0
