#!/usr/bin/python3
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
import json
import re
from collections import defaultdict
from enum import IntEnum

import defusedxml.ElementTree as ET

from lico.monitor.plugins.icinga.helper.base import (
    MetricsBase, PluginData, StateEnum,
)


class FormatEnum(IntEnum):
    DICT = 0
    STRING = 1


OUTPUT_MAP = {
    'gpu_name': FormatEnum.DICT,
    'gpu_driver': FormatEnum.DICT,
    'gpu_pcie': FormatEnum.DICT,
    'mig_profile': FormatEnum.DICT,
    'gpu_static': FormatEnum.DICT,
    'gpu_util': FormatEnum.STRING,
    'gpu_temp': FormatEnum.STRING,
    'gpu_mem_used': FormatEnum.STRING,
    'gpu_mem_total': FormatEnum.STRING,
    'gpu_proc_num': FormatEnum.STRING,
    'gpu_util_mem': FormatEnum.STRING,
    'mig_mode': FormatEnum.STRING,
    'mig_sm_count': FormatEnum.STRING,
    'mig_mem_used': FormatEnum.STRING,
    'mig_mem_total': FormatEnum.STRING,
    'mig_proc_num': FormatEnum.STRING,
    'gpu_dynamic': FormatEnum.STRING,
    'mig_resource': FormatEnum.STRING
}


PARAMS_MAP = {
    'gpu_name': ['gpu_name'],
    'gpu_driver': ['gpu_driver'],
    'gpu_pcie': ['gpu_pcie'],
    'mig_profile': ['mig_profile'],
    'gpu_temp': ['gpu_temp'],
    'gpu_util': ['gpu_util'],
    'gpu_mem_used': ['gpu_mem_used'],
    'gpu_mem_total': ['gpu_mem_total'],
    'gpu_proc_num': ['gpu_proc_num'],
    'gpu_util_mem': ['gpu_util_mem'],
    'mig_mode': ['mig_mode'],
    'mig_sm_count': ['mig_sm_count'],
    'mig_mem_used': ['mig_mem_used'],
    'mig_mem_total': ['mig_mem_total'],
    'mig_proc_num': ['mig_proc_num'],
    'gpu_dynamic': ['gpu_util', 'gpu_temp', 'gpu_mem_used',
                    'gpu_mem_total',
                    'gpu_proc_num', 'gpu_util_mem'],
    'gpu_static': ['gpu_name', 'gpu_driver', 'gpu_pcie'],
    'mig_resource': ['mig_sm_count', 'mig_mem_used', 'mig_mem_total',
                     'mig_proc_num'],
}

METRIC_MAP = {
    'gpu_util': 'utilization.gpu',
    'gpu_temp': 'temperature.gpu',
    'gpu_mem_used': 'memory.used',
    'gpu_mem_total': 'memory.total',
    'gpu_proc_num': 'uuid',
    'gpu_util_mem': 'utilization.memory',
    'gpu_name': 'name',
    'gpu_driver': 'driver_version',
    'gpu_pcie': 'pcie.link.gen.current,pcie.link.gen.max',
    'mig_mode': 'mig.mode.current',
    'mig_sm_count': '',
    'mig_mem_used': '',
    'mig_mem_total': '',
    'mig_proc_num': '',
    'mig_profile': '',

}


