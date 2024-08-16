#!/usr/bin/env python3
# -*- coding: utf-8 -*-


##########################################################################################
# Imports
##########################################################################################

from logging import Logger
from subprocess import run as prun

from .common import ActionConfig


##########################################################################################
# Constants
##########################################################################################

_subsystem = 'jack'
_log_prefix = f'ACPI: {_subsystem}: '

_iconbase = 'Adwaita/symbolic/devices'


##########################################################################################
# Internal functions
##########################################################################################

def _exec_notify(notify_user: str, source: str, msg: str, icon: str) -> None:
    '''
    Helper to notify the user about jack events.

    Arguments:
        source - source of the event
        msg    - message string
        icon   - icon to display with message
    '''

    full_msg = f'Status: {msg}ged'
    full_icon = f'{_iconbase}/{icon}-symbolic.svg'

    p_args = ('sudo', f'--user={notify_user}', 'notify_wrapper', source, full_msg, full_icon)

    prun(p_args, check=True)


##########################################################################################
# Functions
##########################################################################################

def handle_event(lg: Logger, cfg: ActionConfig, action: str, identifier: str) -> int:
    '''
    Generic jack handling function.

    Arguments:
        lg         - system logger
        action     - action of jack event
        identifier - identifier of jack event
    '''

    if action == 'headphone':
        msg_device = 'Headphones'
        msg_icon = 'audio-headphones'
    elif action == 'videoout':
        msg_device = 'Video output'
        msg_icon = 'video-single-display'
    elif action == 'lineout':
        msg_device = 'Line out'
        msg_icon = 'audio-speakers'
    else:
        lg.error(_log_prefix + f'unknown action: {action}')

        return 1

    try:
        _exec_notify(cfg.notify_user, msg_device, identifier, msg_icon)

    except Exception as exc:
        lg.error(_log_prefix + f'notify failed: {exc}')

        return 1

    return 0
