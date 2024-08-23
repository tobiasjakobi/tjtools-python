# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

import sys

from os import setpgrp
from select import poll, POLLIN
from signal import signal, SIGTERM
from subprocess import Popen, DEVNULL, PIPE
from time import sleep


##########################################################################################
# Internal functions
##########################################################################################

def _usage(app: str) -> None:
    print(f'Usage: {app} <source application> <logfile base>', file=sys.stdout)

def _sigterm_handler(_signo, _stack_frame) -> None:
    '''
    Raises SystemExit(0)
    '''
    sys.exit(0)


##########################################################################################
# Main
##########################################################################################

def main(args: list[str]) -> int:
    '''
    Main function.

    Arguments:
        args - list of string arguments from the CLI
    '''

    if len(args) < 3:
        _usage(args[0])

        return 0

    stdout_args = ['zstd', '-z', '-q', '-o', f'{args[2]}-stdout.log.zst']
    stderr_args = ['zstd', '-z', '-q', '-o', f'{args[2]}-stderr.log.zst']
    app_args = [args[1]]

    '''
    TODO: why do we need start_new_session here?
    '''
    app_p = Popen(app_args, stdin=DEVNULL, stdout=PIPE, stderr=PIPE, start_new_session=True)

    '''
    Use os.setpgrp to disable forwarding of signals to the zstd processes.
    '''
    stdout_p = Popen(stdout_args, stdin=PIPE, preexec_fn=setpgrp)
    stderr_p = Popen(stderr_args, stdin=PIPE, preexec_fn=setpgrp)

    stdout_poll = poll()
    stderr_poll = poll()

    stdout_poll.register(app_p.stdout, POLLIN)
    stderr_poll.register(app_p.stderr, POLLIN)

    signal(SIGTERM, _sigterm_handler)

    while True:
        try:
            done = False

            retval = app_p.poll()
            if retval != None:
                print('info: source application exited...', file=sys.stdout)

                done = True

            busy = False

            stdout_res = stdout_poll.poll(0)
            stderr_res = stderr_poll.poll(0)

            if stdout_res:
                line = app_p.stdout.readline()
                stdout_p.stdin.write(line)
                busy = True

            if stderr_res:
                line = app_p.stderr.readline()
                stderr_p.stdin.write(line)
                busy = True

            if done:
                break;

            if not busy:
                sleep(1)

        except (KeyboardInterrupt, SystemExit):
            print('info: terminating source application...', file=sys.stdout)

            app_p.terminate()

    stdout_p.stdin.close()
    stderr_p.stdin.close()

    print(f'info: application exited with return code {app_p.returncode}', file=sys.stdout)

    return 0