# GPU info monitor
class GPUMetric(MetricsBase):
    @classmethod
    def gpu_mig_mode_current(cls, content):

        from enum import Enum

        class Switch(Enum):
            ENABLED = 1
            DISABLED = 0
        output = content
        current_modes = list()
        for mode_str in output:
            index, mode = mode_str.split(',')
            out_state = mode.strip()
            mode = Switch.ENABLED.value \
                if mode.strip() == 'Enabled' else Switch.DISABLED.value
            current_modes.append(
                cls.build_point('gpu{0}_mig_mode'.format(
                    index.strip()),
                    mode,
                    "bool",
                    "",
                    'GPU{0} MIG Mode {1}'.format(
                        index.strip(), out_state if mode == 1 else 'Disable'),
                    StateEnum.OK)
            )
        return current_modes

    @classmethod
    def gpu_temperature(cls, content):
        # content: ['0, 33', '1, 33']
        output = content
        temp_list = list()
        for temp_str in output:
            index, temp = temp_str.split(', ')
            temp_list.append(cls.build_point(
                'gpu{0}_temp'.format(index), temp, 'uint', 'C',
                'GPU{0} temperature'.format(index), StateEnum.OK)
            )
        return temp_list

    @classmethod
    def gpu_model_name(cls, content):
        model_list = list()
        output = content
        for name_str in output:
            index, name = name_str.split(', ')
            model_list.append(cls.build_point(
                'gpu{}_product_name'.format(index),
                0,
                'string',
                '',
                {index: {'product_name': name}},
                StateEnum.OK,
                index
            ))
        return model_list

    @classmethod
    def _gpu_idx_uuid(cls, content):
        gpu_index_uuid = content
        return {
            i.split(',')[0].strip(): i.split(',')[1].strip()
            for i in gpu_index_uuid
        }

    @classmethod
    def _gpu_pid_uuid(cls):
        command = [
            'nvidia-smi', '--query-compute-apps=pid,gpu_uuid',
            '--format=csv,noheader'
        ]
        out, err, ret_code = cls.command_call(command)
        if ret_code:
            err_msg = out + err
            cls.print_err(err_msg)
            return 'error'
        else:
            '''[u'5895, GPU-2c09ffaca', u'5902, GPU-a43275af1']'''
            return out.decode().strip().split('\n') if out else []

    @classmethod
    def gpu_memory_used(cls, content):
        output_gpu_mem = content
        gpu_mem_usage = list()
        for gpu_mem_info in output_gpu_mem:
            idx, mem_usage = gpu_mem_info.strip().split(',')
            idx = idx.strip()
            mem_used = mem_usage.strip()
            gpu_mem_usage.append(
                cls.build_point(
                    'gpu{0}_mem_used'.format(idx),
                    int(mem_used),
                    'uint',
                    'MiB',
                    'GPU{0} used memory'.format(idx),
                    StateEnum.OK
                )
            )
        return gpu_mem_usage

    @classmethod
    def gpu_memory_total(cls, content):
        output_gpu_mem = content
        gpu_mem_usage = list()
        for gpu_mem_info in output_gpu_mem:
            idx, mem_usage = gpu_mem_info.strip().split(',')
            idx = idx.strip()
            mem_total = mem_usage.strip()
            gpu_mem_usage.append(
                cls.build_point(
                    'gpu{0}_mem_total'.format(idx),
                    int(mem_total),
                    'uint',
                    'MiB',
                    'GPU{0} total memory'.format(idx),
                    StateEnum.OK
                )
            )
        return gpu_mem_usage

    @classmethod
    def gpu_util(cls, content):
        output_gpu_util = content
        gpu_util = list()
        for gpu_util_info in output_gpu_util:
            idx, util = gpu_util_info.strip().split(',')
            idx = idx.strip()
            util = util.strip()
            try:
                if util == '[N/A]':
                    # Open MIG
                    mig_info_res = GPUMIGMetric().gpu_mig_info()
                    cls._gpu_with_mig_util(mig_info_res, idx, gpu_util)
                else:
                    gpu_util.append(
                        cls.build_point(
                            'gpu{0}_util'.format(idx),
                            util,
                            'uint',
                            '%',
                            'GPU{0} utilization'.format(idx),
                            StateEnum.OK
                        )
                    )
            except Exception:
                continue

        return gpu_util

    @classmethod
    def _gpu_with_mig_util(cls, mig_info_res, gpu_id, gpu_util):
        use_sm = 0
        gpu_pattern = re.compile(r"(?<=lico_gpu)\d+")

        for mig_info in mig_info_res:
            mi_gpu_id = gpu_pattern.search(
                mig_info['metric'].strip()).group()
            if gpu_id == mi_gpu_id:
                for gpu_mig_element in mig_info['value']:
                    if gpu_mig_element['process']:
                        use_sm += int(gpu_mig_element['sm_counts'])
                g_util = round(use_sm / int(
                    cls.get_sm_total()[str(gpu_id)]), 2) * 100
                gpu_util.append(
                    cls.build_point(
                        'gpu{0}_util'.format(gpu_id),
                        g_util,
                        'uint',
                        '%',
                        'GPU{0} utilization'.format(gpu_id),
                        StateEnum.OK
                    )
                )

    @classmethod
    def gpu_index_process(cls, content):
        # [u'5895, GPU-2c09ffaca', u'5902, GPU-a43275af1']
        pid_uuid_list = cls._gpu_pid_uuid()
        if pid_uuid_list == 'error':
            return []
        # {u'0': u'GPU-636d2089-62a6-72b7-0eb1-35d7abcb53ab'}
        idx_uuid = cls._gpu_idx_uuid(content)
        uuid_dict = defaultdict(int)
        for pid_uuid in pid_uuid_list:
            pid, uuid = pid_uuid.strip().split(',')
            uuid = uuid.strip()
            uuid_dict[uuid] += 1
        gpu_process = list()
        for idx, uuid in idx_uuid.items():
            gpu_process.append(
                cls.build_point(
                    'gpu{0}_proc_num'.format(idx),
                    uuid_dict[uuid],
                    'uint',
                    '',
                    'GPU{0} process number'.format(idx),
                    StateEnum.OK
                )
            )
        return gpu_process

    # Get the driver version
    @classmethod
    def gpu_driver_version(cls, content):
        output = content
        gpu_dv_list = list()
        for gpu_dv_str in output:
            index, gpu_dv = gpu_dv_str.split(', ')
            gpu_dv_list.append(cls.build_point(
                'gpu{0}_driver'.format(index),
                0, 'string', '', {index: {'driver_version': gpu_dv}},
                StateEnum.OK, index)
            )
        return gpu_dv_list

    # Get the PCIE version
    @classmethod
    def gpu_pcie_current(cls, content):
        output_gpu_pcie = content
        gpu_pcie_info = list()
        for gpu_pcie_str in output_gpu_pcie:
            index, gpu_pcie_current = gpu_pcie_str.split(', ')
            index = index.strip()
            gpu_pcie_current = gpu_pcie_current.strip()
            gpu_pcie_info.append(
                cls.build_point(
                    'gpu{0}_pcie_current'.format(index),
                    0,
                    'string',
                    '',
                    gpu_pcie_current,
                    StateEnum.OK,
                    index
                )
            )
        return gpu_pcie_info

    @classmethod
    def gpu_pcie_max(cls, content):
        output_gpu_pcie = content
        gpu_pcie_info = list()
        for gpu_pcie_str in output_gpu_pcie:
            index, gpu_pcie_max = gpu_pcie_str.split(', ')
            index = index.strip()
            gpu_pcie_max = gpu_pcie_max.strip()
            gpu_pcie_info.append(
                cls.build_point(
                    'gpu{0}_pcie_max'.format(index),
                    0,
                    'string',
                    '',
                    gpu_pcie_max,
                    StateEnum.OK,
                    index
                )
            )
        return gpu_pcie_info

    # Get GPU bandwidth utilization
    @classmethod
    def gpu_util_mem(cls, content):
        output = content
        gpu_util_mem_list = list()
        for gpu_util_mem_str in output:
            index, util_mem = gpu_util_mem_str.split(', ')
            if util_mem == '[N/A]':
                util_mem = 0
                gpu_util_mem_list.append(cls.build_point(
                    'gpu{0}_util_mem'.format(index),
                    util_mem,
                    'uint',
                    '%',
                    'GPU{0} utilization.memory'.format(index),
                    StateEnum.OK)
                )
            else:
                gpu_util_mem_list.append(cls.build_point(
                    'gpu{0}_util_mem'.format(index),
                    util_mem,
                    'uint',
                    '%',
                    'GPU{0} utilization.memory'.format(index),
                    StateEnum.OK)
                )
        return gpu_util_mem_list

    # Get all SM quantities
    @classmethod
    def get_sm_total(cls):
        # sm_total {'0': '98', '1': '98'}
        line_need = None
        sm_total = {}
        mig_need_info = []
        idx = None

        command = [
            'nvidia-smi', 'mig', '-lgip',
        ]
        out, err, ret_code = cls.command_call(command)
        if ret_code:
            cls.print_err(out + err)
            return {}
        output = out.decode().split('|')
        for i, line in enumerate(output):
            mig_info = line.split()
            if i == 3:
                line_need = len(mig_info)
            if line_need and len(mig_info) == line_need + 1:
                mig_need_info.append(mig_info)
        # mig_need_info:
        # [['0', 'MIG', '1g.5gb', '19', '0/7', '4.75'.............]
        if mig_need_info:
            for index, line in enumerate(mig_need_info):
                if index == 0:
                    idx = line[0]
                if line[0] != idx:
                    sm_total[mig_need_info[index - 1][0]] = \
                        mig_need_info[index - 1][7]
                    idx = line[0]
            sm_total[mig_need_info[-1][0]] = mig_need_info[-1][7]
        return sm_total


