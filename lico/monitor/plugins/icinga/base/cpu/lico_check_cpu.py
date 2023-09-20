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
import json
import os
import re
import time

from lico.monitor.plugins.icinga.helper.base import MetricsBase, PluginData


class ProcessorMetrics(MetricsBase):
    processor_stat = '/proc/stat'
    processor_load = '/proc/loadavg'

    @classmethod
    def cpu_load(cls):
        if not os.path.exists(cls.processor_load):
            cls.print_err(
                'Get CPU load failed, %s does not exist' %
                cls.processor_load
            )
            return []
        with open(cls.processor_load, 'r') as f:
            load_one_avg = float(f.readline().strip().split()[0])
        return [cls.build_point('cpu_load', load_one_avg, 'float', '')]

    @classmethod
    def cpu_util(cls):
        if not os.path.exists(cls.processor_stat):
            cls.print_err(
                'Get CPU Utilization failed: %s does not exist' %
                cls.processor_stat
            )
            return []

        def sum_cpu_total_time(time_list):
            return sum(map(int, time_list))

        # Example for cls.processor_stat:
        '''
        cpu 109362289 22602 36116382 2483059643 133283 0 2404558 360691 0 0
        '''
        # The 4 column is the accumulated idle time for the moment
        with open(cls.processor_stat, 'r') as f:
            prev_moment = re.split(r'\s+', f.readline())[1:-1]
            time.sleep(3)
            f.seek(0)
            latest_moment = re.split(r'\s+', f.readline())[1:-1]
            prev_total_time = sum_cpu_total_time(prev_moment)
            latest_total_time = sum_cpu_total_time(latest_moment)
            total_time_slice = latest_total_time - prev_total_time

            # Get the CPU free time slice
            free_time_slice = int(latest_moment[3]) - int(prev_moment[3])
            cpu_util = round(
                100.0 * (
                        total_time_slice - free_time_slice) / total_time_slice,
                1
            )
        return [cls.build_point('cpu_util', cpu_util, 'float', '%')]


class CPUSocketMetric(MetricsBase):

    @classmethod
    def parse_lscpu(cls):
        """
        output_dict format:
        {
            "Architecture":"x86_64",
            "CPU op-mode(s)":"32-bit, 64-bit",
            "Byte Order":"Little Endian",
            "CPU(s)":"4",
            "On-line CPU(s) list":"0-3",
            "Thread(s) per core":"1",
            "Core(s) per socket":"1",
            "Socket(s)":"4",
            "NUMA node(s)":"1",
            "Vendor ID":"GenuineIntel",
            "CPU family":"6",
            "Model":"94",
            "Model name":"Intel Core Processor (Skylake, IBRS)",
            "Stepping":"3",
            "CPU MHz":"2099.998",
            "BogoMIPS":"4199.99",
            "Hypervisor vendor":"KVM",
            "Virtualization type":"full",
            "L1d cache":"32K",
            "L1i cache":"32K",
            "L2 cache":"4096K",
            "L3 cache":"16384K",
            "NUMA node0 CPU(s)":"0-3",
        }
        """

        """
        For the explanation of "lscpu -J":
            When util-linux version < 2.39.rc1, the default is to use
            subsections only when output on a terminal and flattened output
            on a non-terminal.

            When util-linux version >= 2.39.rc1, add the following parameter,
            --hierarchic[=when]
               Use subsections in summary output. For backward
               compatibility, the default is to use subsections only when
               output on a terminal and flattened output on a non-terminal.
               The optional argument when can be never, always or auto. If
               the when argument is omitted, it defaults to "always".

        For more information,
        please see https://www.man7.org/linux/man-pages/man1/lscpu.1.html
        """
        out, err, ret_code = cls.command_call(['lscpu', '-J'])
        if ret_code:
            cls.print_err(out + err)
            return {}

        output_dict = dict()
        for info in json.loads(out).get('lscpu', []):
            if not info['field']:
                continue
            output_dict[info['field'][:-1]] = info['data']

        return output_dict

    @classmethod
    def cpu_socket_num(cls):
        lscpu_info = cls.parse_lscpu()

        result = {
            "Cpu Thread Per Core": lscpu_info["Thread(s) per core"],
            "Cpu Core Per Socket": lscpu_info["Core(s) per socket"],
            "Cpu Socket Num": lscpu_info["Socket(s)"],
        }

        return [
            cls.build_point(k, v, 'uint', '') for k, v in result.items()
        ]

    @classmethod
    def hypervisor_vendor(cls):
        lscpu_info = cls.parse_lscpu()

        hypervisor_vendor = lscpu_info.get("Hypervisor vendor", None)
        if hypervisor_vendor:
            result = [
                cls.build_point(
                    "hypervisor_vendor", hypervisor_vendor, 'uint',
                    '')
            ]
        else:
            result = []

        return result


