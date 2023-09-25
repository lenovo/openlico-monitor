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
import asyncio
import functools
import json
import os
import sys
from collections import defaultdict

from lico.monitor.plugins.icinga.helper.base import MetricsBase, PluginData


async def execute(command, preexec_fn=None):
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        preexec_fn=preexec_fn
    )
    result = defaultdict()
    std_out, std_err = await process.communicate()
    error = std_err.decode().strip()
    out = std_out.decode().strip()
    if not error:
        result = {command[1]: json.loads(out)}
    return out, error, result


def get_xpu_command_output():  # noqa: C901
    xpu_c = "xpumcli"
    output = {}
    try:
        discovery_command = [
                xpu_c, 'discovery', '-j'
            ]
        discovery_command_output, err, ret = \
            MetricsBase.command_call(discovery_command)
        if ret:
            MetricsBase.print_err(err)
        else:
            discovery_command_output = json.loads(
                discovery_command_output.decode().strip())
            output["discovery_command_output"] = discovery_command_output
            device_nums = len(discovery_command_output['device_list'])
            if device_nums:
                commands_list = []
                output['stats_command_n_output'] = []
                output['discovery_command_n_output'] = []
                output['ps_command_n_output'] = []
                for n in range(device_nums):
                    stats_command_n = [
                        xpu_c, 'stats',
                        '-d', '{}'.format(n), '-j'
                    ]
                    discovery_command_n = [
                        xpu_c, 'discovery', '-d',
                        '{}'.format(n), '-j'
                    ]
                    ps_command_n = [
                        xpu_c,
                        'ps',
                        '-d', '{}'.format(n),
                        '-j'
                    ]
                    commands_list.append(stats_command_n)
                    commands_list.append(discovery_command_n)
                    commands_list.append(ps_command_n)
                execute_commands = []
                for command in commands_list:
                    execute_commands.append(
                        functools.partial(
                            execute,
                            command=command,
                            preexec_fn=lambda: os.setuid(0)))

                loop = asyncio.get_event_loop()
                results = loop.run_until_complete(
                    asyncio.gather(*[func() for func in execute_commands]))
                loop.close()

                for result in results:
                    if not result[1]:
                        if "ps" in result[2].keys():
                            output['ps_command_n_output'].\
                                append(json.loads(result[0]))
                        elif "stats" in result[2].keys():
                            output['stats_command_n_output'].\
                                append(json.loads(result[0]))
                        elif "discovery" in result[2].keys():
                            output['discovery_command_n_output'].\
                                append(json.loads(result[0]))
                        else:
                            pass
            return output
    except Exception:
        return output


