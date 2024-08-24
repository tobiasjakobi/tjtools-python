# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


from __future__ import annotations


##########################################################################################
# Imports
##########################################################################################

import sys

from dataclasses import dataclass
from enum import IntEnum, unique
from json import loads as jloads
from pathlib import Path
from re import compile as rcompile
from typing import Any

from .sysfs_helper import read_sysfs, get_parent_device


##########################################################################################
# Constants
##########################################################################################

'''
sysfs base path for hardware monitoring devices.
'''
_sysfs_base = Path('/sys/class/hwmon')

'''
Path to config file for the sensors.
'''
_config_path = Path('~/.config/mysensors.conf')

_hwmon_re = rcompile('^hwmon[0-9]+$')
_label_re = rcompile('^temp[0-9]+_label$')


##########################################################################################
# Enumerator definitions
##########################################################################################

@unique
class SensorType(IntEnum):
    '''
    Enumerator for sensor type.

    Default - default sensor type
    ATA     - ATA sensor type
    '''

    Default = 0
    ATA     = 1

    @staticmethod
    def from_json(raw_data: Any) -> SensorType:
        '''
        Parse a sensor type from raw JSON data.

        Arguments:
            raw_data - the raw input data

        Returns None on invalid input.
        '''

        if not isinstance(raw_data, str):
            return None

        if raw_data == 'default':
            return SensorType.Default
        elif raw_data == 'ata':
            return SensorType.ATA
        else:
            return None


##########################################################################################
# Class definitions
##########################################################################################

@dataclass(frozen=True)
class SensorIdentifier:
    '''
    Dataclass encoding identifier for the default sensor type.

    vendor_id - vendor ID of the underlying device
    device_id - device ID of the underlying device
    '''

    vendor_id: int
    device_id: int

    def is_match(self, path: Path) -> bool:
        '''
        Check if a sysfs device path matches the identifier.

        Arguments:
            path - the sysfs device path
        '''

        device_path = path / 'device'
        vendor_path = path / 'vendor'

        try:
            device_id = int(read_sysfs(device_path), 16)
            vendor_id = int(read_sysfs(vendor_path), 16)

        except (ValueError, TypeError):
            return False

        return vendor_id == self.vendor_id and device_id == self.device_id

    @staticmethod
    def from_json(raw_data: Any) -> SensorIdentifier:
        '''
        Parse a sensor identifier from raw JSON data.

        Arguments:
            raw_data - the raw input data

        Returns None on invalid input.
        '''

        if not isinstance(raw_data, dict):
            return None

        for entry in ('vendor_id', 'device_id'):
            if not isinstance(raw_data.get(entry), str):
                return None

        try:
            vendor_id = int(raw_data['vendor_id'], 16)
            device_id = int(raw_data['device_id'], 16)

        except (ValueError, TypeError):
            return None

        return SensorIdentifier(vendor_id, device_id)

@dataclass(frozen=True)
class ATASensorIdentifer:
    '''
    Dataclass encoding identifier for the ATA sensor type.

    vendor   - vendor string of the underlying ATA device
    model    - model string of the underlying ATA device
    revision - revision string of the underlying ATA device
    '''

    vendor: str
    model: str
    revision: str

    def is_match(self, path: Path) -> bool:
        '''
        Check if a sysfs device path matches the identifier.

        Arguments:
            path - the sysfs device path
        '''

        vendor = read_sysfs(path / 'vendor')
        model = read_sysfs(path / 'model')
        revision = read_sysfs(path / 'rev')

        return vendor == self.vendor and model == self.model and revision == self.revision

    @staticmethod
    def from_json(raw_data: Any) -> ATASensorIdentifer:
        '''
        Parse a ATA sensor identifier from raw JSON data.

        Arguments:
            raw_data - the raw input data

        Returns None on invalid input.
        '''

        if not isinstance(raw_data, dict):
            return None

        for entry in ('vendor', 'model', 'revision'):
            if not isinstance(raw_data.get(entry), str):
                return None

        return ATASensorIdentifer(
            raw_data['vendor'],
            raw_data['model'],
            raw_data['revision'],
        )

