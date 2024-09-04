# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0

from __future__ import annotations


'''
TODOs:
- handle enumerated composers, performers, comments
- merge composer/performer/comment entries
'''


##########################################################################################
# Imports
##########################################################################################

from argparse import ArgumentParser
from dataclasses import dataclass
from enum import IntEnum, unique
from itertools import pairwise
from pathlib import Path
from sys import stderr, stdout
from typing import Generator, TypeVar

from magic import Magic

from ...common_util import path_walk
from ...vc_addtag import TagEntry, vc_addtag
from ...vc_helper import gettag
from .flac_encode import is_flac


##########################################################################################
# Enumerator definitions
##########################################################################################

@unique
class ParsingState(IntEnum):
    '''
    State of the album credits parser.

    SearchingBlock - parser is searching for a new credit block
    BlockFound     - parser is found a credit block
    Done           - parser is done
    '''

    SearchingBlock = 0
    BlockFound     = 1
    Done           = 2

@unique
class LineType(IntEnum):
    '''
    Type of a line of a credit block.

    Artist    - line contains artist information
    Composer  - line contains composer information
    Performer - line contains performer information
    Comment   - line contains comment information
    '''

    Artist    = 0
    Composer  = 1
    Performer = 2
    Comment   = 3


##########################################################################################
# Dataclass definitions
##########################################################################################

@dataclass(frozen=True)
class TrackIndexKey:
    '''
    Helper class functioning as index key for a audio track.

    discnumber  - discnumber of the track
    tracknumber - tracknumber of the track
    '''

    discnumber: int
    tracknumber: int

    @staticmethod
    def from_list(values: list[str]) -> TrackIndexKey:
        '''
        Create a track index key from a list of strings.

        Arguments:
            values - list of input strings
        '''

        if len(values) != 2:
            return None

        try:
            discnumber = None if values[0] is None else int(values[0])
            tracknumber = int(values[1])

        except (ValueError, TypeError):
            return None

        return TrackIndexKey(discnumber, tracknumber)

@dataclass(frozen=True, repr=False)
class ArtistEntry:
    '''
    An artist credit entry.

    names - list of artist names (list can be empty)
    '''

    names: list[str]

    @staticmethod
    def make(value: str) -> ArtistEntry:
        '''
        Construct an artist entry from a raw artist value.

        Arguments:
            value - the artist value
        '''

        names = _split_into_names(value)
        if not names:
            raise RuntimeError('invalid artist entry')

        return ArtistEntry(names)

    def __str__(self) -> str:
        pretty = _pretty_names(self.names)

        return f'Artist({repr(pretty)})'

    def fixup(self, post_rules: dict[str, str]) -> ArtistEntry:
        '''
        Apply fixup rules to an artist entry.

        Arguments:
            post_rules - post fixup rules to apply

        Returns a new (fixed up) artist entry.
        '''

        names = self.names.copy()
        for k, v in post_rules.items():
            names[:] = [n.replace(k, v) for n in names]

        return ArtistEntry(names)

    def is_empty(self) -> bool:
        '''
        Check if the artist entry is empty.

        Returns True if the list of artist names belong to the entry is empty.
        '''

        return len(self.names) == 0

    def pretty(self) -> str:
        '''
        Return a pretty formatted string of the artist entry.
        '''

        return _pretty_names(self.names)

@dataclass(frozen=True, repr=False)
class ComposerEntry:
    '''
    A composer credit entry.

    function - the composer function
    names    - list of composer names (list can be empty)
    '''

    function: str
    names: list[str]

    keys = (
        'Composer',
        'Lyrics',
        'Music',
        'Lyricist',
    )

    fixup_map = {
        'Composer': 'Music',
        'Lyricist': 'Lyrics',
    }

    @staticmethod
    def make(value: str, idx: int) -> ComposerEntry:
        '''
        Construct a composer entry from a raw composer value.

        Arguments:
            value - the composer value
            idx   - index into the composer keys
        '''

        names = _split_into_names(value)
        if not names:
            raise RuntimeError('invalid composer entry')

        return ComposerEntry(ComposerEntry.keys[idx], names)

    def __str__(self) -> str:
        pretty = _pretty_names(self.names) + f' ({self.function})'

        return f'Composer({repr(pretty)})'

    def fixup(self, post_rules: dict[str, str]) -> ComposerEntry:
        '''
        Apply fixup rules to a composer entry.

        Arguments:
            post_rules - post fixup rules to apply

        Returns a new (fixed up) composer entry.
        '''

        f = ComposerEntry.fixup_map.get(self.function)
        function = self.function if f is None else f

        names = self.names.copy()
        for k, v in post_rules.items():
            names[:] = [n.replace(k, v) for n in names]

        return ComposerEntry(function, names)

    def is_empty(self) -> bool:
        '''
        Check if the composer entry is empty.

        Returns True if the list of composer names belong to the entry is empty.
        '''

        return len(self.names) == 0

    def pretty(self) -> str:
        '''
        Return a pretty formatted string of the composer entry.
        '''

        return _pretty_names(self.names) + f' ({self.function})'