def get_sm_total():
    return GPUMetric().get_sm_total()


# GPU MIG info monitor
class GPUMIGMetric(MetricsBase):
    def gpu_mig_data(self, gpu_element_data):
        try:
            mig_monitor_result = []
            for gpu_data in gpu_element_data:
                miginfo_list = []
                process_info = []
                mig_mode_date = gpu_data.find('mig_mode')
                mig_mode_state = mig_mode_date.find('current_mig').text \
                    if mig_mode_date else None
                if mig_mode_state == 'Enabled':
                    process_info_data = gpu_data.findall('processes')
                    mig_elemet_data = gpu_data.find('mig_devices').findall(
                        'mig_device')
                    for process_data in process_info_data:
                        for job_info in process_data:
                            result = {}
                            process_gi = job_info.find(
                                'gpu_instance_id').text
                            process_ci = job_info.find(
                                'compute_instance_id').text

                            pid = job_info.find('pid').text
                            result["process_gi"] = process_gi
                            result["process_ci"] = process_ci
                            result["pid"] = pid
                            process_info.append(result)
                    # Get information about MIG
                    miginfo_list = self.get_data_info(
                        mig_elemet_data,
                        process_info,
                        miginfo_list)
                    gpu_index = gpu_data.find('minor_number').text
                    mig_monitor_result.append(self.build_point(
                        "lico_gpu{}_mig_devices".format(gpu_index),
                        miginfo_list,
                        'string',
                        '',
                    ))
                else:
                    mig_err = "The current device does not support MIG " \
                              "or MIG is not enabled"
                    self.print_err(mig_err)

                """
                    :return example:
                    [{'metric': 'lico_gpu0_mig_devices', 'value': [
                    {'mig_device': '0', 'gpu_instance_id': '1',
                    'computnstance_id': '0', 'memory_total': '20096 MiB',
                    'memory_used': '13 MiB', 'sm_counts': '14', 'util': 100,
                    'proces [], 'mig_jobid': [26189,], }]}]
                """
        except Exception:
            return 0
        return mig_monitor_result

    # need root premission
    def get_gpu_typename(self, gpu_instance_id,
                         compute_instance_id, gpu_mig_info):
        command = [
            'nvidia-smi', 'mig', '-gi',
            '{}'.format(gpu_instance_id), '-lci'
        ]
        out, err, ret_code = self.command_call(command)
        if ret_code:
            self.print_err(out + err)
            return []
        output = out.decode().split('|')
        for i in output:
            if "MIG" in i:
                if i.split()[5] == compute_instance_id:
                    gpu_mig_info["type_name"] = i.split()[3]
        return gpu_mig_info

    def get_data_info(self, mig_elemet_data, process_info, miginfo_list):
        for mig_data in mig_elemet_data:
            gpu_mig_info = {}
            # 'mig_device': '0'
            mig_device = mig_data.find(
                'index').text
            gpu_mig_info["mig_device"] = mig_device
            # 'gpu_instance_id': '0'
            gpu_instance_id = mig_data.find(
                'gpu_instance_id').text
            gpu_mig_info["gpu_instance_id"] = gpu_instance_id

            # 'compute_instance_id': '0'
            compute_instance_id = mig_data.find(
                'compute_instance_id').text
            gpu_mig_info["compute_instance_id"] = compute_instance_id

            # 'memory_total': '40536 MiB'
            memory_total = mig_data.find(
                'fb_memory_usage/total').text
            gpu_mig_info["memory_total"] = memory_total

            # 'memory_used': '0 MiB'
            memory_used = mig_data.find(
                'fb_memory_usage/used').text
            gpu_mig_info["memory_used"] = memory_used

            # 'sm_counts': '42'
            sm_counts = mig_data.find(
                'device_attributes/shared/multiprocessor_count'
            ).text
            gpu_mig_info["sm_counts"] = sm_counts

            # 'type_name': '3c.7g.40gb'
            self.get_gpu_typename(gpu_instance_id, compute_instance_id,
                                  gpu_mig_info)
            # Get pid 'process': []
            list_pid = []
            gpu_mig_info["process"] = []
            for process_mig_info in process_info:
                if process_mig_info['process_gi'] == gpu_instance_id \
                        and process_mig_info['process_ci'] == \
                        compute_instance_id:
                    list_pid.append(process_mig_info['pid'])
                gpu_mig_info["process"] = list_pid
            miginfo_list.append(gpu_mig_info)

        return miginfo_list

    def gpu_mig_info(self):

        command = [
            'nvidia-smi', '-q', '-x'
        ]
        out, err, ret_code = self.command_call(command)
        if ret_code:
            self.print_err(out + err)
            return []
        output = out.decode()

        gpu_element = ET.fromstring(output)
        gpu_element_data = gpu_element.findall('gpu')
        return self.gpu_mig_data(gpu_element_data)


