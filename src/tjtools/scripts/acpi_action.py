# -*- coding: utf-8 -*-


##########################################################################################
# Imports
##########################################################################################

from logging.handlers import SysLogHandler
from logging import getLogger

from tjtools.acpi_actions.ac_adapter import handle_event as handle_ac_adapter
from tjtools.acpi_actions.battery import handle_event as handle_battery
from tjtools.acpi_actions.button import handle_event as handle_button
from tjtools.acpi_actions.jack import handle_event as handle_jack
from tjtools.acpi_actions.thermal_zone import handle_event as handle_thermal_zone
from tjtools.acpi_actions.video import handle_event as handle_video


##########################################################################################
# Constants
##########################################################################################

_log_prefix = 'ACPI: '


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
        ret = handle_ac_adapter(lg, device, value)
    elif group == 'battery':
        ret = handle_battery(lg, device, identifier, value)
    elif group == 'button':
        ret = handle_button(lg, action, device, identifier)
    elif group == 'jack':
        ret = handle_jack(lg, action, identifier)
    elif group == 'thermal_zone':
        ret = handle_thermal_zone(lg, action, device, identifier, value)
    elif group == 'video':
        ret = handle_video(lg, action, device)
    else:
        lg.error(_log_prefix + f'received event for unknown group: {group}')
        lg.error(_log_prefix + f'event description: action={action}, device={device}, identifier={identifier}, value={value}')

        return 1

    if ret != 0:
        lg.error(_log_prefix + f'event handling failed with error: {ret}')

        return 2

    return 0