class XPUMetric(MetricsBase):
    output = get_xpu_command_output()

    @classmethod
    def _get_device_nums(cls):
        if cls.output:
            device_nums = len(cls.output['discovery_command_output']
                              ['device_list'])
            return device_nums
        else:
            return 0

    @classmethod
    def xpu_nums(cls):
        nums = cls._get_device_nums()
        if nums:
            return [
                cls.build_point('gpu_nums', nums, 'uint', '', index='')
            ]
        else:
            return []

    @classmethod
    def xpu_temperature(cls):
        temp_list = []
        nums = cls._get_device_nums()
        if nums:
            for n in range(nums):
                if 'stats_command_n_output' in cls.output.keys():
                    stats_out = cls.output['stats_command_n_output'][n]
                else:
                    return []
                temp = list()
                if 'tile_level' in stats_out.keys():
                    for data_list in stats_out["tile_level"]:
                        for data in data_list['data_list']:
                            if data["metrics_type"] == \
                                    "XPUM_STATS_GPU_CORE_TEMPERATURE":
                                temp.append(data["value"])
                else:
                    for data in stats_out['device_level']:
                        if data["metrics_type"] == \
                                "XPUM_STATS_GPU_CORE_TEMPERATURE":
                            temp.append(data["value"])
                temp_list.append(cls.build_point(
                    'gpu{0}_temp'.format(n),
                    int(max(temp)) if temp else 0,
                    'uint',
                    'C',
                    index=n)
                )
        return temp_list

    @classmethod
    def xpu_product_name(cls):
        if "discovery_command_output" in cls.output.keys():
            discovery_out = cls.output['discovery_command_output']
        else:
            return []
        product_list = list()
        for device in discovery_out["device_list"]:
            index, name = device["device_id"], device["device_name"]
            product_list.append(cls.build_point(
                'gpu{0}_product_name'.format(index),
                name,
                'string',
                '',
                index=index))
        return product_list

    @classmethod  # noqa: C901
    def xpu_memory_usage(cls, type):
        gpu_mem_usage = list()
        nums = cls._get_device_nums()
        if nums:
            for n in range(nums):
                if 'stats_command_n_output' in cls.output.keys():
                    stats_out = cls.output['stats_command_n_output'][n]
                else:
                    return []
                if 'discovery_command_n_output' in cls.output.keys():
                    discovery_out = \
                        cls.output['discovery_command_n_output'][n]
                else:
                    return []
                memory_used = 0.0
                if 'tile_level' in stats_out.keys():
                    for stat in stats_out['tile_level']:
                        data_lists = stat['data_list']
                        for data in data_lists:
                            if data['metrics_type'] == \
                                    'XPUM_STATS_MEMORY_USED':
                                memory_used += float(data['value'])
                else:
                    for data in stats_out['device_level']:
                        if data['metrics_type'] == 'XPUM_STATS_MEMORY_USED':
                            memory_used += float(data['value'])
                if "memory_physical_size_byte" in discovery_out.keys():
                    memory_total = float(
                        int(discovery_out[
                                "memory_physical_size_byte"])/1024/1024)
                else:
                    memory_total = float(discovery_out["memory_physical_size"])
                gpu_mem_usage.append(cls.build_point(
                    'gpu{0}_mem_{1}'.format(n, type),
                    int(locals().get('memory_' + type)),
                    'uint',
                    'MiB',
                    index=n)
                )
        return gpu_mem_usage

    @classmethod
    def xpu_memory_total(cls):
        return cls.xpu_memory_usage('total')

    @classmethod
    def xpu_memory_used(cls):
        return cls.xpu_memory_usage('used')

    @classmethod
    def xpu_util(cls):
        gpu_util = list()
        nums = cls._get_device_nums()
        if nums:
            for n in range(nums):
                if 'stats_command_n_output' in cls.output.keys():
                    stats_out = cls.output['stats_command_n_output'][n]
                else:
                    return []
                util = 0
                if 'tile_level' in stats_out.keys():
                    tile_num = len(stats_out['tile_level'])
                    for tile in stats_out['tile_level']:
                        data_list = tile['data_list']
                        for data in data_list:
                            if data["metrics_type"] == \
                                    "XPUM_STATS_GPU_UTILIZATION":
                                util += data["value"]
                else:
                    tile_num = 1
                    for data in stats_out['device_level']:
                        if data["metrics_type"] == \
                                "XPUM_STATS_GPU_UTILIZATION":
                            util += data["value"]
                gpu_util.append(
                    cls.build_point(
                        'gpu{0}_util'.format(n),
                        round(util/tile_num, 1),
                        'uint',
                        '%',
                        index=n
                    )
                )
        return gpu_util

    @classmethod
    def xpu_index_process(cls):
        nums = cls._get_device_nums()
        pid_list = list()
        xpu_process = list()
        if nums:
            for n in range(nums):
                if 'ps_command_n_output' in cls.output.keys():
                    ps_out = cls.output['ps_command_n_output'][n]
                else:
                    return []
                for proc in ps_out["device_util_by_proc_list"]:
                    if proc['process_name'] not in \
                            ["xpu-smi", "xpumd", "slurmd"]:
                        pid_list.append(proc["process_id"])
                xpu_process.append(
                    cls.build_point(
                        'gpu{0}_proc_num'.format(n),
                        len(set(pid_list)),
                        'uint',
                        '',
                        index=n
                    )
                )
        return xpu_process

    @classmethod
    def xpu_driver_version(cls):
        gpu_dv_list = list()
        nums = cls._get_device_nums()
        if nums:
            for n in range(nums):
                if 'discovery_command_n_output' in cls.output.keys():
                    discovery_out = \
                        cls.output['discovery_command_n_output'][n]
                else:
                    return []
                gpu_dv = discovery_out["driver_version"]
                gpu_dv_list.append(cls.build_point(
                        'gpu{0}_driver'.format(n),
                        gpu_dv, 'string', '', index=n)
                    )
        return gpu_dv_list

    @classmethod
    def xpu_pcie_generation(cls):
        gpu_pcie_info = list()
        nums = cls._get_device_nums()
        if nums:
            for n in range(nums):
                if 'discovery_command_n_output' in cls.output.keys():
                    discovery_out = \
                        cls.output['discovery_command_n_output'][n]
                else:
                    return []
                gpu_pcie_current = discovery_out["pcie_generation"]
                gpu_pcie_max = ""
                gpu_pcie_info.append(
                    cls.build_point(
                        'gpu{0}_pcie_generation'.format(n),
                        {'current': gpu_pcie_current, 'max': gpu_pcie_max},
                        'string',
                        '',
                        index=n
                    )
                )
        return gpu_pcie_info

    @classmethod
    def xpu_util_mem(cls):
        gpu_util_mem_list = list()
        nums = cls._get_device_nums()
        if nums:
            for n in range(nums):
                if 'stats_command_n_output' in cls.output.keys():
                    stats_out = cls.output['stats_command_n_output'][n]
                else:
                    return []
                util_mem = 0
                if 'tile_level' in stats_out.keys():
                    tile_num = len(stats_out['tile_level'])
                    for tile in stats_out['tile_level']:
                        data_list = tile['data_list']
                        for data in data_list:
                            if data["metrics_type"] == \
                                    "XPUM_STATS_MEMORY_BANDWIDTH":
                                util_mem += data["value"]
                else:
                    tile_num = 1
                    for data in stats_out['device_level']:
                        if data["metrics_type"] == \
                                "XPUM_STATS_MEMORY_BANDWIDTH":
                            util_mem += data["value"]
                gpu_util_mem_list.append(
                    cls.build_point(
                        'gpu{0}_util_mem'.format(n),
                        round(util_mem/tile_num, 1),
                        'string',
                        '%',
                        index=n
                    )
                )
        return gpu_util_mem_list