@dataclass(frozen=True)
class SensorDescriptor:
    '''
    Dataclass encoding a sensor descriptor.

    description     - human readable description of the sensor
    sensor_type     - type of the sensor (see the enumerator for details)
    ignore          - should we ignore this sensor descriptor?
    driver          - kernel driver of the sensor
    label           - label of the sensor
    identifier      - identifier for sensors of default type
    sata_identifier - identifier for sensors of SATA type
    '''

    description: str
    sensor_type: SensorType
    ignore: bool
    driver: str
    label: str
    identifier: SensorIdentifier
    ata_identifier: ATASensorIdentifer

    def _lookup_label(self, path: Path) -> str:
        '''
        Helper for looking up the sensor label.

        Arguments:
            path - sysfs path of sensor device
        '''

        for entry in path.iterdir():
            if not _label_re.findall(entry.name):
                continue

            sensor_label = read_sysfs(entry)
            if sensor_label == self.label:
                return entry.name

        return None

    def _identify_sensor(self, path: Path) -> SensorContext:
        '''
        Helper for identifying a sensor.

        Arguments:
            path - sysfs path of sensor device
        '''

        sensor_driver = read_sysfs(path / 'name')
        if sensor_driver != self.driver:
            return None

        if self.sensor_type == SensorType.Default:
            parent_device = get_parent_device(path)
            if not self.identifier.is_match(parent_device):
                return None
        elif self.sensor_type == SensorType.ATA:
            parent_device = path / 'device'
            if not self.ata_identifier.is_match(parent_device):
                return None
        else:
            return None

        if self.label is not None:
            label_node = self._lookup_label(path)
            if label_node is None:
                return None

            try:
                prefix, _ = label_node.rsplit('_', maxsplit=1)

            except ValueError:
                return None
        else:
            prefix = 'temp1'

        value_path = path / f'{prefix}_input'

        return SensorContext(self, value_path, parent_device)

    def get_context(self) -> SensorContext:
        '''
        Lookup a sensor using the descriptor.

        Returns a SensorContext, or None if the sensor does not exist.
        '''

        if not _sysfs_base.is_dir():
            return None

        for entry in _sysfs_base.iterdir():
            if not  _hwmon_re.findall(entry.name):
                continue

            if not entry.is_symlink():
                continue

            info = self._identify_sensor(entry)
            if info is not None:
                return info

        return None

    @staticmethod
    def from_json(descriptor_data: Any) -> SensorDescriptor:
        '''
        Parse a sensor descriptor from raw JSON data.

        Arguments:
            raw_data - the raw input data
        '''

        if not isinstance(descriptor_data, dict):
            raise RuntimeError('bad descriptor format')

        for entry in ('desc', 'type', 'ignore', 'driver', 'label', 'identifier'):
            if not entry in descriptor_data:
                raise RuntimeError(f'descriptor entry missing: {entry}')

        description = descriptor_data['desc']
        if not isinstance(description, str):
            raise RuntimeError(f'invalid description: {description}')

        raw_type = descriptor_data['type']
        sensor_type = SensorType.from_json(raw_type)
        if sensor_type is None:
            raise RuntimeError(f'invalid type: {raw_type}')

        ignore = descriptor_data['ignore']
        if not isinstance(ignore, bool):
            raise RuntimeError(f'invalid ignore flag: {ignore}')

        driver = descriptor_data['driver']
        if not isinstance(driver, str):
            raise RuntimeError(f'invalid driver: {description}')

        label = descriptor_data['label']
        if label is not None and not isinstance(label, str):
            raise RuntimeError(f'invalid label: {description}')

        raw_identifier = descriptor_data['identifier']
        if sensor_type == SensorType.Default:
            identifier = SensorIdentifier.from_json(raw_identifier)
            if identifier is None:
                raise RuntimeError(f'invalid identifier: {raw_identifier}')

            ata_identifier = None
        elif sensor_type == SensorType.ATA:
            identifier = None

            ata_identifier = ATASensorIdentifer.from_json(raw_identifier)
            if ata_identifier is None:
                raise RuntimeError(f'invalid ATA identifier: {raw_identifier}')
        else:
            raise RuntimeError(f'unknown sensor type: {sensor_type}')

        return SensorDescriptor(
            description,
            sensor_type,
            ignore,
            driver,
            label,
            identifier,
            ata_identifier,
        )

