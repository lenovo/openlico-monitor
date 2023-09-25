#! /usr/bin/python3
# Copyright 2015-present Lenovo
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
import time

from lico.monitor.plugins.icinga.helper.base import MetricsBase, PluginData

try:
    from lico.monitor.libs._infiniband import get_device_list
except ModuleNotFoundError:
    def get_device_list():
        return []


class InfinibandMetric(MetricsBase):
    @classmethod
    def ib_recv(cls):
        try:
            ib_in_f = sum([p.io_counters.rcv_data
                           for dev in get_device_list() for p in dev.ports])
            time.sleep(1)
            ib_in_g = sum([p.io_counters.rcv_data
                           for dev in get_device_list() for p in dev.ports])
            ib_in = ib_in_g - ib_in_f
        except Exception as e:
            cls.print_err(e)
            return []
        return [cls.build_point('ib_in', ib_in, 'float', 'B')]

    @classmethod
    def ib_send(cls):
        try:
            ib_out_f = sum([p.io_counters.xmit_data
                            for dev in get_device_list() for p in dev.ports])
            time.sleep(1)
            ib_out_g = sum([p.io_counters.xmit_data
                            for dev in get_device_list() for p in dev.ports])
            ib_out = ib_out_g - ib_out_f
        except Exception as e:
            cls.print_err(e)
            return []
        return [cls.build_point('ib_out', ib_out, 'float', 'B')]


def ib_recv(verbose):
    InfinibandMetric.verbose = verbose
    return InfinibandMetric.ib_recv()


def ib_send(verbose):
    InfinibandMetric.verbose = verbose
    return InfinibandMetric.ib_send()


def get_network_ib_in(plugin_data, verbose):
    try:
        ib_in_dict = ib_recv(verbose)[0]
    except Exception as e:
        if verbose:
            raise e
    else:
        plugin_data.add_output_data(
            "Infiniband Adapter Input Speed = {}{}/s".format(
                ib_in_dict['value'],
                ib_in_dict['units']
            )
        )
        plugin_data.add_perf_data(
            "{}={}{}".format(
                ib_in_dict['metric'],
                ib_in_dict['value'],
                ib_in_dict['units']
            )
        )


def get_network_ib_out(plugin_data, verbose):
    try:
        ib_out_dict = ib_send(verbose)[0]
    except Exception as e:
        if verbose:
            raise e
    else:
        plugin_data.add_output_data(
            "Output Speed = {}{}/s".format(
                ib_out_dict['value'],
                ib_out_dict['units']
            )
        )
        plugin_data.add_perf_data(
            "{}={}{}".format(
                ib_out_dict['metric'],
                ib_out_dict['value'],
                ib_out_dict['units']
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
    parser.add_argument('--recv', action='store_true', help="""
    Get upload speed;
    """)
    parser.add_argument('--send', action='store_true', help="""
    Get download speed;
    """)
    args = parser.parse_args()
    plugin_data = PluginData()

    if args.recv or args.all:
        get_network_ib_in(plugin_data, args.verbose)
    if args.send or args.all:
        get_network_ib_out(plugin_data, args.verbose)
    plugin_data.exit()