@dataclass(frozen=True, repr=False)
class PerformerEntry:
    '''
    A performer credit entry.

    function - the performer function
    names    - list of performer names (list can be empty)
    '''

    function: str
    names: list[str]

    keys = (
        '1st Choir',
        '1st Violin',
        '2nd Choir',
        '2nd Violin',
        'Acoustic Guitar',
        'Bansuri',
        'Bass',
        'Bouzouki',
        'Cello',
        'Choir',
        'Classical Guitar',
        'Dizi',
        'Double Bass',
        'Duduk',
        'Electric Guitar',
        'Erhu',
        'Female Solo Vocals',
        'Guitar',
        'Guzheng',
        'Harp',
        'Harpsichord',
        'Kanun',
        'Koto',
        'Mandolin',
        'Ney',
        'Orchestra',
        'Oud',
        'Piano',
        'Pipa',
        'Santur',
        'Saz',
        'Shakuhachi',
        'Shaoqin',
        'Singer',
        'Sitar',
        'Steel-Stringed Guitar',
        'Taiko',
        'Tsugaru Shamisen',
        'Voice',
        'Viola',
        'Violin',
        'Xiao',
    )

    fixup_map = {
        'Orchestra': '',
        'Choir': '',
    }

    @staticmethod
    def make(value: str, idx: int) -> PerformerEntry:
        '''
        Construct a performer entry from a raw performer value.

        Arguments:
            value - the performer value
            idx   - index into the performer keys
        '''

        return PerformerEntry(PerformerEntry.keys[idx], _split_into_names(value))

    def __str__(self) -> str:
        pretty = _pretty_names(self.names)
        if pretty is None:
            pretty = f'{self.function}:'
        elif self.function is not None:
            pretty += f' ({self.function})'

        return f'Performer({repr(pretty)})'

    def fixup(self, post_rules: dict[str, str]) -> PerformerEntry:
        '''
        Apply fixup rules to a composer entry.

        Arguments:
            post_rules - post fixup rules to apply

        Returns a new (fixed up) composer entry.
        '''

        function = self.function

        f = PerformerEntry.fixup_map.get(function)
        if f is not None:
            is_function_explicit = self.names and all([function in n for n in self.names])

            if is_function_explicit:
                function = None if len(f) == 0 else f

        names = self.names.copy()
        for k, v in post_rules.items():
            names[:] = [n.replace(k, v) for n in names]

        return PerformerEntry(function, names)

    def is_empty(self) -> bool:
        '''
        Check if the performer entry is empty.

        Returns True if the list of performer names belong to the entry is empty.
        '''

        return len(self.names) == 0

    def pretty(self) -> str:
        '''
        Return a pretty formatted string of the performer entry.
        '''

        pretty = _pretty_names(self.names)
        if pretty is None:
            pretty = f'{self.function}:'
        elif self.function is not None:
            pretty += f' ({self.function})'

        return pretty