class XPUTILEMetric(XPUMetric):

    @classmethod
    def _xpu_tile_data(cls, stats, tile_nums, memory_total):
        xpu_tile_info = []
        xpu_tiles = []
        if int(tile_nums) == 1:
            xpu_tile = {}
            xpu_tile['tile_id'] = 0
            xpu_tile['data_list'] = stats['device_level']
            xpu_tiles.append(xpu_tile)
        else:
            xpu_tiles = stats['tile_level']
        for xpu_tile in xpu_tiles:
            xpu_tile_dict = {}
            xpu_tile_dict['memory_used'] = 0
            xpu_tile_dict['gpu_utilization'] = 0
            xpu_tile_dict['gpu_temperature'] = 0
            xpu_tile_dict['gpu_bandwidth_utilization'] = 0
            xpu_tile_dict['tile_id'] = xpu_tile['tile_id']
            xpu_tile_dict['memory_total'] = float(memory_total)/int(tile_nums)
            for data in xpu_tile['data_list']:
                if data['metrics_type'] == 'XPUM_STATS_MEMORY_USED':
                    xpu_tile_dict['memory_used'] = round(data['value'], 1)
                elif data['metrics_type'] == 'XPUM_STATS_GPU_UTILIZATION':
                    xpu_tile_dict['gpu_utilization'] = round(data['value'], 1)
                elif data['metrics_type'] == \
                        'XPUM_STATS_GPU_CORE_TEMPERATURE':
                    xpu_tile_dict['gpu_temperature'] = int(data['value'])
                elif data['metrics_type'] == 'XPUM_STATS_MEMORY_BANDWIDTH':
                    xpu_tile_dict['gpu_bandwidth_utilization'] = \
                        round(data['value'], 1)
            xpu_tile_info.append(xpu_tile_dict)
        return xpu_tile_info

    @classmethod
    def xpu_tile_info(cls):
        xpu_tile_monitor_result = list()
        nums = cls._get_device_nums()
        if nums:
            for n in range(nums):
                if 'stats_command_n_output' in cls.output.keys():
                    output_stats = cls.output['stats_command_n_output'][n]
                else:
                    return []
                if 'discovery_command_n_output' in cls.output.keys():
                    output_discovery = cls.output[
                        'discovery_command_n_output'][n]
                else:
                    return []
                tile_nums = output_discovery['number_of_tiles']
                if "memory_physical_size_byte" in output_discovery.keys():
                    vram = str(float(int(output_discovery
                                         ['memory_physical_size_byte']
                                         )/1024/1024))
                else:
                    vram = output_discovery['memory_physical_size']
                xpu_tile_monitor_result.append(cls.build_point(
                    "gpu{}_xpu_tiles".format(n),
                    cls._xpu_tile_data(
                        output_stats,
                        tile_nums,
                        vram),
                    'string',
                    '',
                    index=n
                ))
        return xpu_tile_monitor_result


def get_gpu_temp(plugin_data, verbose):
    try:
        gpu_temp_list = XPUMetric.xpu_temperature()
    except Exception as e:
        if verbose:
            raise e
        return []
    else:
        for gpu_temp_dict in gpu_temp_list:
            plugin_data.add_output_data(
                "GPU{} temperature = {}{}".format(
                    gpu_temp_dict['index'],
                    int(gpu_temp_dict['value']),
                    gpu_temp_dict['units']
                )
            )
            plugin_data.add_perf_data(
                "{}={}{}".format(
                    gpu_temp_dict['metric'],
                    int(gpu_temp_dict['value']),
                    '')
            )


