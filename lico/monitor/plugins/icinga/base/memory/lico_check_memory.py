#!/usr/bin/python3
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

from lico.monitor.plugins.icinga.helper.base import MetricsBase, PluginData


class MemoryMetrics(MetricsBase):

    @classmethod
    def mem_result(cls):
        out, err, ret_code = cls.command_call(['free', '-k'])
        if ret_code:
            cls.print_err(out + err)
            return []
        mem_list = out.decode().split('\n')
        return dict(zip(mem_list[0].split(), mem_list[1].split()[1:]))

    @classmethod
    def memory_total(cls):
        mem_result = cls.mem_result()
        if not mem_result:
            return []
        return [
            cls.build_point('memory_total', int(mem_result['total']), 'uint',
                            'KiB')
        ]

    @classmethod
    def memory_used(cls):
        mem_result = cls.mem_result()
        if not mem_result:
            return []
        return [
            cls.build_point('memory_used', int(mem_result['used']), 'uint',
                            'KiB')
        ]


def memory_total(verbose):
    MemoryMetrics.verbose = verbose
    return MemoryMetrics.memory_total()


def memory_used(verbose):
    MemoryMetrics.verbose = verbose
    return MemoryMetrics.memory_used()


def get_mem_total(plugin_data, verbose):
    mem_total_dict = memory_total(verbose)
    if mem_total_dict:
        mem_total_dict = mem_total_dict[0]
        plugin_data.add_output_data("Memory total = {0}{1}".format(
            mem_total_dict['value'], mem_total_dict['units']))
        plugin_data.add_perf_data("{0}={1}{2}".format(mem_total_dict['metric'],
                                                      mem_total_dict['value'],
                                                      mem_total_dict['units']))


def get_mem_used(plugin_data, verbose):
    mem_used_dict = memory_used(verbose)
    if mem_used_dict:
        mem_used_dict = mem_used_dict[0]
        plugin_data.add_output_data("Memory used = {0}{1}".format(
            mem_used_dict['value'], mem_used_dict['units']))
        plugin_data.add_perf_data("{0}={1}{2}".format(mem_used_dict['metric'],
                                                      mem_used_dict['value'],
                                                      mem_used_dict['units']))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', action='store_true', help="""
    Verbose mode;
    """)
    parser.add_argument('--all', action='store_true', help="""
    Get memory capacity and used memory;
    """)
    parser.add_argument('--total', action='store_true', help="""
    Get memory capacity;
    """)
    parser.add_argument('--used', action='store_true', help="""
    Get used memory;
    """)
    args = parser.parse_args()
    plugin_data = PluginData()

    if args.total or args.all:
        get_mem_total(plugin_data, args.verbose)
    if args.used or args.all:
        get_mem_used(plugin_data, args.verbose)
    plugin_data.exit()