@dataclass(frozen=True, repr=False)
class CommentEntry:
    '''
    A comment credit entry.

    function - the comment function
    names    - list of comment names (list can be empty)

    The field :function: can be None if this is an unstructured entry.
    Unstructured entries always have a :names: list of length one.
    '''

    function: str
    names: list[str]

    fixup_map = {
        'Mixing Studio': 'Mixing Location',
        'Mastering Studio': 'Mastering Location',
        'Recording Studio': 'Recording Location',
        'Co-produced by': 'Co-Producer',
        'Produced by': 'Producer',
    }

    @staticmethod
    def make_unstructed(line: str) -> CommentEntry:
        '''
        Format an unstructured comment entry.

        Arguments:
            line - the comment line
        '''

        # TODO: extend handling

        return CommentEntry(None, [line])

    @staticmethod
    def make(key: str, value: str) -> CommentEntry:
        '''
        Format a (structured) key/value comment entry.

        Arguments:
            key   - the coment key
            value - the comment value
        '''

        return CommentEntry(key, _split_into_names(value))

    def __str__(self) -> str:
        pretty = f'{self.function}: {_pretty_names(self.names)}'

        return f'Comment({repr(pretty)})'

    def fixup(self, post_rules: dict[str, str]) -> CommentEntry:
        '''
        Apply fixup rules to a comment entry.

        Arguments:
            post_rules - post fixup rules to apply

        Returns a new (fixed up) comment entry.
        '''

        if self.function is not None:
            f = CommentEntry.fixup_map.get(self.function)
            function = self.function if f is None else f
        else:
            function = None

        names = self.names.copy()
        for k, v in post_rules.items():
            names[:] = [n.replace(k, v) for n in names]

        return CommentEntry(function, names)

    def is_empty(self) -> bool:
        '''
        Check if the comment entry is empty.

        Returns True if the list of comment names belong to the entry is empty.
        '''

        return len(self.names) == 0

    def is_unstructured(self) -> bool:
        '''
        Check if the comment entry is unstructured.
        '''

        return self.function is None

    def pretty(self) -> str:
        '''
        Return a pretty formatted string of the performer entry.
        '''

        return f'{self.function}: {_pretty_names(self.names)}'

@dataclass(frozen=True)
class BlockHeader:
    '''
    Header of a credit block.

    discnumber  - discnumber of the credited track
    tracknumber - tracknumber of the credited track
    trackname   - trackname of the credited track (optional, i.e. can be None)
    '''

    discnumber: int
    tracknumber: int
    trackname: str

    @staticmethod
    def from_line(line: str) -> BlockHeader:
        '''
        Construct a block header from a raw line.

        Arguments:
            line - raw input line

        Returns None if the raw line does not encode a valid block header.
        '''

        try:
            prefix, trackname = line.split(' ', maxsplit=1)

        except ValueError:
            '''
            If the spliting fails, assume that we don't have a trackname.
            '''
            prefix = line
            trackname = None

        tracknumber = None

        for separator in ('.', '-'):
            if separator in prefix:
                try:
                    first, second = prefix.split(separator, maxsplit=1)

                    discnumber = int(first)
                    tracknumber = int(second)

                except ValueError:
                    pass

        if tracknumber is None:
            discnumber = None

            try:
                tracknumber = int(prefix)

            except ValueError:
                return None

        if discnumber is not None and (discnumber <= 0 or discnumber >= 30):
            return None

        if tracknumber <= 0 or tracknumber >= 99:
            return None

        return BlockHeader(discnumber, tracknumber, trackname)

    @staticmethod
    def is_header(line: str) -> bool:
        '''
        Check if the raw line encodes a valid block header.

        Arguments:
            line - raw input line
        '''

        return BlockHeader.from_line(line) is not None

    def get_index(self) -> TrackIndexKey:
        '''
        Get the index key of the block header.
        '''

        return TrackIndexKey(self.discnumber, self.tracknumber)


##########################################################################################
# Type definitions
##########################################################################################

'''
Define a generic entry type, that covers the artist/composer/performer/comment entry.
'''
GenericEntryType = TypeVar('GenericEntryType', ArtistEntry, ComposerEntry, PerformerEntry, CommentEntry)


##########################################################################################
# Class definitions
##########################################################################################

