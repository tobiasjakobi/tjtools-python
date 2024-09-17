# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

from os.path import dirname, exists, isdir, join as pjoin, split as psplit
from os import makedirs, rename, unlink, walk
from tempfile import NamedTemporaryFile

from ranger.api.commands import Command
from ranger.container.file import File


##########################################################################################
# Class definitions
##########################################################################################

class autoprefix_rename(Command):
    """:autoprefix_rename

    Does the same as prefix_rename, but takes an integer argument that is incremented
    with each directory encountered.
    """

    def execute(self) -> None:
        raw_prefix = self.arg(1)
        if not raw_prefix or not raw_prefix.isdigit():
            self.fm.notify('Missing or invalid prefix argument for renaming', bad=True)

            return

        start_prefix = int(raw_prefix)
        prefix = start_prefix

        rename_candidates: list[str] = list()

        for arg in self.fm.thistab.get_selection():
            if arg.is_directory:
                prefix_rename._collect_files(arg.path, rename_candidates, str(prefix))
            elif arg.is_file:
                rename_candidates.append(prefix_rename._rename_tuple(dirname(arg.path), arg.basename, str(prefix)))

            prefix += 1

        self.fm.notify(f'Renaming {len(rename_candidates)} files: autoprefix={start_prefix}..{prefix-1}')

        rename_fails = 0

        for old, new in rename_candidates:
            if exists(new):
                rename_fails += 1
            else:
                rename(old, new)

        if rename_fails != 0:
            self.fm.notify(f'Autoprefix renaming failed for {rename_fails} files', bad=True)

class gui_bulkrename(Command):
    """:gui_bulkrename

    This command opens a list of selected files in an external GUI editor.
    After you edit and save the file, it will bulk rename according to
    the changes you did in the file.
    """

    def execute(self) -> None:
        '''
        Create and edit the file list.
        '''
        filenames = [f.relative_path for f in self.fm.thistab.get_selection()]
        with NamedTemporaryFile(mode='w', encoding='utf-8', delete=False) as list_file:
            list_path = list_file.name

            for line in filenames:
                print(line, file=list_file)

        self.fm.execute_file([File(list_path)], app='gui-editor-wait')
        with open(list_path, mode='r', encoding='utf-8') as list_file:
            dst_filenames = list_file.read().splitlines()

        unlink(list_path)

        if len(filenames) != len(dst_filenames):
            self.fm.notify(f'Mismatch of filename list length: {len(filenames)}: {len(dst_filenames)}', bad=True)
            return

        new_dirs: list[str] = list()
        for f, dst_f in zip(filenames, dst_filenames):
            if f == dst_f:
                continue

            basepath, _ = psplit(dst_f)
            if basepath and basepath not in new_dirs and not isdir(basepath):
                new_dirs.append(basepath)

        for d in new_dirs:
            makedirs(d)

        '''
        TODO: use intermediate rename step to avoid filename clashing
        '''
        rename_fails = 0
        for f, dst_f in zip(filenames, dst_filenames):
            if f == dst_f:
                continue

            if exists(dst_f):
                rename_fails += 1
            else:
                rename(f, dst_f)

        if rename_fails != 0:
            self.fm.notify(f'Bulk renaming failed for {rename_fails} files', bad=True)

        tags_changed = False
        for f, dst_f in zip(filenames, dst_filenames):
            if f == dst_f:
                continue

            p = pjoin(self.fm.thisdir.path, f)
            dst_p = pjoin(self.fm.thisdir.path, dst_f)

            if p in self.fm.tags:
                t = self.fm.tags.tags[p]
                self.fm.tags.remove(p)
                self.fm.tags.tags[dst_p] = t
                tags_changed = True

        if tags_changed:
            self.fm.tags.dump()

class prefix_rename(Command):
    """:prefix_rename

    Rename a selection by prepending a prefix to each filename. If the selection
    contains a directory, the files in the directory are renamed, but not the
    directory itself.
    """

    @staticmethod
    def _rename_tuple(dir_path: str, filename: str, prefix: str) -> tuple[str, str]:
        '''
        Construct a renaming tuple.

        Arguments:
            dir_path - path to directory
            filename - the input filename
            prefix   - the prefix to use
        '''

        old_path = pjoin(dir_path, filename)
        renamed_path = pjoin(dir_path, prefix + filename)

        return (old_path, renamed_path)

    @staticmethod
    def _collect_files(root_path: str, output_list: list, prefix: str) -> None:
        '''
        Collect filenames of files in a root directory path.

        Arguments:
            root_path   - path to root directory
            output_list - list where the collected filenames are stored
            prefix      - the prefix to use
        '''

        for dirpath, dirnames, filenames in walk(top=root_path):
            for fn in filenames:
                output_list.append(prefix_rename._rename_tuple(dirpath, fn, prefix))

    def execute(self) -> None:
        prefix = self.rest(1)
        if not prefix:
            self.fm.notify('Missing prefix argument for renaming', bad=True)

            return

        rename_candidates: list[str] = list()

        for arg in self.fm.thistab.get_selection():
            if arg.is_directory:
                prefix_rename._collect_files(arg.path, rename_candidates, prefix)
            elif arg.is_file:
                rename_candidates.append(prefix_rename._rename_tuple(dirname(arg.path), arg.basename, prefix))

        self.fm.notify(f'Renaming {len(rename_candidates)} files: prefix=<<{prefix}>>')

        rename_fails = 0

        for old, new in rename_candidates:
            if exists(new):
                rename_fails += 1
            else:
                rename(old, new)

        if rename_fails != 0:
            self.fm.notify(f'Prefix renaming failed for {rename_fails} files', bad=True)

