# -*- coding: utf-8 -*-

from sys import argv as sys_argv

from .razer_config import main as razer_config_main

def razer_config_cli() -> int:
    return razer_config_main(sys_argv)