def get_gpu_util(plugin_data, verbose):
    try:
        gpu_util_list = XPUMetric.xpu_util()
    except Exception as e:
        if verbose:
            raise e
        return []
    else:
        for gpu_util_dict in gpu_util_list:
            plugin_data.add_output_data(
                "GPU{} utilization = {}{}".format(
                    gpu_util_dict['index'],
                    gpu_util_dict['value'],
                    gpu_util_dict['units']
                )
            )
            plugin_data.add_perf_data(
                "{}={}{}".format(
                    gpu_util_dict['metric'],
                    gpu_util_dict['value'],
                    gpu_util_dict['units'])
            )


def get_gpu_static(plugin_data, verbose):
    try:
        nums = XPUMetric.xpu_nums()
        gpu_pcie_generation_list = XPUMetric.xpu_pcie_generation()
        gpu_driver_version_list = XPUMetric.xpu_driver_version()
        gpu_product_name_list = XPUMetric.xpu_product_name()
    except Exception as e:
        if verbose:
            raise e
        return []
    else:
        if nums:
            gpu_nums = nums[0]['value']
            output = defaultdict()
            for i in range(gpu_nums):
                gpu_pcie_generation_dict = gpu_pcie_generation_list[i]
                gpu_driver_version_dict = gpu_driver_version_list[i]
                gpu_product_name_dict = gpu_product_name_list[i]
                output[str(i)] = {"product_name":
                                  gpu_product_name_dict['value'],
                                  "driver_version":
                                  gpu_driver_version_dict['value'],
                                  "pcie_generation":
                                  gpu_pcie_generation_dict['value']}
                plugin_data.add_perf_data(
                    "{}={}".format(
                        gpu_product_name_dict['metric'],
                        1)
                )
                plugin_data.add_perf_data(
                    "{}={}".format(
                        gpu_driver_version_dict['metric'],
                        0)
                )
                plugin_data.add_perf_data(
                    "{}={}".format(
                        gpu_pcie_generation_dict['metric'],
                        0)
                )
            plugin_data.add_output_data(
                json.dumps(output))


def get_gpu_index_process(plugin_data, verbose):
    try:
        gpu_process_list = XPUMetric.xpu_index_process()
    except Exception as e:
        if verbose:
            raise e
        return []
    else:
        for gpu_process_dict in gpu_process_list:
            plugin_data.add_output_data(
                "GPU{} process number = {}".format(
                    gpu_process_dict['index'],
                    gpu_process_dict['value']
                )
            )
            plugin_data.add_perf_data(
                "{}={}".format(
                    gpu_process_dict['metric'],
                    gpu_process_dict['value'])
            )


def get_gpu_mem_used(plugin_data, verbose):
    try:
        gpu_mem_used_list = XPUMetric.xpu_memory_used()
    except Exception as e:
        if verbose:
            raise e
        return []
    else:
        for gpu_mem_used_dict in gpu_mem_used_list:
            plugin_data.add_output_data(
                "GPU{} used memory = {}{}".format(
                    gpu_mem_used_dict['index'],
                    gpu_mem_used_dict['value'],
                    gpu_mem_used_dict['units']
                )
            )
            plugin_data.add_perf_data(
                "{}={}{}".format(
                    gpu_mem_used_dict['metric'],
                    gpu_mem_used_dict['value'],
                    gpu_mem_used_dict['units'])
            )


def get_gpu_mem_total(plugin_data, verbose):
    try:
        gpu_mem_total_list = XPUMetric.xpu_memory_total()
    except Exception as e:
        if verbose:
            raise e
        return []
    else:
        for gpu_mem_total_dict in gpu_mem_total_list:
            plugin_data.add_output_data(
                "GPU{} total memory = {}{}".format(
                    gpu_mem_total_dict['index'],
                    gpu_mem_total_dict['value'],
                    gpu_mem_total_dict['units']
                )
            )
            plugin_data.add_perf_data(
                "{}={}{}".format(
                    gpu_mem_total_dict['metric'],
                    gpu_mem_total_dict['value'],
                    gpu_mem_total_dict['units'])
            )