def gpu_util(content):
    return GPUMetric().gpu_util(content)


def gpu_temp(content):
    return GPUMetric().gpu_temperature(content)


def gpu_memory_used(content):
    return GPUMetric().gpu_memory_used(content)


def gpu_memory_total(content):
    return GPUMetric().gpu_memory_total(content)


def gpu_index_process(content):
    return GPUMetric().gpu_index_process(content)


def gpu_util_mem(content):
    return GPUMetric().gpu_util_mem(content)


def gpu_model_name(content):
    return GPUMetric().gpu_model_name(content)


def gpu_driver_version(content):
    return GPUMetric().gpu_driver_version(content)


def gpu_pcie_current(content):
    return GPUMetric().gpu_pcie_current(content)


def gpu_pcie_max(content):
    return GPUMetric().gpu_pcie_max(content)


def gpu_mig_mode_current(content):
    return GPUMetric().gpu_mig_mode_current(content)


def gpu_mig_info():
    return GPUMIGMetric().gpu_mig_info()


# get gpu mig mode status<Enabled/Disabled>
def get_gpu_mig_mode_current(**kwargs):
    plugin_data = kwargs['plugin_data']
    content = kwargs['content']
    gpu_mig_mode_current_list = gpu_mig_mode_current(content)
    if gpu_mig_mode_current_list:
        for gpu_mig_mode_dict in gpu_mig_mode_current_list:
            metric = gpu_mig_mode_dict['metric']
            value = gpu_mig_mode_dict['value']
            output = gpu_mig_mode_dict['output']
            state = gpu_mig_mode_dict['state']
            plugin_data.add_output_data(
                f"{output}"
            )
            plugin_data.add_perf_data(
                f"{metric}={value}"
            )
            plugin_data.set_state(state)


