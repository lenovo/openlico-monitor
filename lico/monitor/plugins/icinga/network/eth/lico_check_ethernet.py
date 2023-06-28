#! /usr/bin/python3
# Copyright 2015-2023 Lenovo
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import os
import time

from lico.monitor.plugins.icinga.helper.base import MetricsBase, PluginData


class EthernetMetric(MetricsBase):
    net_dev = '/proc/net/dev'
    net_vlan_dev = '/proc/net/vlan/'

    @classmethod
    def _exclude_dev(cls):
        devices = ['lo', 'bond']
        # Get Vlan Devices
        if os.path.isdir(cls.net_vlan_dev):
            for root, dirs, files in os.walk(cls.net_vlan_dev):
                devices.append(files)
                break
        return devices

    @classmethod
    def _read_eth_bytes(cls):
        # flag only support 'in' and 'out'
        # interval unit is second
        def _parse_net_dev():
            recv_items = ['bytes', 'packets', 'errs', 'drop', 'fifo', 'frame',
                          'compressed', 'multicast']
            send_items = ['bytes', 'packets', 'errs', 'drop', 'fifo', 'colls',
                          'carrier', 'compressed']
            interfaces = []
            recv_bytes = []
            send_bytes = []
            parsed_data = {
                'interface': interfaces,
                'recv_bytes': recv_bytes,
                'send_bytes': send_bytes
            }
            for num, line in enumerate(f, start=1):
                if 1 == num:
                    continue
                elif 2 == num:
                    items = line.split('|')
                    recv_items = items[1].strip().split()
                    send_items = items[2].strip().split()
                else:
                    eth_info = line.split(':')
                    interface = eth_info[0].strip()
                    if interface not in cls._exclude_dev():
                        values = eth_info[1].strip().split()
                        rbytes_idx = recv_items.index('bytes')
                        sbytes_idx = \
                            send_items.index('bytes') + len(recv_items)
                        interfaces.append(interface)
                        recv_bytes.append(int(values[rbytes_idx]))
                        send_bytes.append(int(values[sbytes_idx]))
            return parsed_data

        with open(cls.net_dev, 'r') as f:
            prev_data = _parse_net_dev()
            time.sleep(1)
            f.seek(0)
            latest_data = _parse_net_dev()
            recv_speed = \
                sum(latest_data['recv_bytes']) - sum(prev_data['recv_bytes'])
            send_speed = \
                sum(latest_data['send_bytes']) - sum(prev_data['send_bytes'])

        return recv_speed, send_speed

    @classmethod
    def eth_recv(cls):
        eth_read, _ = cls._read_eth_bytes()
        return [cls.build_point('eth_in', eth_read, 'float', 'B')]

    @classmethod
    def eth_send(cls):
        _, eth_send = cls._read_eth_bytes()
        return [cls.build_point('eth_out', eth_send, 'float', 'B')]


def eth_recv(verbose):
    EthernetMetric.verbose = verbose
    return EthernetMetric.eth_recv()


def eth_send(verbose):
    EthernetMetric.verbose = verbose
    return EthernetMetric.eth_send()


def get_network_eth_in(plugin_data, verbose):
    try:
        eth_in_dict = eth_recv(verbose)[0]
    except Exception as e:
        if verbose:
            raise e
    else:
        plugin_data.add_output_data(
            "Ethernet Adapter Input Speed = {}{}/s".format(
                eth_in_dict["value"],
                eth_in_dict["units"],
            )
        )
        plugin_data.add_perf_data(
            "{0}={1}{2}".format(
                eth_in_dict['metric'],
                eth_in_dict['value'],
                eth_in_dict['units']
            )
        )


def get_network_eth_out(plugin_data, verbose):
    try:
        eth_out_dict = eth_send(verbose)[0]
    except Exception as e:
        if verbose:
            raise e
    else:
        plugin_data.add_output_data(
            "Output Speed = {}{}/s".format(
                eth_out_dict["value"],
                eth_out_dict["units"],
            )
        )
        plugin_data.add_perf_data(
            "{0}={1}{2}".format(
                eth_out_dict['metric'],
                eth_out_dict['value'],
                eth_out_dict['units']
            )
        )


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', action='store_true', help="""
    Verbose mode;
    """)
    parser.add_argument('--all', action='store_true', help="""
    Get upload and download speed;
    """)
    parser.add_argument('--send', action='store_true', help="""
    Get upload speed;
    """)
    parser.add_argument('--recv', action='store_true', help="""
    Get download speed;
    """)
    args = parser.parse_args()
    plugin_data = PluginData()

    if args.recv or args.all:
        get_network_eth_in(plugin_data, args.verbose)
    if args.send or args.all:
        get_network_eth_out(plugin_data, args.verbose)
    plugin_data.exit()
