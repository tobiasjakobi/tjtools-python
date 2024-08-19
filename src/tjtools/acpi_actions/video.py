# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

from logging import Logger

from .common import ActionConfig, BrightnessControl


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
        value = -cfg.brightness_modifier
    elif action == 'brightnessup' and device == 'BRTUP':
        value = cfg.brightness_modifier
    else:
        lg.error(_log_prefix + f'unknown action/device: {action}/{device}')

        return 1

    try:
        brctl = BrightnessControl()
        brctl.modify_brightness(value)

    except Exception as exc:
        lg.error(_log_prefix + f'failed to modify brightness: {exc}')

        return 2

    return 0