@dataclass(frozen=True)
class SensorConfiguration:
    '''
    Dataclass encoding the sensor configuration.

    sensors - dictionary mapping sensor ID to descriptor
    '''

    sensors: dict[str, SensorDescriptor]

    @staticmethod
    def from_path(path: Path) -> SensorConfiguration:
        '''
        Create a sensor config from a config path.

        Arguments:
            path - path from where we read the config
        '''

        if not path.is_file():
            raise RuntimeError(f'config path is not a file: {path}')

        config_raw = path.read_text(encoding='utf-8')
        config_data = jloads(config_raw)

        if not isinstance(config_data, dict):
            raise RuntimeError('bad config format')

        sensors: dict[str, SensorDescriptor] = dict()

        for key, value in config_data.items():
            try:
                descriptor = SensorDescriptor.from_json(value)

            except Exception as exc:
                print(f'warn: skipping invalid descriptor entry: {key}: {exc}', file=sys.stderr)

                continue

            sensors[key] = descriptor

        return SensorConfiguration(sensors)

@dataclass(frozen=True)
class SensorContext:
    '''
    Dataclass encoding a sensor context.

    descriptor - descriptor belonging to the context
    value_path - path 
    '''

    descriptor: SensorDescriptor
    value_path: Path
    parent_path: Path

    def _read_internal(self) -> str:
        '''
        Internal read helper.
        '''

        value = read_sysfs(self.value_path)

        if value is None or not value.isdigit():
            return 'Error'

        return '{0:6.2f}°C'.format(float(int(value)) / 1000.0)

    def is_online(self) -> bool:
        '''
        Check if the sensor is online.
        '''

        status_path = self.parent_path / 'power/runtime_status'
        if not status_path.is_file():
            return False

        runtime_status = read_sysfs(status_path)
        if runtime_status is None:
            return False

        return runtime_status == 'active'

    def read(self) -> str:
        '''
        Read current sensor value.
        '''

        if not self.is_online():
            return 'N/A'

        return self._read_internal()

    def gpu_busy(self) -> int:
        '''
        Read the GPU busy ratio of the sensor's parent device.

        Reading the busy ratio is only supported if the parent device is a GPU.
        '''

        if not self.is_online():
            return None

        busy_path = self.parent_path / 'gpu_busy_percent'
        if not busy_path.is_file():
            return None

        value = read_sysfs(busy_path)
        if value is None or not value.isdigit():
            return None

        return int(value)


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

    sensor = args[1]

    try:
        config = SensorConfiguration.from_path(_config_path.expanduser())

    except Exception as exc:
        print(f'error: failed to read config from path: {_config_path}: {exc}', file=sys.stderr)

        return 1

    descriptor = config.sensors.get(sensor)
    if descriptor is None:
        print(f'error: unknown sensor requested: {sensor}', file=sys.stderr)

        return 2

    ctx = descriptor.get_context()
    if ctx is None:
        print('error: sensor not found', file=sys.stderr)

        return 3

    sensor_value = ctx.read()

    print(f'Sensor {sensor}: {sensor_value}', file=sys.stdout)

if __name__ == '__main__':
    sys.exit(main(sys.argv))