class CreditBlock:
    '''
    Block of track credit information.
    '''

    _post_fixup_map = {
        'SHANGRI-LA Inc.': 'Shangri-La Inc.',
    }

    _all_caps = (
        'Crescente Studio',
        'MonolithSoft',
        'Onkio Haus',
        'Procyon Studio',
        'Studio Sunshine',
    )

    @staticmethod
    def get_type(line: str) -> tuple[LineType, GenericEntryType]:
        '''
        Get the type of a line of the credit block.

        Arguments:
            line - the credit block line
        '''

        try:
            key, value = line.split(':', maxsplit=1)

        except ValueError:
            return (LineType.Comment, CommentEntry.make_unstructed(line))

        if key in ('Arranger'):
            return (LineType.Artist, ArtistEntry.make(value.lstrip()))

        try:
            idx = ComposerEntry.keys.index(key)

            return (LineType.Composer, ComposerEntry.make(value.lstrip(), idx))

        except ValueError:
            pass

        try:
            idx = PerformerEntry.keys.index(key)

            return (LineType.Performer, PerformerEntry.make(value.lstrip(), idx))

        except ValueError:
            pass

        return (LineType.Comment, CommentEntry.make(key, value.lstrip()))

    def __init__(self, header: str) -> None:
        '''
        Constructor.

        Arguments:
            header - header line of the credit block
        '''

        self._header = BlockHeader.from_line(header)

        self._artist: list[ArtistEntry] = list()
        self._composer: list[ComposerEntry] = list()
        self._performer: list[PerformerEntry] = list()
        self._comment: list[CommentEntry] = list()

    def __str__(self) -> str:
        '''
        Format credit block as human-readable output.
        '''

        artist = [f'\t{a}' for a in self._artist]
        composer = [f'\t{c}' for c in self._composer]
        performer = [f'\t{p}' for p in self._performer]
        comment = [f'\t{c}' for c in self._comment]

        everything = artist + composer + performer + comment

        return format(self._header) + '\n' + '\n'.join(everything)

    def parse(self, line: str) -> None:
        '''
        Parse a line and add the information to the credit block.

        Arguments:
            line - the input line to parse
        '''

        line_type, result = CreditBlock.get_type(line)

        if line_type == LineType.Artist:
            self._artist.append(result)
        elif line_type == LineType.Composer:
            self._composer.append(result)
        elif line_type == LineType.Performer:
            self._performer.append(result)
        elif line_type == LineType.Comment:
            self._comment.append(result)
        else:
            raise RuntimeError('not implemented')

    def merge(self) -> None:
        '''
        Merge the information stored in the credit block.

        This also applies various fixup operations to the information.
        '''

        fixup_map = CreditBlock._post_fixup_map.copy()

        for arg in CreditBlock._all_caps:
            fixup_map[arg.upper()] = arg

        fixed_artist = [a.fixup(fixup_map) for a in self._artist]
        fixed_composer = [c.fixup(fixup_map) for c in self._composer]
        fixed_performer = [p.fixup(fixup_map) for p in self._performer]
        fixed_comment = [c.fixup(fixup_map) for c in self._comment]

        artist_merged = ArtistEntry([name for entry in fixed_artist for name in entry.names])
        self._artist = [artist_merged]

        self._composer = _merge_entries_generic(fixed_composer)
        self._performer = _merge_entries_generic(fixed_performer)
        self._comment = _merge_entries_generic(fixed_comment)

    def get_functions(self, entry_type: GenericEntryType) -> list[str]:
        '''
        Get the list of functions from this credit block for a given entry type.

        Arguments:
            entry_type - the entry type
        '''

        if entry_type is PerformerEntry:
            functions = [p.function for p in self._performer]
        elif entry_type is ComposerEntry:
            functions = [p.function for p in self._composer]
        elif entry_type is CommentEntry:
            functions = [p.function for p in self._comment]
        else:
            raise RuntimeError(f'invalid entry type: {entry_type}')

        return functions

    def apply_tags(self, files: dict[TrackIndexKey, Path]) -> None:
        '''
        Apply all information from the credit block as tags.

        Arguments:
            files - map between track index and file path

        The block header of the credit block is used to look up the correct
        path in the :files: argument.
        '''

        idx = self._header.get_index()

        path = files.get(idx)
        if path is None:
            return

        artist = [a.pretty() for a in self._artist]
        composer = [c.pretty() for c in self._composer]
        performer = [p.pretty() for p in self._performer]
        comment = [c.pretty() for c in self._comment]

        entries = [
            TagEntry(key='artist', value='\n'.join(artist)),
            TagEntry(key='composer', value='\n'.join(composer)),
            TagEntry(key='performer', value='\n'.join(performer)),
            TagEntry(key='comment', value='\n'.join(comment)),
        ]

        vc_addtag(path, entries)

