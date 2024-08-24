# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

from pathlib import Path

from magic import Magic
from mutagen.flac import FLAC
from mutagen.oggvorbis import OggVorbis


##########################################################################################
# Constants
##########################################################################################

_switcher = {
    'audio/ogg': OggVorbis,
    'audio/flac': FLAC,
}


##########################################################################################
# Functions
##########################################################################################

def gettag(path: Path, tags: list[str]) -> list[str]:
    '''
    Get a number of tag values from a given file.

    Arguments:
        path - path to the file used as input
        tags - list of tag keys

    Returns a list of strings, containing the values corresponding
    to the given tag keys.

    Should some tag key not exist, then None is put at this position
    in the list.
    '''

    mime = Magic(mime=True)

    if not path.is_file():
        raise RuntimeError(f'input path not found: {path}')

    input_type = mime.from_file(path.as_posix())

    audiotype = _switcher.get(input_type, None)
    if audiotype is None:
        raise RuntimeError(f'input has unsupported type: {input_type}')

    try:
        audio = audiotype(path.as_posix())

    except Exception as exc:
        raise RuntimeError(f'failed to open file: {exc}') from exc

    ret: list[str] = list()

    for _t in tags:
        _v = None
        if _t in audio.tags:
            _v = audio.tags[_t]

        if _v is not None:
            if len(_v) != 1:
                raise RuntimeError(f'multi-key tag not supported: {_t}')

            ret.append(_v[0])
        else:
            ret.append(_v)

    return ret
