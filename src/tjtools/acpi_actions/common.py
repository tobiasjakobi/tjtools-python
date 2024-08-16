# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


from __future__ import annotations


##########################################################################################
# Imports
##########################################################################################

from dataclasses import dataclass
from json import loads as jloads
from pathlib import Path


##########################################################################################
# Dataclass definitions
##########################################################################################

@dataclass(frozen=True)
class ActionConfig:
    '''
    Dataclass encoding the ACPI actions configuration.

    notify_user         - user used to emit notify events
    ac_adapter_sysfs    - sysfs name of the AC adapter
    ac_adapter_device   - ACPI device name of the AC adapter
    battery_device      - ACPI device name of the battery
    power_button        - ACPI device name of the power button
    sleep_button        - ACPI device name of the sleep button
    lid_button          - ACPI device name of the lid button
    brightness_modifier - modified value applied when changing display brightness
    '''

    notify_user: str
    ac_adapter_sysfs: str
    ac_adapter_device: str
    battery_device: str
    power_button: str
    sleep_button: str
    lid_button: str
    brightness_modifier: int

    _entries = (
        'notify-user',
        'ac-adapter-sysfs',
        'ac-adapter-device',
        'battery-device',
        'power-button',
        'sleep-button',
        'lid-button',
        'brightness-modifier'
    )

    @staticmethod
    def from_path(path: Path) -> ActionConfig:
        '''
        Create a ACPI actions config from a config path.

        Arguments:
            path - path from where we read the config
        '''

        if not path.is_file():
            raise RuntimeError(f'config path is not a file: {path}')

        config_raw = path.read_text(encoding='utf-8')
        config_data = jloads(config_raw)

        for entry in ActionConfig._entries:
            if not entry in config_data:
                raise RuntimeError(f'config entry missing: {entry}')

        notify_user = config_data['notify-user']
        ac_adapter_sysfs = config_data['ac-adapter-sysfs']
        ac_adapter_device = config_data['ac-adapter-device']
        battery_device = config_data['battery-device']
        power_button = config_data['power-button']
        sleep_button = config_data['sleep-button']
        lid_button = config_data['lid-button']

        for string_val in (notify_user, ac_adapter_sysfs, ac_adapter_device, battery_device, power_button, sleep_button, lid_button):
            if not isinstance(string_val, str):
                raise RuntimeError(f'invalid string value: {string_val}')

        brightness_modifier = config_data['brightness-modifier']

        if not isinstance(brightness_modifier, int) or brightness_modifier <= 0:
            raise RuntimeError(f'invalid modifer value: {brightness_modifier}')

        return ActionConfig(
            notify_user,
            ac_adapter_sysfs,
            ac_adapter_device,
            battery_device,
            power_button,
            sleep_button,
            lid_button,
            brightness_modifier
        )