# GPU temperature
def get_gpu_temp(**kwargs):
    plugin_data = kwargs['plugin_data']
    content = kwargs['content']
    gpu_temp_list = gpu_temp(content)
    if gpu_temp_list:
        for gpu_temp_dict in gpu_temp_list:
            metric = gpu_temp_dict['metric']
            value = gpu_temp_dict['value']
            units = gpu_temp_dict['units']
            output = gpu_temp_dict['output']
            state = gpu_temp_dict['state']

            plugin_data.add_output_data(
                f"{output} = {value}{units}"
            )
            plugin_data.add_perf_data(
                f"{metric}={value}"
            )
            plugin_data.set_state(state)


# GPU total memory
def get_gpu_memory_total(**kwargs):
    plugin_data = kwargs['plugin_data']
    content = kwargs['content']
    gpu_mem_total_list = gpu_memory_total(content)
    if gpu_mem_total_list:
        for gpu_mem_total_dict in gpu_mem_total_list:
            metric = gpu_mem_total_dict['metric']
            value = gpu_mem_total_dict['value']
            units = gpu_mem_total_dict['units']
            output = gpu_mem_total_dict['output']
            state = gpu_mem_total_dict['state']
            plugin_data.add_output_data(
                f"{output} = {value}{units}"
            )
            plugin_data.add_perf_data(
                f"{metric}={value}{units}"
            )
            plugin_data.set_state(state)


# GPU used memory
def get_gpu_memory_used(**kwargs):
    plugin_data = kwargs['plugin_data']
    content = kwargs['content']
    gpu_mem_used_list = gpu_memory_used(content)
    if gpu_mem_used_list:
        for gpu_mem_used_dict in gpu_mem_used_list:
            metric = gpu_mem_used_dict['metric']
            value = gpu_mem_used_dict['value']
            units = gpu_mem_used_dict['units']
            output = gpu_mem_used_dict['output']
            state = gpu_mem_used_dict['state']
            plugin_data.add_output_data(
                f"{output} = {value}{units}"
            )
            plugin_data.add_perf_data(
                f"{metric}={value}{units}"
            )
            plugin_data.set_state(state)


# GPU utilization
def get_gpu_util(**kwargs):
    plugin_data = kwargs['plugin_data']
    content = kwargs['content']
    gpu_util_list = gpu_util(content)
    if gpu_util_list:
        for gpu_util_dict in gpu_util_list:
            metric = gpu_util_dict['metric']
            value = gpu_util_dict['value']
            units = gpu_util_dict['units']
            output = gpu_util_dict['output']
            state = gpu_util_dict['state']
            plugin_data.add_output_data(
                f"{output} = {value}{units}"
                )
            plugin_data.add_perf_data(
                f"{metric}={value}{units}"
            )
            plugin_data.set_state(state)


# GPU process number
def get_gpu_index_process(**kwargs):
    plugin_data = kwargs['plugin_data']
    content = kwargs['content']
    gpu_process_list = gpu_index_process(content)
    if gpu_process_list:
        for gpu_process_dict in gpu_process_list:
            metric = gpu_process_dict['metric']
            value = gpu_process_dict['value']
            output = gpu_process_dict['output']
            state = gpu_process_dict['state']

            plugin_data.add_output_data(
                f"{output} = {value}"
            )
            plugin_data.add_perf_data(
                f"{metric}={value}"
            )
            plugin_data.set_state(state)


# GPU bandwidth utilization
def get_gpu_util_mem(**kwargs):
    plugin_data = kwargs['plugin_data']
    content = kwargs['content']
    gpu_util_mem_list = gpu_util_mem(content)
    if gpu_util_mem_list:
        """
        gpu0_util_mem = 100%
        """
        for gpu_util_mem_dict in gpu_util_mem_list:
            metric = gpu_util_mem_dict['metric']
            value = gpu_util_mem_dict['value']
            units = gpu_util_mem_dict['units']
            output = gpu_util_mem_dict['output']
            state = gpu_util_mem_dict['state']
            plugin_data.add_output_data(
                f"{output} = {value}{units}"
            )
            plugin_data.add_perf_data(
                f"{metric}={value}{units}"
            )
            plugin_data.set_state(state)


# GPU model name
def get_gpu_model_name(**kwargs):
    plugin_data = kwargs['plugin_data']
    content = kwargs['content']
    gpu_model_name_list = gpu_model_name(content)
    if gpu_model_name_list:
        for gpu_model_name_dict in gpu_model_name_list:
            metric = gpu_model_name_dict['metric']
            value = gpu_model_name_dict['value']
            units = gpu_model_name_dict['units']
            output = gpu_model_name_dict['output']
            state = gpu_model_name_dict['state']
            plugin_data.add_output_data(
                f"{json.dumps(output)}"
            )
            plugin_data.add_perf_data(
                f"{metric}={value}{units}"
            )
            plugin_data.set_state(state)


# GPU driver version
def get_gpu_driver_version(**kwargs):
    plugin_data = kwargs['plugin_data']
    content = kwargs['content']
    gpu_driver_version_list = gpu_driver_version(content)
    if gpu_driver_version_list:
        for gpu_driver_version_dict in gpu_driver_version_list:
            metric = gpu_driver_version_dict['metric']
            value = gpu_driver_version_dict['value']
            units = gpu_driver_version_dict['units']
            output = gpu_driver_version_dict['output']
            state = gpu_driver_version_dict['state']
            plugin_data.add_output_data(
                f"{json.dumps(output)}"
            )
            plugin_data.add_perf_data(
                f"{metric}={value}{units}"
            )
            plugin_data.set_state(state)


