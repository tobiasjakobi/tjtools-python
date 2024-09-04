# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

from os import environ
from pathlib import Path
from subprocess import DEVNULL, Popen, run as prun
from sys import stdout


##########################################################################################
# Constants
##########################################################################################

_soundfont = '/usr/share/sounds/sf2/FluidR3_GM.sf2'


##########################################################################################
# Internal functions
##########################################################################################

def _usage(app: str) -> None:
    print(f'Usage: {app} <DOSBox config>', file=stdout)


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

    config = args[1]

    fsynth_args = (
        'fluidsynth',
        '-a', 'pulseaudio',
        '-m', 'alsa_seq',
        '-o', 'midi.autoconnect=1',
        '-g', '1.0',
        _soundfont,
    )

    fsynth_p = Popen(fsynth_args, stdin=DEVNULL, capture_output=True, encoding='utf-8')

    dosbox_args = ['dosbox', '-conf', config]

    libpath = Path('~/local/lib').expanduser()

    dosbox_env = environ.copy()
    dosbox_env['SDL_AUDIODRIVER'] = 'pulse'
    dosbox_env['SDL_VIDEODRIVER'] = 'wayland'
    dosbox_env['LD_LIBRARY_PATH'] = libpath.as_posix()

    prun(dosbox_args, env=dosbox_env)

    fsynth_p.terminate()

    fsynth_out = fsynth_p.stdout.read().splitlines()
    fsynth_p.wait()

    print('info: fluidsynth output:', file=stdout)
    for line in fsynth_out:
        print(line, file=stdout)

    return 0