def cpu_socket_num(verbose):
    CPUSocketMetric.verbose = verbose
    return CPUSocketMetric.cpu_socket_num()


def get_hypervisor_vendor(verbose):
    CPUSocketMetric.verbose = verbose
    return CPUSocketMetric.hypervisor_vendor()


def cpu_load(verbose):
    ProcessorMetrics.verbose = verbose
    return ProcessorMetrics.cpu_load()


def cpu_util(verbose):
    ProcessorMetrics.verbose = verbose
    return ProcessorMetrics.cpu_util()


def get_cpu_load(plugin_data, verbose):
    cpu_load_dict = cpu_load(verbose)
    if cpu_load_dict:
        cpu_load_dict = cpu_load_dict[0]
        plugin_data.add_output_data(
            f"Cpu load = {cpu_load_dict['value']}"
        )
        plugin_data.add_perf_data(
            f"'{cpu_load_dict['metric']}'={cpu_load_dict['value']};"
        )


def get_cpu_util(plugin_data, verbose):
    cpu_util_dict = cpu_util(verbose)
    if cpu_util_dict:
        cpu_util_dict = cpu_util_dict[0]
        plugin_data.add_output_data(
            f"Cpu util = {cpu_util_dict['value']}{cpu_util_dict['units']}"
        )
        plugin_data.add_perf_data(
            f"'{cpu_util_dict['metric']}'="
            f"{cpu_util_dict['value']}{cpu_util_dict['units']};"
        )


def get_cpu_core_info(plugin_data, verbose):
    cpu_core_info = cpu_socket_num(verbose)
    if cpu_core_info:
        for item in cpu_core_info:
            plugin_data.add_output_data(
                f"{item['metric']} = {item['value']}"
            )
            plugin_data.add_perf_data(
                "'{}'={};".format(
                    "_".join(item['metric'].split()).lower(),
                    item['value']
                )
            )


def get_hypervisor(plugin_data, verbose):
    hypervisor = get_hypervisor_vendor(verbose)
    if hypervisor:
        plugin_data.add_output_data(
            f"Hypervisor Vendor = {hypervisor[0]['value']}"
        )
        plugin_data.add_perf_data("'hypervisor_mode'=1;")
    else:
        plugin_data.add_perf_data("'hypervisor_mode'=0;")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', action='store_true', help="""
    Verbose mode;
    """)
    parser.add_argument('--dynamic', action='store_true', help="""
    Get CPU dynamic information (including CPU load, utilization);
    """)
    parser.add_argument('--static', action='store_true', help="""
    Get CPU static information (including CPU core, hypervisor information);
    """)
    parser.add_argument('--all', action='store_true', help="""
    Get CPU dynamic and static information;
    """)
    parser.add_argument('--load', action='store_true', help="""
    Get CPU load;
    """)
    parser.add_argument('--util', action='store_true', help="""
    Get CPU utilization;
    """)
    parser.add_argument('--core', action='store_true', help="""
    Get CPU core;
    """)
    parser.add_argument('--hypervisor', action='store_true', help="""
    Get CPU hypervisor information;
    """)
    args = parser.parse_args()

    plugin_data = PluginData()

    if args.load or args.dynamic or args.all:
        get_cpu_load(plugin_data, args.verbose)
    if args.util or args.dynamic or args.all:
        get_cpu_util(plugin_data, args.verbose)
    if args.core or args.static or args.all:
        get_cpu_core_info(plugin_data, args.verbose)
    if args.hypervisor or args.static or args.all:
        get_hypervisor(plugin_data, args.verbose)
    plugin_data.exit()
