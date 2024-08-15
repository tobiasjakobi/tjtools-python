#!/usr/bin/env python3
# -*- coding: utf-8 -*-


##########################################################################################
# Imports
##########################################################################################

import sys

from getopt import getopt, GetoptError
from os.path import basename, dirname, isdir, islink, realpath, join as pjoin, getsize as pgetsize
from os import getcwd, walk
from subprocess import Popen, DEVNULL, PIPE


##########################################################################################
# Internal functions
##########################################################################################

def _usage(app: str):
    print(f'Usage: {app} [--nomt] [--prefix=<filename-prefix>] [--location=<output-location>] <directory>', file=sys.stdout)

def _get_size(start_path: str) -> int:
    total_size = 0

    for dirpath, dirnames, filenames in walk(start_path):
        for f in filenames:
            fp = pjoin(dirpath, f)

            '''
            Skip if this is a symbolic link.
            '''
            if not islink(fp):
                total_size += pgetsize(fp)

    return total_size


##########################################################################################
# Main
##########################################################################################

def main(args: list) -> int:
    location = None
    prefix = None
    singlethread = False

    getopt_largs = ('help', 'nomt', 'prefix=', 'location=')

    try:
        opts, oargs = getopt(args[1:], 'hnsp:l:', getopt_largs)

    except GetoptError as err:
        print(f'error: getopt parsing failed: {err}', file=sys.stderr)
        _usage(args[0])

        return 1

    if len(oargs) != 1:
        print('error: directory argument missing', file=sys.stderr)
        _usage(args[0])

        return 2

    input_directory = oargs[0].rstrip('/')
    if not isdir(input_directory):
        print(f'error: directory not found: {input_directory}', file=sys.stderr)
        _usage(args[0])

        return 3

    for o, a in opts:
        if o in ('-h', '--help'):
            _usage(args[0])

            return 0
        elif o in ('-n', '--nomt'):
            singlethread = True
        elif o in ('-p', '--prefix'):
            prefix = a
        elif o in ('-l', '--location'):
            if not isdir(a):
                print(f'error: invalid location {a}', file=sys.stderr)

                return 2

            location = a
        else:
            assert False, 'unhandled option'

    filebase = basename(input_directory)
    working = dirname(input_directory)
    current = realpath(getcwd())
    estimated_size = _get_size(input_directory)

    if len(working) == 0:
        working = './'

    if location != None:
        current = realpath(location)

    print(f'info: estimated uncompressed size is {estimated_size} bytes', file=sys.stdout)

    output_file = '{}/{}{}.tar.zst'.format(current, '' if prefix is None else prefix, filebase)

    thread_arg = '--single-thread' if singlethread else '--threads=4'
    zstd_args = ['zstd', '--compress', thread_arg, '--ultra', '-22', f'--size-hint={estimated_size}', '-o', output_file]

    tar_args = ['tar', '--create', '--file', '-', f'--directory={working}', filebase]

    tar_p = Popen(tar_args, stdin=DEVNULL, stdout=PIPE)
    zstd_p = Popen(zstd_args, stdin=tar_p.stdout)

    tar_p.stdout.close()

    zstd_p.wait()
    tar_p.wait()

    if zstd_p.returncode != 0:
        print(f'error: zstd process failed with error code {zstd_p.returncode}', file=sys.stderr)

    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))