# GPU pcie version
def get_gpu_pcie_generation(**kwargs):
    plugin_data = kwargs['plugin_data']
    content = kwargs['content']
    gpu_pcie_current_list = gpu_pcie_current(content)
    gpu_pcie_max_list = gpu_pcie_max(content)
    if gpu_pcie_current_list and gpu_pcie_max_list:
        for current, max_pcie in zip(gpu_pcie_current_list, gpu_pcie_max_list):
            output_dict = dict()
            pcie_generation_dict = dict()
            output_dict['current'] = current['output']
            output_dict['max'] = max_pcie['output']
            """
            output_dict: {'current': 3, 'max': 3}
            """
            pcie_generation_dict[current['index']] = \
                {'pcie_generation': output_dict}
            state = current['state']
            index = current['index']
            value = current['value']
            units = current['units']
            plugin_data.add_output_data(
                f"{json.dumps(pcie_generation_dict)}"
            )
            plugin_data.add_perf_data(
                f"gpu{index}_pcie_generation={value}{units}"
            )
            plugin_data.set_state(state)


gpu_pattern = re.compile(r"(?<=lico_gpu)\d+")


# mig number of sm in different sizes
def get_mig_sm(**kwargs):
    plugin_data = kwargs['plugin_data']
    mig_resource_out = kwargs['mig_resource_out']
    if mig_resource_out:
        for gpu_element in mig_resource_out:
            idx = gpu_pattern.search(
                gpu_element['metric'].strip()).group()
            for mig_value in gpu_element['value']:
                dev = mig_value['mig_device']
                gi = mig_value['gpu_instance_id']
                ci = mig_value['compute_instance_id']
                sm_count = mig_value['sm_counts']
                plugin_data.add_output_data(
                    f"GPU{idx}.{dev}.{gi}.{ci} SM Count = "
                    f"{sm_count}"
                )
                plugin_data.add_perf_data(
                    f"gpu{idx}_{dev}_{gi}_{ci}_sm_count="
                    f"{sm_count}"
                )


# memory usage for different mig sizes
def get_mig_mem_used(**kwargs):
    plugin_data = kwargs['plugin_data']
    mig_resource_out = kwargs['mig_resource_out']
    if mig_resource_out:
        for gpu_element in mig_resource_out:
            idx = gpu_pattern.search(
                gpu_element['metric'].strip()).group()
            for mig_value in gpu_element['value']:
                dev = mig_value['mig_device']
                gi = mig_value['gpu_instance_id']
                ci = mig_value['compute_instance_id']
                mem_used = \
                    round(convert_uint(mig_value['memory_used']), 1)
                plugin_data.add_output_data(
                    f"GPU{idx}.{dev}.{gi}.{ci} Used Memory = "
                    f"{mem_used}"
                )
                plugin_data.add_perf_data(
                    f"gpu{idx}_{dev}_{gi}_{ci}_mem_used="
                    f"{mem_used}"
                )


# memory total for different mig sizes
def get_mig_total(**kwargs):
    plugin_data = kwargs['plugin_data']
    mig_resource_out = kwargs['mig_resource_out']
    if mig_resource_out:
        for gpu_element in mig_resource_out:
            idx = gpu_pattern.search(
                gpu_element['metric'].strip()).group()
            for mig_value in gpu_element['value']:
                dev = mig_value['mig_device']
                gi = mig_value['gpu_instance_id']
                ci = mig_value['compute_instance_id']
                mem_total = \
                    round(convert_uint(mig_value['memory_total']), 1)
                plugin_data.add_output_data(
                    f"GPU{idx}.{dev}.{gi}.{ci} Total Memory = "
                    f"{mem_total}"
                )
                plugin_data.add_perf_data(
                    f"gpu{idx}_{dev}_{gi}_{ci}_mem_total="
                    f"{mem_total}"
                )


# number of processes with different mig sizes
def get_mig_proc_num(**kwargs):
    plugin_data = kwargs['plugin_data']
    mig_resource_out = kwargs['mig_resource_out']
    if mig_resource_out:
        for gpu_element in mig_resource_out:
            idx = gpu_pattern.search(
                gpu_element['metric'].strip()).group()
            for mig_value in gpu_element['value']:
                dev = mig_value['mig_device']
                gi = mig_value['gpu_instance_id']
                ci = mig_value['compute_instance_id']
                process_num = len(mig_value['process'])
                plugin_data.add_output_data(
                    f"GPU{idx}.{dev}.{gi}.{ci} Process Number = "
                    f"{process_num}"
                )
                plugin_data.add_perf_data(
                    f"gpu{idx}_{dev}_{gi}_{ci}_proc_num="
                    f"{process_num}"
                )


