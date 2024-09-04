# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

from argparse import ArgumentParser
from pathlib import Path
from sys import stderr, stdout
from typing import Generator

from ..common_util import path_walk


##########################################################################################
# Functions
##########################################################################################

def linklist_analyse(link_list: Path, work_dir: Path, remove_lines: bool) -> None:
    '''
    Analyse a link list.

    Arguments:
        link_list    - path to the link list file
        work_dir     - working directory for the analysis
        remove_lines - should we remove deprecated lines from the link list?
    '''

    if not link_list.is_file():
        raise RuntimeError(f'link list is not a file: {link_list}')

    if not work_dir.is_dir():
        raise RuntimeError(f'work dir is not a directory: {link_list}')

    def _gen_prefixes(path: Path) -> Generator[str, None, None]:
        for entry in path_walk(path):
            if entry.suffix not in ('.jpeg', '.mkv', '.mp4', '.wmv', '.avi'):
                print(f'warn: skipping file with unknown extension: {entry.name}', file=stderr)
            else:
                yield entry.stem

    prefixes = set(_gen_prefixes(work_dir))

    if remove_lines:
        links = link_list.read_text(encoding='utf-8').splitlines()

        def _gen_output(lines: list[str]) -> Generator[str, None, None]:
            for line in lines:
                if not any(map(lambda p: line.find(p) != -1, prefixes)):
                    yield line

        output_lines = list(_gen_output(links))

        with open(link_list, mode='wt', encoding='utf-8') as f:
            map(lambda l: print(l, file=f), output_lines)

    else:
        print('info: the following lines can be removed from the link-list:', file=stdout)

        lineidx = 0
        links = link_list.read_text(encoding='utf-8').splitlines()

        for link in links:
            lineidx += 1

            for arg in prefixes:
                if link.find(arg) != -1:
                    print(f'{lineidx}: {link.strip()}', file=stdout)


##########################################################################################
# Main
##########################################################################################

def main(args: list[str]) -> int:
    '''
    Main function.

    Arguments:
        args - list of string arguments from the CLI
    '''

    parser = ArgumentParser(description='Helper to analyze a link list file.')

    parser.add_argument('-r', '--remove-lines', action='store_true', help='Should deprecated lines be removed from the link list?')
    parser.add_argument('-l', '--link-list', help='Path to the link list file', required=True)
    parser.add_argument('-d', '--directory', help='Path to the working directory', required=True)

    parsed_args = parser.parse_args(args[1:])

    if parsed_args.link_list is not None and parsed_args.directory is not None:
        link_list = Path(parsed_args.link_list)
        directory = Path(parsed_args.directory)

        try:
            linklist_analyse(link_list, directory, parsed_args.remove_lines)

        except Exception as exc:
            print(f'error: failed to analyse linklis: {exc}', file=stderr)

            return 1

    return 0
