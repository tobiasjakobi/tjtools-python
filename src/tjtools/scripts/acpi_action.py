# -*- coding: utf-8 -*-


##########################################################################################
# Imports
##########################################################################################

from logging.handlers import SysLogHandler
from logging import getLogger
from pathlib import Path

from ..acpi_actions.common import ActionConfig

from ..acpi_actions.ac_adapter import handle_event as handle_ac_adapter
from ..acpi_actions.battery import handle_event as handle_battery
from ..acpi_actions.button import handle_event as handle_button
from ..acpi_actions.jack import handle_event as handle_jack
from ..acpi_actions.thermal_zone import handle_event as handle_thermal_zone
from ..acpi_actions.video import handle_event as handle_video


##########################################################################################
# Constants
##########################################################################################

_log_prefix = 'ACPI: '

'''
Path to config file for ACPI actions configuration.
'''
_config_path = Path('/etc/acpi-actions.conf')


##########################################################################################
# Main
##########################################################################################

def main(args: list[str]) -> int:
    '''
    Main function.

    Arguments:
        args - list of string arguments from the CLI
    '''

    if len(args) < 2:
        return 0

    lg = getLogger()
    lg.addHandler(SysLogHandler('/dev/log'))

    try:
        config = ActionConfig.from_path(_config_path)

    except Exception as exc:
        lg.error(_log_prefix + f'error: valid to read config from path: {_config_path}: {exc}')

        return 1

    try:
        group, action = args[1].split('/', maxsplit=1)

    except ValueError:
        group = args[1]
        action = None

    if len(args) > 2:
        device = args[2]
    else:
        device = None

    if len(args) > 3:
        identifier = args[3]
    else:
        identifier = None

    if len(args) > 4:
        value = args[4]
    else:
        value = None

    if group == 'ac_adapter':
        ret = handle_ac_adapter(lg, config, device, value)
    elif group == 'battery':
        ret = handle_battery(lg, config, device, identifier, value)
    elif group == 'button':
        ret = handle_button(lg, config, action, device, identifier)
    elif group == 'jack':
        ret = handle_jack(lg, config, action, identifier)
    elif group == 'thermal_zone':
        ret = handle_thermal_zone(lg, config, action, device, identifier, value)
    elif group == 'video':
        ret = handle_video(lg, config, action, device)
    else:
        lg.error(_log_prefix + f'received event for unknown group: {group}')
        lg.error(_log_prefix + f'event description: action={action}, device={device}, identifier={identifier}, value={value}')

        return 2

    if ret != 0:
        lg.error(_log_prefix + f'event handling failed with error: {ret}')

        return 3

    return 0
