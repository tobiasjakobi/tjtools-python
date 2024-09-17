#!/usr/bin/env python3
# -*- coding: utf-8 -*-


##########################################################################################
# Imports
##########################################################################################

import sys

from datetime import datetime
from pathlib import Path
from time import sleep

from psutil import disk_partitions, disk_usage

from tjtools.sway_sensors import SensorConfiguration, SensorContext, SensorDescriptor
from tjtools.sway_battery import read_battery

'''
References:
https://unix.stackexchange.com/questions/473788/simple-swaybar-example

Additional emojis and characters for the status bar:
Electricity: ⚡ ↯ ⭍ 🔌
Audio: 🔈 🔊 🎧 🎶 🎵 🎤
Separators: \| ❘ ❙ ❚
Misc: 🐧 💎 💻 💡 ⭐ 📁 ↑ ↓ ✉ ✅ ❎
'''


##########################################################################################
# Constants
##########################################################################################

'''
Path to config file for the sensors.
'''
_config_path = Path('~/.config/mysensors.conf')


##########################################################################################
# Internal functions
##########################################################################################

def _bytes2human(n: int) -> str:
    '''
    http://code.activestate.com/recipes/578019
    >>> bytes2human(10000)
    '9.8K'
    >>> bytes2human(100001221)
    '95.4M'
    '''

    symbols = ('K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')
    prefix = {}

    for i, s in enumerate(symbols):
        prefix[s] = 1 << (i + 1) * 10

    for s in reversed(symbols):
        if n >= prefix[s]:
            value = float(n) / prefix[s]
            return f'{value:.1f}{s}'

    return f'{n}B'


##########################################################################################
# Class definitions
##########################################################################################

class SwayTopBar:
    def __init__(self, sconf_path: Path):
        sensor_config = SensorConfiguration.from_path(sconf_path)

        cpu_desc: SensorDescriptor = sensor_config.sensors.get('CPU')
        if cpu_desc is None:
            raise RuntimeError('failed to get sensor descriptor for CPU')

        igpu_desc: SensorDescriptor = sensor_config.sensors.get('iGPU')
        if igpu_desc is None:
            raise RuntimeError('failed to get sensor descriptor for iGPU')

        self._cpu_ctx: SensorContext = cpu_desc.get_context()
        if self._cpu_ctx is None:
            raise RuntimeError('failed to get sensor context for CPU')

        self._igpu_ctx: SensorContext = igpu_desc.get_context()
        if self._igpu_ctx is None:
            raise RuntimeError('failed to get sensor context for iGPU')

        self._base_interval = 1

        self._cpu_status_interval = 5
        self._igpu_status_interval = 5
        self._battery_status_interval = 8

        self._cpu_status_counter = 0
        self._igpu_status_counter = 0
        self._battery_status_counter = 0

        self._cpu_status = None
        self._gpu_status = None
        self._battery_status = None
        self._disk_space = None

    def _get_cpu_status(self) -> None:
        cur_temp = self._cpu_ctx.read()
        if cur_temp is None:
            cur_temp = '---'

        self._cpu_status = f'CPU: {cur_temp: >8}'

    def _get_igpu_status(self) -> None:
        cur_temp = self._igpu_ctx.read()
        if cur_temp is None:
            cur_temp = '---'

        self._gpu_status = f'GPU: {cur_temp: >8}'

    def _get_battery_status(self) -> None:
        bat_state = read_battery()
        if bat_state is None:
            bat_state = 'unknown'

        self._battery_status = f'🔌: {bat_state: <17}'

    def _get_disk_space(self) -> None:
        home = None

        for p in disk_partitions():
            if p.mountpoint == '/home':
                home = disk_usage(p.mountpoint)
                break

        if home is not None:
            status = f'home[{_bytes2human(home.used)}/{_bytes2human(home.total)}]'
        else:
            status = 'unknown'

        self._disk_space = f'Disk: {status}'

    def _update(self) -> None:
        if self._cpu_status_counter == 0:
            self._get_cpu_status()
            self._cpu_status_counter = self._cpu_status_interval
        else:
            self._cpu_status_counter -= 1

        if self._igpu_status_counter == 0:
            self._get_igpu_status()
            self._igpu_status_counter = self._igpu_status_interval
        else:
            self._igpu_status_counter -= 1

        if self._battery_status_counter == 0:
            self._get_battery_status()
            self._battery_status_counter = self._battery_status_interval
        else:
            self._battery_status_counter -= 1

        self._get_disk_space()

    def refresh(self) -> int:
        try:
            self._update()

            date = datetime.now().strftime('%a %Y-%m-%d %k:%M:%S')
            output = f'{self._disk_space} | {self._battery_status} | {self._gpu_status} | {self._cpu_status} | {date}'

            print(output, file=sys.stdout, flush=True)

            sleep(self._base_interval)

            return 0

        except Exception as exc:
            print(f'error: top bar refresh failed: {exc}', file=sys.stdout)

            return 1


##########################################################################################
# Main
##########################################################################################

def main(args: list[str]) -> int:
    '''
    Main function.

    Arguments:
        args - list of string arguments from the CLI
    '''

    bar = SwayTopBar(_config_path.expanduser())

    while True:
        ret = bar.refresh()
        if ret != 0:
            break

    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))