class AlbumCreditsParser:
    '''
    Flexible parser for track credits belonging to music albums.
    '''

    def __init__(self, lines: list[str], verbose: bool) -> None:
        '''
        Constructor.

        Arguments:
            lines   - the album credit lines the parser should work on
            verbose - should we enable verbose printing?
        '''

        if lines is None or len(lines) == 0:
            raise RuntimeError('invalid lines argument')

        '''
        We make a copy here since we modify the list.
        '''
        self._line_storage: list[str] = lines.copy()

        self._verbose = verbose
        self._state: ParsingState = ParsingState.SearchingBlock
        self._new_block: CreditBlock = None
        self._blocks: list[CreditBlock] = list()

    def __str__(self) -> str:
        '''
        Pretty format the album credits.
        '''

        formatted_blocks = map(format, self._blocks)

        return '\n'.join(formatted_blocks)

    def _consume_line(self) -> str:
        '''
        Consume a line from the line storage and return it.

        If the line storage is empty, None is returned.
        '''

        if len(self._line_storage) == 0:
            return None

        ret = self._line_storage.pop(0)

        if self._verbose:
            print(f'info: consuming line: {ret}', file=stdout)

        return ret

    def parse(self) -> bool:
        '''
        Consume a line from the line storage and parse it.

        Returns True if there are more lines to parse.
        Returns False if parsing is done.
        '''

        if self._verbose:
            print(f'info: parsing state: {self._state.name}', file=stdout)

        if self._state == ParsingState.SearchingBlock:
            current_line = self._consume_line()
            if current_line is None:
                self._state = ParsingState.Done
            elif BlockHeader.is_header(current_line):
                self._state = ParsingState.BlockFound
                self._new_block = CreditBlock(current_line)

            return True

        elif self._state == ParsingState.BlockFound:
            current_line = self._consume_line()
            if current_line is None:
                self._state = ParsingState.Done
            elif len(current_line) == 0:
                self._state = ParsingState.SearchingBlock
                self._blocks.append(self._new_block)
                self._new_block = None
            else:
                self._new_block.parse(current_line)

            return True

        elif self._state == ParsingState.Done:
            if self._new_block is not None:
                self._blocks.append(self._new_block)
                self._new_block = None

            return False

    def merge(self) -> None:
        '''
        Merge all currently managed credit blocks.
        '''

        list(map(lambda b: b.merge(), self._blocks))

    def get_functions(self, entry_type: GenericEntryType) -> list[str]:
        '''
        Get the list of functions from all credit blocks for a given entry type.

        Arguments:
            entry_type - the entry type
        '''

        functions = set()

        list(map(lambda b: functions.update(b.get_functions(entry_type)), self._blocks))

        return list(functions)

    def apply_tags(self, files: list[Path]) -> None:
        '''
        Apply all information of all credit blocks to a list of files.

        Arguments:
            files - list of file paths

        The files are required to have the tracknumber and 
        discnumber (if applicable) tag set.
        '''

        tags = ['discnumber', 'tracknumber']

        files_map = {TrackIndexKey.from_list(gettag(f, tags)): f for f in files}

        list(map(lambda b: b.apply_tags(files_map), self._blocks))


##########################################################################################
# Internal Functions
##########################################################################################

def _escaped_split(line: str) -> list[str]:
    '''
    Split a line by comma with escape handling (regular braces are handled).

    Arguments:
        line - input line that we want to split

    Returns a list of strings.
    '''

    parts: list[str] = list()
    braces_level = 0
    current = list()

    '''
    Trick to remove special-case of trailing chars.
    '''
    tmp = line + ','

    for c in tmp:
        if c == ',' and braces_level == 0:
            parts.append(''.join(current))
            current = list()
        else:
            if c == '(':
                braces_level += 1
            elif c == ')':
                braces_level -= 1

            current.append(c)

    return parts

def _pretty_names(names: list[str]) -> str:
    '''
    Pretty format a names list.

    Arguments:
        names - list of input names
    '''

    if len(names) == 0:
        return None

    if len(names) == 1:
        return names[0]

    return ', '.join(names[0:-1]) + ' and ' + names[-1]

def _split_into_names(value: str) -> list[str]:
    '''
    Split a generic value string into a list of names.

    Arguments:
        value - input value string

    Returns an empty list if the value string is empty.
    '''

    if len(value) == 0:
        return list()

    if ',' not in value:
        return [value]

    return list(map(lambda x: x.strip(), _escaped_split(value)))

