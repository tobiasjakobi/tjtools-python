#!/usr/bin/env python3
# -*- coding: utf-8 -*-


##########################################################################################
# Imports
##########################################################################################

import sys

from collections.abc import Mapping
from configparser import ConfigParser
from ipaddress import IPv4Interface, IPv6Interface
from os.path import exists
from os import environ as os_env
from subprocess import run as prun


'''
TODOs:
- use pyroute2 instead of the ip CLI
- handle netns add/delete in other systemd unit, so we don't need all the
  permission granting for OpenVPN
'''


##########################################################################################
# Constants
##########################################################################################

'''
Our VPN configuration file.
'''
_config_file = '/etc/vpn.conf'

'''
OpenVPN specific environment variables that we use.

The boolean values indicate if the variable is mandatory, i.e
if we should error out when it is missing.
'''
_openvpn_keys = {
    'script_type': True,
    'dev': True,
    'tun_mtu': True,
    'ifconfig_local': False,
    'ifconfig_netmask': False,
    'ifconfig_broadcast': False,
    'ifconfig_ipv6_local': False,
    'ifconfig_ipv6_netbits': False,
    'route_vpn_gateway': False,
    'ifconfig_ipv6_remote': False,
}


##########################################################################################
# Internal functions
##########################################################################################

def _route_add(namespace: str, args: list):
    p_args = ['ip', '-netns', namespace, 'route', 'add'] + args
    prun(p_args, check=True)

def _route_del(namespace: str, args: list):
    p_args = ['ip', '-netns', namespace, 'route', 'del'] + args
    prun(p_args, check=True)

def _addr_add(namespace: str, args: list):
    p_args = ['ip', '-netns', namespace, 'addr', 'add'] + args
    prun(p_args, check=True)

def _addr_del(namespace: str, args: list):
    p_args = ['ip', '-netns', namespace, 'addr', 'del'] + args
    prun(p_args, check=True)

def _get_ipv4_if(env: dict) -> IPv4Interface:
    ipv4_local = env.get('ifconfig_local')
    if ipv4_local is None:
        return None

    ipv4_netmask = env.get('ifconfig_netmask')
    if ipv4_netmask is None:
        raise RuntimeError('IPv4 netmask missing')

    return IPv4Interface(f'{ipv4_local}/{ipv4_netmask}')

def _get_ipv6_if(env: dict) -> IPv6Interface:
    ipv6_local = env.get('ifconfig_ipv6_local')
    if ipv6_local is None:
        return None

    ipv6_netbits = env.get('ifconfig_ipv6_netbits')
    if ipv6_netbits is None:
        raise RuntimeError('IPv6 netbits missing')

    return IPv6Interface(f'{ipv6_local}/{ipv6_netbits}')

def _env_prepare(in_env: Mapping) -> dict:
    out_env = {arg: in_env.get(arg) for arg in _openvpn_keys.keys()}

    for key, value in _openvpn_keys.items():
        if value and out_env.get(key) is None:
            raise RuntimeError(f'mandatory key in OS environment missing: {key}')

    return out_env

def _handle_up(namespace: str, env: dict):
    netdev = env.get('dev')
    mtu = env.get('tun_mtu')

    if not exists(f'/run/netns/{namespace}'):
        p_args = ['ip', 'netns', 'add', namespace]
        prun(p_args, check=True)

        p_args = ['ip', '-netns', namespace, 'link', 'set', 'dev', 'lo', 'up']
        prun(p_args, check=True)

    p_args = ['ip', 'link', 'set', 'dev', netdev, 'up', 'netns', namespace, 'mtu', mtu]
    prun(p_args, check=True)

    ipv4_interface = _get_ipv4_if(env)
    if ipv4_interface is not None:
        ipv4_args = ['dev', netdev, ipv4_interface.with_prefixlen]

        ipv4_broadcast = env.get('ifconfig_broadcast')
        if ipv4_broadcast is not None:
            ipv4_args.extend(['broadcast', ipv4_broadcast])

        _addr_add(namespace, ipv4_args)

    ipv6_interface = _get_ipv6_if(env)
    if ipv6_interface is not None:
        _addr_add(namespace, ['dev', netdev, ipv6_interface.with_prefixlen])

def _handle_route_up(namespace: str, env: dict):
    netdev = env.get('dev')

    ipv4_gateway = env.get('route_vpn_gateway')
    if ipv4_gateway is not None:
        _route_add(namespace, ['default', 'via', ipv4_gateway])
    else:
        _route_add(namespace, ['broadcast', '255.255.255.255', 'dev', netdev, 'scope', 'link'])

    ipv6_remote = env.get('ifconfig_ipv6_remote')
    if ipv6_remote is not None:
        _route_add(namespace, ['default', 'via', ipv6_remote])

def _handle_pre_down(namespace: str, env: dict):
    netdev = env.get('dev')

    ipv4_gateway = env.get('route_vpn_gateway')
    if ipv4_gateway is not None:
        _route_del(namespace, ['default', 'via', ipv4_gateway])
    else:
        _route_del(namespace, ['broadcast', '255.255.255.255', 'dev', netdev])

    ipv6_remote = env.get('ifconfig_ipv6_remote')
    if ipv6_remote is not None:
        _route_del(namespace, ['default', 'via', ipv6_remote])

    ipv4_interface = _get_ipv4_if(env)
    if ipv4_interface is not None:
        _addr_del(namespace, ['dev', netdev, ipv4_interface.with_prefixlen])

    ipv6_interface = _get_ipv6_if(env)
    if ipv6_interface is not None:
        _addr_del(namespace, ['dev', netdev, ipv6_interface.with_prefixlen])

def _handle_down(namespace: str, env: dict):
    p_args = ['ip', 'netns', 'pids', namespace]
    p = prun(p_args, check=True, capture_output=True, encoding='utf-8')

    ns_pids = p.stdout.splitlines()

    if ns_pids:
        print(f'warn: processes still using network namespace: {ns_pids}', file=sys.stdout)
    else:
        p_args = ['ip', 'netns', 'delete', namespace]
        prun(p_args, check=True)


##########################################################################################
# Functions
##########################################################################################

def get_ns_identifier() -> str:
    '''
    Get the identifier of the network namespace.
    '''

    p = ConfigParser()

    with open(_config_file, mode='r') as f:
        p.read_file(f)

    return p.get('NetworkNamespace', 'Identifier')

def is_ns_live(identifier: str) -> bool:
    '''
    Check if the network namespace is live.

    Arguments:
        identifier - network namespace identifier
    '''

    return exists(f'/run/netns/{identifier}')

def openvpn_netns(args: list):
    '''
    Handle a OpenVPN network namespace request.

    Arguments:
       args - list of request arguments from OpenVPN
    '''

    script_env = _env_prepare(os_env)

    switcher = {
        'up': _handle_up,
        'route-up': _handle_route_up,
        'route-pre-down': _handle_pre_down,
        'down': _handle_down,
    }

    namespace = get_ns_identifier()

    script_type = script_env.get('script_type')
    if script_type is None:
        raise RuntimeError('no script type given')

    cmd = switcher.get(script_type, None)
    if cmd is None:
        raise RuntimeError(f'script type not implemented: {script_type}')

    print(f'info: handling {script_type} request in namespace: {namespace}', file=sys.stdout)

    cmd(namespace, script_env)


##########################################################################################
# Main
##########################################################################################

def main(args: list) -> int:
    try:
        openvpn_netns(args[1:])

    except Exception as exc:
        print(f'error: failed to handle request: {exc}', file=sys.stderr)

        return 1

    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))