# mig profile information
def mig_profile(mig_resource_out):
    try:
        gpu_mig_info_data = mig_resource_out
    except Exception:
        return 0
    else:
        if gpu_mig_info_data:
            gpu_pattern = re.compile(r"(?<=lico_gpu)\d+")
            profile_list = list()

            for gpu_element in gpu_mig_info_data:
                metric_list = list()
                output_list = list()
                idx = gpu_pattern.search(
                    gpu_element['metric'].strip()).group()
                for mig_value in gpu_element['value']:
                    dev = mig_value['mig_device']
                    gi = mig_value['gpu_instance_id']
                    ci = mig_value['compute_instance_id']
                    name = mig_value.get('type_name')
                    if not name:
                        return []
                    metric_list.append(f"gpu{idx}_{dev}_{gi}_{ci}")
                    output_list.append({'dev': dev, 'gi': gi,
                                        'ci': ci, 'profile': name})
                profile_list.append(MetricsBase.build_point(
                    metric_list,
                    0,
                    'string',
                    '',
                    {idx: {'logical_device': output_list}},
                    StateEnum.OK,
                    idx
                ))
            return profile_list


def get_mig_profile(**kwargs):
    plugin_data = kwargs['plugin_data']
    mig_resource_out = kwargs['mig_resource_out']
    mig_profile_list = mig_profile(mig_resource_out)
    if mig_resource_out and mig_profile_list:
        for mig_profile_dict in mig_profile_list:
            metric = mig_profile_dict['metric']
            value = mig_profile_dict['value']
            units = mig_profile_dict['units']
            output = mig_profile_dict['output']
            state = mig_profile_dict['state']
            plugin_data.add_output_data(
                f"{json.dumps(output)}"
            )
            plugin_data.set_state(state)
            for i in metric:
                plugin_data.add_perf_data(
                    f"{i}={value}{units}"
                )


# Processing special output
def format_output(plugin_data):
    dict_out_list = plugin_data.get_output_data(out_list=True)
    output_dict = dict()
    index_dict = dict()
    output_list = list()
    if dict_out_list:
        for i in dict_out_list:
            metric = json.loads(i)
            output_list.append(metric)
            for k, v in metric.items():
                index_dict[k] = 'index'

        for k in index_dict.keys():
            new_dict = dict()
            for i in output_list:
                if i.get(k):
                    new_dict.update(i.get(k))
            output_dict[k] = new_dict
        plugin_data.overwrite_data([json.dumps(output_dict)])


# unit conversion
def convert_uint(uint_data):
    # uint_data: '1024 MiB'
    try:
        data = uint_data.replace(" ", "")
        uint_mapping = {
            "KiB": float(data[:-3:]) / 1024,
            "MiB": float(data[:-3:]),
            "GiB": float(data[:-3:]) * 1024,
            "TiB": float(data[:-3:]) * 1024 ** 2,
            "PiB": float(data[:-3:]) * 1024 ** 3,
            "EiB": float(data[:-3:]) * 1024 ** 4
        }
        # The output value is in MIB
        return uint_mapping.get(data[-3:], 0)
    except Exception as e:
        print(e)


def add_argument(parser):
    parser.add_argument('--verbose', action='store_true',
                        help="""
                            Verbose mode;
                            """
                        )
    gpu_dynamic_group = parser.add_argument_group(
        title='GPU dynamic information')
    gpu_static_group = parser.add_argument_group(
        title='GPU static information')
    gpu_mig_group = parser.add_argument_group(
        title='GPU mig information')

    gpu_dynamic_group.add_argument('--gpu-dynamic', action='store_true',
                                   help="""
                                   Get GPU dynamic information (including
                                   GPU usage, temperature, memory usage,
                                   total memory, process number,
                                   memory bandwidth utilization);
                                   """
                                   )
    gpu_dynamic_group.add_argument('--gpu-util', action='store_true',
                                   help="""
                                   Get the usage for each GPU;
                                   """
                                   )
    gpu_dynamic_group.add_argument('--gpu-temp', action='store_true',
                                   help="""
                                   Get the temperature for each GPU;
                                   """
                                   )
    gpu_dynamic_group.add_argument('--gpu-mem-used', action='store_true',
                                   help="""
                                   Get the used memory for each GPU;
                                   """
                                   )
    gpu_dynamic_group.add_argument('--gpu-mem-total', action='store_true',
                                   help="""
                                   Get the total memory for each GPU;
                                   """
                                   )
    gpu_dynamic_group.add_argument('--gpu-proc-num', action='store_true',
                                   help="""
                                   Get the process number for each GPU;
                                   """
                                   )
    gpu_dynamic_group.add_argument('--gpu-util-mem', action='store_true',
                                   help="""
                                   Get the usage of memory bandwidth for
                                   each GPU;
                                   """
                                   )

    gpu_static_group.add_argument('--gpu-static', action='store_true',
                                  help="""
                                  Get GPU static information (including
                                  GPU product name, driver version,
                                  pcie information);
                                  """
                                  )

    gpu_static_group.add_argument('--gpu-name', action='store_true',
                                  help="""
                                  Get the product name for each GPU;
                                  """
                                  )
    gpu_static_group.add_argument('--gpu-driver', action='store_true',
                                  help="""
                                  Get the driver version for each GPU;
                                  """
                                  )
    gpu_static_group.add_argument('--gpu-pcie', action='store_true',
                                  help="""
                                  Get the pcie information for each GPU;
                                  """
                                  )
    gpu_mig_group.add_argument('--mig-profile', action='store_true',
                               help="""
                               Get the profile name for each MIG instance;
                               """
                               )
    gpu_mig_group.add_argument('--mig-resource', action='store_true',
                               help="""
                               Get the resource information for each
                               MIG instance;
                               """
                               )
    gpu_mig_group.add_argument('--mig-sm-count', action='store_true',
                               help="""
                               Get the SM count for each MIG instance;
                               """
                               )
    gpu_mig_group.add_argument('--mig-mem-used', action='store_true',
                               help="""
                               Get the used memory for each MIG instance;
                               """
                               )
    gpu_mig_group.add_argument('--mig-mem-total', action='store_true',
                               help="""
                               Get the total memory for each MIG instance;
                               """
                               )
    gpu_mig_group.add_argument('--mig-proc-num', action='store_true',
                               help="""
                               Get the process number for each MIG instance;
                               """
                               )
    gpu_mig_group.add_argument('--mig-mode', action='store_true',
                               help="""
                               Get the current MIG mode for each GPU;
                               """
                               )


