# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

import sys

from dataclasses import dataclass
from enum import IntEnum, unique
from os import environ as os_environ
from pathlib import Path
from subprocess import run as prun

from i3ipc import Connection as I3Connection


##########################################################################################
# Enumerator definitions
##########################################################################################

@unique
class InputType(IntEnum):
    '''
    Input type enumerator.

    DVD    - input is a DVD, either given a device or image
    BluRay - input is a BluRay, either given a device or image
    Other  - input is something else, most likely a file
    '''

    DVD    = 0
    BluRay = 1
    Other  = 2

@unique
class ConfigType(IntEnum):
    '''
    Config type enumerator.

    Sound    - config controlling sound
    Decode   - config controlling generic decode characteristics
    VideoOut - config controlling video output
    Extra    - config controlling something else
    '''

    Sound    = 0
    Decode   = 1
    VideoOut = 2
    Extra    = 3


##########################################################################################
# Dataclass definitions
##########################################################################################

@dataclass(frozen=True)
class ConfigDescriptor:
    '''
    Config descriptor.

    config_type - type of the config (see the enumerator for details)
    desc        - human readable description
    envvar      - environment variable key associated with the config
    switcher    - switcher to map envvar values to mpv profiles
    '''

    config_type: ConfigType
    desc: str
    envvar: str
    switcher: dict[str, tuple[str]]

    def process(self, profiles: list[str]) -> None:
        '''
        Process the descriptor and generate profiles.

        Arguments:
            profiles - list of mpv profiles

        This checks the environment variable and adds corresponding
        profiles to the list.
        '''

        envvar_data = os_environ.get(self.envvar)
        if envvar_data is None or len(envvar_data) == 0:
            return

        for arg in envvar_data.split(':'):
            p = self.switcher.get(arg)
            if p is None:
                print(f'warn: unknown {self.desc} option: {arg}', file=sys.stderr)
            else:
                profiles.extend(p)


##########################################################################################
# Constants
##########################################################################################

'''
Use mpv provided by system.
'''
_player_binary = 'mpv'

_config_descriptors = (
    ConfigDescriptor(
        config_type=ConfigType.Sound,
        desc='sound',
        envvar='mpv_sound',
        switcher={
            'drc': ('custom.drc',),
            'downmix': ('custom.downmix',),
        },
    ),
    ConfigDescriptor(
        config_type=ConfigType.Decode,
        desc='decode',
        envvar='mpv_decode',
        switcher={
            'swdec': ('custom.swdec',),
        },
    ),
    ConfigDescriptor(
        config_type=ConfigType.VideoOut,
        desc='video out',
        envvar='mpv_vout',
        switcher={
            'hdmi': ('custom.extern_hdmi',),
            'dp': ('custom.extern_dp',),
        },
    ),
    ConfigDescriptor(
        config_type=ConfigType.Extra,
        desc='extra',
        envvar='mpv_extra',
        switcher={
            'bigcache': ('custom.bigcache',),
            'english': ('custom.lang_en',),
        },
    ),
)

'''
Name of the default external output.
'''
_external_output = 'DP-2'


##########################################################################################
# Internal functions
##########################################################################################

def _usage(app: str) -> None:
    print(f'Usage: {app} <media URL> [optional image filename]', file=sys.stdout)

    msg = '''
media URL: e.g. dvd:// or a filename
optional image filename: filename of ISO when using dvd://, dvdnav:// or bd://


External environment variables used:
  mpv_sound  : drc (dynamic range compression)
               downmix (stereo downmix)
  mpv_decode : swdec (software decoding)
  mpv_vout   : hdmi (output on external HDMI)
               dp (output on external DisplayPort)
  mpv_extra  : bigcache (use bigger cache)
               english (use English audio+subs)
  mpv_custom : string is passed unmodified to the mpv options

  Separator for envvar options is the colon.'''

    print(msg, file=sys.stdout)

def _has_active_output(output_name: str) -> bool:
    '''
    Check if we have an active video output.

    Arguments:
        output_name - name of the video output
    '''

    conn = I3Connection()

    for output in conn.get_outputs():
        active = output.ipc_data.get('active')
        name = output.ipc_data.get('name')

        if active is not None and active and output_name == name:
            return True

    return False


##########################################################################################
# Functions
##########################################################################################

def playmedia(input_url: str, device_path: Path) -> None:
    '''
    Helper to play media.

    Arguments:
        input_url   - the input URL
        device_path - optional device path (can be None)

    This is a thin wrapper around mpv that does some automatic
    profile handling.
    '''

    if input_url.startswith('dvd://'):
        input_type = InputType.DVD
    elif input_url.startswith('bd://'):
        input_type = InputType.BluRay
    else:
        input_type = InputType.Other

    profiles: list[str] = list()

    for desc in _config_descriptors:
        desc.process(profiles)

    if _has_active_output(_external_output):
        print(f'info: using {_external_output} as preferred output')
        profiles.extend(['custom.wayland_extern'])

    config = ['--fs']

    mpv_custom = os_environ.get('mpv_custom')
    if mpv_custom is not None:
        config.extend(mpv_custom.split())

    if len(profiles) != 0:
        config.append('--profile={0}'.format(','.join(profiles)))

    if input_type == InputType.DVD:
        if device_path is not None and device_path.exists():
            config.append(f'--dvd-device={device_path.as_posix()}')

        mpv_env = None

    elif input_type == InputType.BluRay:
        if device_path is not None and device_path.exists():
            config.append(f'--bluray-device={device_path.as_posix()}')

        mpv_env = os_environ.copy()
        mpv_env.update({'LIBAACS_PATH': 'libmmbd', 'LIBBDPLUS_PATH': 'libmmbd'})

    elif input_type == InputType.Other:
        mpv_env = None

    else:
        raise RuntimeError('invalid input type')

    if os_environ.get('DEBUG') is not None:
        print(config)

    mpv_args = [_player_binary] + config + ['--', input_url]

    prun(mpv_args, env=mpv_env)


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
        _usage(args[0])

        return 0

    input_url = args[1]
    device_path = None
    if len(args) >= 3:
        device_path = Path(args[2])

    try:
        playmedia(input_url, device_path)

    except Exception as exc:
        print(f'error: failed to play media: {exc}', file=sys.stderr)

        return 1

    return 0