def get_gpu_util_mem(plugin_data, verbose):
    try:
        gpu_util_mem_list = XPUMetric.xpu_util_mem()
    except Exception as e:
        if verbose:
            raise e
        return []
    else:
        for gpu_util_mem_dict in gpu_util_mem_list:
            plugin_data.add_output_data(
                "GPU{} utilization.memory = {}{}".format(
                    gpu_util_mem_dict['index'],
                    gpu_util_mem_dict['value'],
                    gpu_util_mem_dict['units']
                )
            )
            plugin_data.add_perf_data(
                "{}={}{}".format(
                    gpu_util_mem_dict['metric'],
                    gpu_util_mem_dict['value'],
                    gpu_util_mem_dict['units'])
            )


def get_xpu_tile_info(plugin_data, verbose):
    try:
        xpu_tile_info_list = XPUTILEMetric().xpu_tile_info()
    except Exception as e:
        if verbose:
            raise e
        return []
    else:
        for xpu_tile_info_dict in xpu_tile_info_list:
            for tile_value in xpu_tile_info_dict['value']:
                plugin_data.add_output_data(
                    "GPU{}.{} memory.usage = {}{}".format(
                        xpu_tile_info_dict['index'],
                        tile_value['tile_id'],
                        round((tile_value['memory_used'] /
                               tile_value['memory_total']) * 100, 1),
                        '%'
                    )
                )
                plugin_data.add_perf_data(
                    "gpu{}_{}_mem_usage={}{}".format(
                        xpu_tile_info_dict['index'],
                        tile_value['tile_id'],
                        round((tile_value['memory_used'] /
                               tile_value['memory_total']) * 100, 1),
                        '%'
                    ))
                plugin_data.add_output_data(
                    "GPU{}.{} utilization = {}{}".format(
                        xpu_tile_info_dict['index'],
                        tile_value['tile_id'],
                        tile_value['gpu_utilization'],
                        '%'
                    )
                )
                plugin_data.add_perf_data(
                    "gpu{}_{}_util={}{}".format(
                        xpu_tile_info_dict['index'],
                        tile_value['tile_id'],
                        tile_value['gpu_utilization'],
                        '%'
                    ))
                plugin_data.add_output_data(
                    "GPU{}.{} temperature = {}{}".format(
                        xpu_tile_info_dict['index'],
                        tile_value['tile_id'],
                        int(tile_value['gpu_temperature']),
                        'C'
                    )
                )
                plugin_data.add_perf_data(
                    "gpu{}_{}_temp={}{}".format(
                        xpu_tile_info_dict['index'],
                        tile_value['tile_id'],
                        int(tile_value['gpu_temperature']),
                        ''
                    ))
                plugin_data.add_output_data(
                    "GPU{}.{} used memory = {}{}".format(
                        xpu_tile_info_dict['index'],
                        tile_value['tile_id'],
                        tile_value['memory_used'],
                        'MiB'
                    )
                )
                plugin_data.add_perf_data(
                    "gpu{}_{}_mem_used={}{}".format(
                        xpu_tile_info_dict['index'],
                        tile_value['tile_id'],
                        int(tile_value['memory_used']),
                        'MiB'
                    ))
                plugin_data.add_output_data(
                    "GPU{}.{} utilization.bandwidth = {}{}".format(
                        xpu_tile_info_dict['index'],
                        tile_value['tile_id'],
                        tile_value['gpu_bandwidth_utilization'],
                        '%'
                    )
                )
                plugin_data.add_perf_data(
                    "gpu{}_{}_util_bandwidth={}{}".format(
                        xpu_tile_info_dict['index'],
                        tile_value['tile_id'],
                        tile_value['gpu_bandwidth_utilization'],
                        '%'
                    ))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--dynamic', action='store_true',
                        help='Get the dynamic information of XPU, '
                             'like utilization.')
    parser.add_argument('-s', '--static', action='store_true',
                        help='Get the static information of XPU, '
                             'like driver version, product name '
                             'and pcie generation.')
    parser.add_argument('-t', '--tile', action='store_true',
                        help='Get the tile information of XPU')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Verbose mode')
    args = parser.parse_args()

    plugin_data = PluginData()
    if args.dynamic:
        get_gpu_util(plugin_data, args.verbose)
        get_gpu_temp(plugin_data, args.verbose)
        get_gpu_mem_used(plugin_data, args.verbose)
        get_gpu_mem_total(plugin_data, args.verbose)
        get_gpu_index_process(plugin_data, args.verbose)
        get_gpu_util_mem(plugin_data, args.verbose)
    if args.static and (args.dynamic or args.tile):
        if args.verbose:
            print("There is a conflict between parameter --static with "
                  "--dynamic or --tile, please check the parameters")
            sys.exit(2)
        else:
            sys.exit(2)
    elif args.static:
        get_gpu_static(plugin_data, args.verbose)
    if args.tile:
        get_xpu_tile_info(plugin_data, args.verbose)
    plugin_data.exit()