gpu_handle_map = {
        'gpu_util': get_gpu_util,
        'gpu_temp': get_gpu_temp,
        'gpu_mem_used': get_gpu_memory_used,
        'gpu_mem_total': get_gpu_memory_total,
        'gpu_proc_num': get_gpu_index_process,
        'gpu_util_mem': get_gpu_util_mem,
        'mig_mode': get_gpu_mig_mode_current,
        'gpu_name': get_gpu_model_name,
        'gpu_driver': get_gpu_driver_version,
        'gpu_pcie': get_gpu_pcie_generation,
        'mig_sm_count': get_mig_sm,
        'mig_mem_used': get_mig_mem_used,
        'mig_mem_total': get_mig_total,
        'mig_proc_num': get_mig_proc_num,
        'mig_profile': get_mig_profile

    }


def handle_params(args):
    atomic_params_list = list()
    input_params_list = list()
    input_params_set = set()
    pre_param = ''
    for k, v in args.__dict__.items():
        if v and PARAMS_MAP.get(k):
            input_params_list.append(k)
            atomic_params_list += PARAMS_MAP.get(k)
            input_params_set.add(OUTPUT_MAP.get(k))
            if len(input_params_set) == 1:
                pre_param = k
            if len(input_params_set) >= 2:
                if args.verbose:
                    print(f"The input parameters {pre_param} "
                          f"and {k} conflict, please check the parameters")
                return [], []

    return atomic_params_list, input_params_set


def get_gpu_info(atomic_param_list: list) -> list:
    gpu_command_list = []
    output_list = []
    for atomic_use in atomic_param_list:
        if METRIC_MAP.get(atomic_use):
            gpu_command_list.append(METRIC_MAP.get(atomic_use))
    if gpu_command_list:
        command_gpu = [
            'nvidia-smi', '--query-gpu=index,{}'.format(
                ','.join(gpu_command_list)), '--format=csv,noheader,nounits']
        out, err, ret_code = MetricsBase().command_call(command_gpu)
        if ret_code:
            MetricsBase().print_err(out + err)
            return []
        output = out.decode().strip().split('\n')
        output_list = [x.split(',') for x in output]

    return output_list


def get_mig_info(atomic_param_list: list) -> list:
    mig_para = False
    for atomic_use in atomic_param_list:
        if not METRIC_MAP.get(atomic_use):
            mig_para = True
    if mig_para:
        mig_resource_out = gpu_mig_info()
        return mig_resource_out
    return []


def main():
    parser = argparse.ArgumentParser()
    add_argument(parser)
    args = parser.parse_args()

    MetricsBase.verbose = args.verbose
    plugin_data = PluginData()

    atomic_param_list, input_params_set = handle_params(args)

    if atomic_param_list:
        gpu_info = get_gpu_info(atomic_param_list)
        mig_info = get_mig_info(atomic_param_list)
        gpu_para_list = []
        for i in atomic_param_list:
            if METRIC_MAP.get(i):
                gpu_para_list.append(i)
        for index, value in enumerate(gpu_para_list):
            if gpu_info:
                content_need = [f'{i[0]},{i[index + 1]}' for i in gpu_info]
                if content_need:
                    gpu_handle_map[value](plugin_data=plugin_data,
                                          content=content_need)
        for value in atomic_param_list:
            if value not in gpu_para_list:
                gpu_handle_map[value](plugin_data=plugin_data,
                                      mig_resource_out=mig_info)

        if list(input_params_set)[0] == 0:
            format_output(plugin_data)

    plugin_data.exit()


if __name__ == '__main__':
    main()
