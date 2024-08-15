#!/usr/bin/env python3
# -*- coding: utf-8 -*-


##########################################################################################
# Imports
##########################################################################################

import sys

from os.path import expanduser


##########################################################################################
# Constants
##########################################################################################

_filename = expanduser('~/.bash_history')


##########################################################################################
# Main
##########################################################################################

def main(args: list[str]) -> int:
    '''
    Deduplicates and flips the lines of the Bash history.
    '''

    unique_lines = []

    with open(_filename, mode='r+') as f:
        for line in reversed(list(f)):
            if line in unique_lines:
                continue

            '''
            We prepend the line so older entries get to the start of the list.
            That way, recently used commands in bash_history are suggested first
            with fzf.
            '''
            unique_lines.insert(0, line)

        f.seek(0)
        f.truncate()

        for line in unique_lines:
            print(line, end='', file=f)

    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))
