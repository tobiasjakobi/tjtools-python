# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


from sys import argv as sys_argv

def acpi_action_cli() -> int:
    from .acpi_action import main as cli_main
    return cli_main(sys_argv)

def backup_manage_cli() -> int:
    from .backup_manage import main as cli_main
    return cli_main(sys_argv)

def checksum_cli() -> int:
    from .checksum import main as cli_main
    return cli_main(sys_argv)

def clean_bashhistory_cli() -> int:
    from .clean_bashhistory import main as cli_main
    return cli_main(sys_argv)

def cpufreq_perf_cli() -> int:
    from .cpufreq_perf import main as cli_main
    return cli_main(sys_argv)

def dosbox_wrap_cli() -> int:
    from .dosbox_wrap import main as cli_main
    return cli_main(sys_argv)

def gentoo_sandbox_cli() -> int:
    from .gentoo_sandbox import main as cli_main
    return cli_main(sys_argv)

def greeter_idle_cli() -> int:
    from .greeter_idle import main as cli_main
    return cli_main(sys_argv)

def kupdate_cli() -> int:
    from .kupdate import main as cli_main
    return cli_main(sys_argv)

def linklist_analyse_cli() -> int:
    from .linklist_analyse import main as cli_main
    return cli_main(sys_argv)

def mpv_ipc_cli() -> int:
    from .mpv_ipc import main as cli_main
    return cli_main(sys_argv)

def nag_helper_cli() -> int:
    from .nag_helper import main as cli_main
    return cli_main(sys_argv)

def openvpn_netns_cli() -> int:
    from .openvpn_netns import main as cli_main
    return cli_main(sys_argv)

def playmedia_cli() -> int:
    from .playmedia import main as cli_main
    return cli_main(sys_argv)

def pulseserver_wrap_cli() -> int:
    from .pulseserver_wrap import main as cli_main
    return cli_main(sys_argv)

def razer_config_cli() -> int:
    from .razer_config import main as cli_main
    return cli_main(sys_argv)

def rename_vfat_cli() -> int:
    from .rename_vfat import main as cli_main
    return cli_main(sys_argv)

def rifle_cmd_cli() -> int:
    from .rifle_cmd import main as cli_main
    return cli_main(sys_argv)

def rifle_monitor_cli() -> int:
    from .rifle_monitor import main as cli_main
    return cli_main(sys_argv)

def sshpipe_cli() -> int:
    from .sshpipe import main as cli_main
    return cli_main(sys_argv)

def stdcompress_cli() -> int:
    from .stdcompress import main as cli_main
    return cli_main(sys_argv)

def strip_utf8bom_cli() -> int:
    from .strip_utf8bom import main as cli_main
    return cli_main(sys_argv)

def sway_idle_cli() -> int:
    from .sway_idle import main as cli_main
    return cli_main(sys_argv)

def sway_multimedia_cli() -> int:
    from .sway_multimedia import main as cli_main
    return cli_main(sys_argv)

def swayshot_cli() -> int:
    from .swayshot import main as cli_main
    return cli_main(sys_argv)

def touchpad_control_cli() -> int:
    from .touchpad_control import main as cli_main
    return cli_main(sys_argv)

def waybar_cmus_cli() -> int:
    from .waybar_cmus import main as cli_main
    return cli_main(sys_argv)

def waybar_musicpd_cli() -> int:
    from .waybar_musicpd import main as cli_main
    return cli_main(sys_argv)

def zstd_simple_cli() -> int:
    from .zstd_simple import main as cli_main
    return cli_main(sys_argv)
