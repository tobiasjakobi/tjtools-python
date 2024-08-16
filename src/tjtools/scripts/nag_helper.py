# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

from argparse import ArgumentParser
from json import loads as jloads
from pathlib import Path
from subprocess import run as prun

from dbus import SystemBus, Interface as DBusInterface
from dbus.exceptions import DBusException

import sys


##########################################################################################
# Constants
##########################################################################################

_rfkill_type = 'wlan'
_powerlimit_profiles = ('default', 'quiet', 'turbo')
_powerlimit_unit = 'cpu-powerlimit@{0}.service'

_state_msg_template = 'Active CPU powerlimit profile: {0}'


##########################################################################################
# Internal functions
##########################################################################################

def _get_active_profile(bus: SystemBus) -> str:
    '''
    Get the active CPU powerlimit profile.

    Arguments:
        bus - the DBus system bus to use
    '''

    systemd1_obj = bus.get_object(bus_name='org.freedesktop.systemd1', object_path='/org/freedesktop/systemd1')
    iface = DBusInterface(object=systemd1_obj, dbus_interface='org.freedesktop.systemd1.Manager')

    active_profile = None

    for profile in _powerlimit_profiles:
        unit_name = _powerlimit_unit.format(profile)

        try:
            iface.GetUnit(unit_name)
            active_profile = profile

        except DBusException as exc:
            pass

        if active_profile is not None:
            break

    return active_profile

def _set_profile(bus: SystemBus, active_profile: str, profile: str) -> str:
    '''
    Set the CPU powerlimit profile.

    Arguments:
        bus            - the DBus system bus to use
        active_profile - CPU powerlimit that is currently active
        profile        - the profile we want to switch to
    '''

    systemd1_obj = bus.get_object(bus_name='org.freedesktop.systemd1', object_path='/org/freedesktop/systemd1')
    iface = DBusInterface(object=systemd1_obj, dbus_interface='org.freedesktop.systemd1.Manager')

    active_unit = _powerlimit_unit.format(active_profile)

    if active_profile is not None:
        iface.StopUnit(active_unit, 'fail')

    if profile is not None and profile != 'default':
        start_unit = _powerlimit_unit.format(profile)

        iface.StartUnit(start_unit, 'fail')

def _make_button(profile: str) -> tuple[str]:
    '''
    Make a swaynag button from a CPU powerlimit profile.

    Arguments:
        profile - CPU powerlimit to use
    '''

    nag_helper = Path(__file__).as_posix();

    return ('--button-dismiss-no-terminal', f'Set {profile}', f'{nag_helper} --profile-select={profile}')


##########################################################################################
# Functions
##########################################################################################

def select_cpu_powerlimit(profile: str) -> None:
    '''
    Helper for selecting the CPU powerlimit.

    Arguments:
        profile - CPU powerlimit to set

    This helper is called by swaynag.
    '''

    if not profile in ('default', 'quiet', 'turbo'):
        raise RuntimeError(f'invalid profile: {profile}')

    bus = SystemBus()

    active_profile = _get_active_profile(bus)

    _set_profile(bus, active_profile, profile)

def nag_cpu_powerlimit() -> None:
    '''
    Display a nag message for CPU powerlimit selection.
    '''

    bus = SystemBus()

    active_profile = _get_active_profile(bus)

    state_msg = _state_msg_template.format('default' if active_profile is None else active_profile)

    buttons = list()

    if active_profile is None or active_profile == 'default':
        buttons.extend(_make_button('quiet'))
        buttons.extend(_make_button('turbo'))
    elif active_profile == 'quiet':
        buttons.extend(_make_button('default'))
        buttons.extend(_make_button('turbo'))
    elif active_profile == 'turbo':
        buttons.extend(_make_button('default'))
        buttons.extend(_make_button('quiet'))
    else:
        raise RuntimeError(f'invalid active profile: {active_profile}')

    p_args = (
        '/usr/bin/swaynag',
        '--type', 'warning',
        '--message', state_msg,
        *buttons
    )

    prun(p_args, check=True, capture_output=True)

def nag_rfkill() -> None:
    '''
    Display a nag message for WiFi rfkill selection.
    '''

    p_args = ('/usr/bin/rfkill', '--json')

    p = prun(p_args, check=True, capture_output=True, encoding='utf-8')

    devices = jloads(p.stdout).get('rfkilldevices')

    radio_state = False

    for device in devices:
        if device.get('type') == _rfkill_type:
            radio_state = device.get('soft') == 'unblocked'
            break

    if radio_state:
        state_msg = 'WiFi radio on'
        button_msg = 'Switch radio off'
    else:
        state_msg = 'WiFi radio off'
        button_msg = 'Switch radio on'

    p_args = (
        '/usr/bin/swaynag',
        '--type', 'warning',
        '--message', state_msg,
        '--button-dismiss-no-terminal', button_msg, f'/usr/bin/rfkill toggle {_rfkill_type}',
    )

    prun(p_args, check=True, capture_output=True)


##########################################################################################
# Main
##########################################################################################

def main(args: list[str]) -> int:
    '''
    Main function.

    Arguments:
        args - list of string arguments from the CLI
    '''

    parser = ArgumentParser()

    parser.add_argument('-c', '--cpu-powerlimit', action='store_true', help='Spawn nag message for CPU powerlimit')
    parser.add_argument('-r', '--rfkill', action='store_true', help='Spawn nag messagee for WiFi rfkill')
    parser.add_argument('-p', '--profile-select', choices=('default', 'quiet', 'turbo'), help='Select a CPU powerlimit profile')

    parsed_args = parser.parse_args(args[1:])

    if parsed_args.cpu_powerlimit:
        try:
            nag_cpu_powerlimit()

        except Exception as exc:
            print(f'error: CPU powerlimit nag failed: {exc}', file=sys.stderr)

            return 1
    elif parsed_args.rfkill:
        try:
            nag_rfkill()

        except Exception as exc:
            print(f'error: rfkill nag failed: {exc}', file=sys.stderr)

            return 2
    elif parsed_args.profile_select:
        try:
            select_cpu_powerlimit(parsed_args.profile_select)

        except Exception as exc:
            print(f'error: CPU powerlimit select failed: {exc}', file=sys.stderr)

            return 3
    else:
        print('error: no nag mode selected', file=sys.stderr)

        return 4

    return 0