def _partition_by_entries(entries: list[GenericEntryType], partition_entries: list[GenericEntryType]) -> Generator[list[GenericEntryType]]:
    '''
    Partition a list of entries using another list containg the partition points.

    Arguments:
        entries           - the input list of (generic) entries
        partition_entries - the list of entries used to create partition points

    Returns a generator that generates contiguous sublists of :entries: by locating
    each element of :partition_entries: in :entries: and using the resulting
    indices as partition points.
    '''

    if not partition_entries:
        yield entries
    else:
        part_indices = {entries.index(pe) for pe in partition_entries}

        part_indices.add(0)
        part_indices.add(len(entries))

        for i, j in pairwise(sorted(list(part_indices))):
            yield entries[i:j]

def _merge_entries_generic(entries: list[GenericEntryType]) -> list[GenericEntryType]:
    '''
    Merge a list of entries.

    Arguments:
        entries - the input list of (generic) entries

    TODO: desc
    '''

    if len(entries) == 0:
        return list()

    '''
    We assume that all elements of our entries list have the same type.
    '''
    EntryType = type(entries[0])

    empty_entries = list(filter(lambda e: e.is_empty(), entries))
    partitions = _partition_by_entries(entries, empty_entries)

    def _merge_by_function(entries: list[EntryType], function: str) -> EntryType:
        '''
        TODO: desc
        '''

        matching_entries = filter(lambda x: x.function == function, entries)

        merged_names = [n for entry in matching_entries for n in entry.names]

        return EntryType(function, merged_names)

    result: list[EntryType] = list()

    for part in partitions:
        if part[0].is_empty():
            result.append(part[0])
            part_entries = part[1:]
        else:
            part_entries = part

        functions = [e.function for e in part_entries]

        result.extend([_merge_by_function(part_entries, f) for f in functions])

    return result


##########################################################################################
# Functions
##########################################################################################

def vgmdb_albumcredits(directory_path: Path, credits_path: Path, just_print: bool, verbose: bool) -> None:
    '''
    Apply VGMdb album credits to FLAC files in a given directory.

    Arguments:
        directory_path - path to the directory which we should process
        credits_path   - path to the credits file that serves as input
        just_print     - just print and don't apply any tags
        verbose        - should we enable verbose printing?
    '''

    lines = credits_path.read_text(encoding='utf-8').splitlines()

    credits_parser = AlbumCreditsParser(lines, verbose)

    while credits_parser.parse():
        pass

    credits_parser.merge()

    if verbose:
        print('info: printing verbose function information:', file=stdout)

        for arg in (ComposerEntry, PerformerEntry, CommentEntry):
            print(f'\tFunctions for {arg.__name__}: {credits_parser.get_functions(arg)}', file=stdout)

    if just_print:
        print(credits_parser)
    else:
        mime = Magic(mime=True)

        files = [x for x in path_walk(directory_path) if is_flac(mime, x)]

        credits_parser.apply_tags(files)


##########################################################################################
# Main
##########################################################################################

def main(args: list[str]) -> int:
    '''
    Main function.

    Arguments:
        args - list of string arguments from the CLI
    '''

    parser = ArgumentParser(description='Copy VorbisComment and picture metadata.')

    parser.add_argument('-d', '--directory', help='Directory where tags should be applied', required=True)
    parser.add_argument('-c', '--credits-file', help='File containing the input credits', required=True)
    parser.add_argument('-p', '--print', action='store_true', help='Should we just print the tags (instead of applying them)?')
    parser.add_argument('-v', '--verbose', action='store_true', help='Should we enable verbose printing?')

    parsed_args = parser.parse_args(args[1:])

    if parsed_args.directory is not None and parsed_args.credits_file is not None:
        directory_path = Path(parsed_args.directory)
        if not directory_path.is_dir():
            print(f'error: path is not a directory: {directory_path}', file=stderr)

            return 1

        credits_path = Path(parsed_args.credits_file)
        if not credits_path.is_file():
            print(f'error: invalid credits file: {credits_path}', file=stderr)

            return 2

        try:
            vgmdb_albumcredits(directory_path, credits_path, parsed_args.print, parsed_args.verbose)

        except Exception as exc:
            print(f'error: failed to apply album credits: {exc}', file=stderr)

            return 3

    return 0
