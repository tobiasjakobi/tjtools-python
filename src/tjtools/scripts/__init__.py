# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


from sys import argv as sys_argv

def acpi_action_cli() -> int:
    from .acpi_action import main as cli_main
    return cli_main(sys_argv)

def backup_manage_cli() -> int:
    from .backup_manage import main as cli_main
    return cli_main(sys_argv)

def clean_bashhistory_cli() -> int:
    from .clean_bashhistory import main as cli_main
    return cli_main(sys_argv)

def cpufreq_perf_cli() -> int:
    from .cpufreq_perf import main as cli_main
    return cli_main(sys_argv)

def greeter_idle_cli() -> int:
    from .greeter_idle import main as cli_main
    return cli_main(sys_argv)

def nag_helper_cli() -> int:
    from .nag_helper import main as cli_main
    return cli_main(sys_argv)

def razer_config_cli() -> int:
    from .razer_config import main as cli_main
    return cli_main(sys_argv)

def touchpad_control_cli() -> int:
    from .touchpad_control import main as cli_main
    return cli_main(sys_argv)

def zstd_simple_cli() -> int:
    from .zstd_simple import main as cli_main
    return cli_main(sys_argv)
