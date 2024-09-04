# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


from sys import argv as sys_argv

def album_transcode_cli() -> int:
    from .album_transcode import main as cli_main
    return cli_main(sys_argv)

def audio_rename_cli() -> int:
    from .audio_rename import main as cli_main
    return cli_main(sys_argv)

def bs1770gain_wrap_cli() -> int:
    from .bs1770gain_wrap import main as cli_main
    return cli_main(sys_argv)

def eac_pretag_cli() -> int:
    from .eac_pretag import main as cli_main
    return cli_main(sys_argv)

def flac_encode_cli() -> int:
    from .flac_encode import main as cli_main
    return cli_main(sys_argv)

def id3_fixenc_cli() -> int:
    from .id3_fixenc import main as cli_main
    return cli_main(sys_argv)

def reflac_cli() -> int:
    from .reflac import main as cli_main
    return cli_main(sys_argv)

def vc_auto_albumprepare_cli() -> int:
    from .vc_auto_albumprepare import main as cli_main
    return cli_main(sys_argv)

def vc_auto_tracknumber_cli() -> int:
    from .vc_auto_tracknumber import main as cli_main
    return cli_main(sys_argv)

def vc_cleantags_cli() -> int:
    from .vc_cleantags import main as cli_main
    return cli_main(sys_argv)

def vc_copytags_cli() -> int:
    from .vc_copytags import main as cli_main
    return cli_main(sys_argv)

def vc_interactive_tag_cli() -> int:
    from .vc_interactive_tag import main as cli_main
    return cli_main(sys_argv)

def vc_multi_tag_cli() -> int:
    from .vc_multi_tag import main as cli_main
    return cli_main(sys_argv)

def vgmdb_albumcredits_cli() -> int:
    from .vgmdb_albumcredits import main as cli_main
    return cli_main(sys_argv)

def vgmdb_tracklist_cli() -> int:
    from .vgmdb_tracklist import main as cli_main
    return cli_main(sys_argv)
