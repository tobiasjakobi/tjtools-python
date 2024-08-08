#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations


##########################################################################################
# Imports
##########################################################################################

import sys

from dataclasses import dataclass
from json import loads as jloads
from pathlib import Path
from struct import pack
from time import sleep


##########################################################################################
# Constants
##########################################################################################

'''
Path to config file for the sandbox.
'''
_config_path = Path('/etc/razer-config.conf')

'''
Path to sysfs HID devices.
'''
_hid_path = Path('/sys/bus/hid/devices')

_serial_retries = 10


##########################################################################################
# Dataclass definitions
##########################################################################################

@dataclass(frozen=True)
class DeviceIdentifier:
    '''
    Dataclass encoding the Razer device identifier.

    vendor_id  - vendor ID of the device
    product_id - product ID of the device
    '''

    vendor_id: int
    product_id: int

    @staticmethod
    def from_args(args: list[str]) -> DeviceIdentifier:
        '''
        Create a device identifier from CLI arguments.

        Arguments:
            args - list of CLI string arguments
        '''

        if len(args) != 1:
            return None

        try:
            vendor_id, product_id = map(lambda x: int(x, 16), args[0].split(':'))

        except ValueError:
            return None

        return DeviceIdentifier(vendor_id, product_id)

    @staticmethod
    def from_path(path: Path) -> DeviceIdentifier:
        '''
        Create a device identifier from a sysfs HID device path.

        Arguments:
            path - path to sysfs HID device
        '''

        try:
            prefix, _ = path.name.split('.')

        except ValueError:
            return None

        try:
            _, vendor_id, product_id = map(lambda x: int(x, 16), prefix.split(':'))

        except ValueError:
            return None

        return DeviceIdentifier(vendor_id, product_id)

@dataclass(frozen=True)
class RazerConfig:
    '''
    Dataclass encoding the Razer configuration.

    device_type   - device type string
    device_serial - device serial string
    dpi_x         - DPI in x-direction
    dpi_y         - DPI in -direction
    '''

    device_type: str
    device_serial: str
    dpi_x: int
    dpi_y: int

    @staticmethod
    def from_path(path: Path) -> RazerConfig:
        '''
        Create a Razer config from a config path.

        Arguments:
            path - path from where we read the config
        '''

        if not path.is_file():
            raise RuntimeError(f'config path is not a file: {path}')

        config_raw = path.read_text(encoding='utf-8')
        config_data = jloads(config_raw)

        for entry in ('device-type', 'device-serial', 'dpi-x', 'dpi-y'):
            if not entry in config_data:
                raise RuntimeError(f'config entry missing: {entry}')

        device_type = config_data['device-type']
        if not isinstance(device_type, str):
            raise RuntimeError(f'invalid device type: {device_type}')

        device_serial = config_data['device-serial']
        if not isinstance(device_serial, str):
            raise RuntimeError(f'invalid device serial: {device_serial}')

        dpi_x = config_data['dpi-x']
        dpi_y = config_data['dpi-y']

        for val in (dpi_x, dpi_y):
            if not isinstance(val, int) or val <= 0:
                raise RuntimeError(f'invalid DPI value: {val}')

        return RazerConfig(device_type, device_serial, dpi_x, dpi_y)


##########################################################################################
# Internal functions
##########################################################################################

def _do_config(config: RazerConfig, device_node: Path) -> None:
    '''
    Do the actual configuration of a given device.

    Arguments:
        config      - the Razer config to use
        device_node - path to the sysfs HID device node
    '''

    serial_path = device_node / Path('device_serial')

    logo_led = device_node / Path('logo_led_brightness')
    scroll_led = device_node / Path('scroll_led_brightness')
    dpi_path = device_node / Path('dpi')

    sleep(1.0)

    serial_ok = False
    retry = 0
    while True:
        serial = serial_path.read_text(encoding='utf-8').rstrip()

        if serial == config.device_serial:
            serial_ok = True
            break

        if retry == _serial_retries:
            break

        retry += 1
        sleep(0.5)

    if not serial_ok:
        raise RuntimeError('failed to verify device serial')

    logo_led.write_text('0', encoding='utf-8')
    scroll_led.write_text('0', encoding='utf-8')
    dpi_path.write_bytes(pack(">HH", config.dpi_x, config.dpi_y))


##########################################################################################
# Functions
##########################################################################################

def razer_config(config: RazerConfig, ident: DeviceIdentifier) -> None:
    '''
    Perform configuration of Razer HID devices.

    Arguments:
        config - the Razer config to use
        ident  - device identifier to use for device lookup
    '''

    razer_nodes: list[Path] = list()
    for entry in _hid_path.iterdir():
        if not entry.is_symlink():
            continue

        entry_ident = DeviceIdentifier.from_path(entry)
        if entry_ident is None:
            continue

        if ident == entry_ident:
            razer_nodes.append(entry)

    node = None
    for arg in razer_nodes:
        device_type = arg / Path('device_type')
        if not device_type.is_file():
            continue

        if device_type.read_text(encoding='utf-8').rstrip() == config.device_type:
            node = arg
            break

    if node is None:
        raise RuntimeError('failed to locate Razer HID node')

    print(f'info: selected HID node: {node}', file=sys.stdout)

    try:
        _do_config(config, node)

    except Exception as exc:
        raise RuntimeError(f'failed to set configuration: {exc}') from exc


##########################################################################################
# Main
##########################################################################################

def main(args: list[str]) -> int:
    '''
    Main function.

    Arguments:
        args - list of string arguments from the CLI
    '''

    try:
        config = RazerConfig.from_path(_config_path)

    except Exception as exc:
        print(f'error: valid to read config from path: {_config_path}: {exc}', file=sys.stderr)

        return 1

    ident = DeviceIdentifier.from_args(args[1:])
    if ident is None:
        print(f'error: failed to parse device identifier: {args[1:]}', file=sys.stderr)

        return 2

    try:
        razer_config(config, ident)

    except Exception as exc:
        print(f'error: failed to configure Razer device: {exc}', file=sys.stderr)

        return 3

    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))
