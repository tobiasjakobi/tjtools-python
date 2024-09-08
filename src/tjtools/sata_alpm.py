# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0


##########################################################################################
# Imports
##########################################################################################

from pathlib import Path


##########################################################################################
# Constants
##########################################################################################

_scsi_host = Path('/sys/class/scsi_host')


##########################################################################################
# Functions
##########################################################################################

def sata_alpm() -> None:
    '''
    Enable ALPM (aggressive link power management) on all supported SCSI hosts.
    '''

    for entry in _scsi_host.iterdir():
        if not entry.is_symlink():
            continue

        if not entry.name.startswith('host'):
            continue

        policy = entry / 'link_power_management_policy'
        if policy.is_file():
            policy.write_text('min_power', encoding='utf-8')
