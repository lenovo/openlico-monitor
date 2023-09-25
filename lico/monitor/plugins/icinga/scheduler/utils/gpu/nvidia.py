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

import re
import time
from collections import defaultdict

from lico.monitor.plugins.icinga.scheduler.utils import (
    command_call, convert_unit,
)


class GPUInfo:
    index = None
    uuid = None
    vram = 0
    # utilization rate
    used = 0


def get_gpu_res_by_job(sche_list, plugin_data, verbose):
    try:
        # sm_total: {'0': 96, ...}   # gpu_index: sm_total
        gpu_mig_dict, sm_total = _get_mig_info(verbose)
        gp_dict, gp_mem_dict = _get_gpu_info()
        """
        gp_dict = {
            g_uuid: gp_info(index, g_uuid, util, vram)
        }
        gp_mem_dict = {
            g_pid:[(g_uuid, vram_used), ...]
        }
        """
        time.sleep(0.02)  # wait for cpu_percent compute
        for sche in sche_list:
            # index_pids = {'index': ['pid1', 'pid2']}
            index_pids = _get_gpu_running_pids(sche, gp_dict, gp_mem_dict)
            for g in sche.gpu.values():
                gpu_sm_total = sm_total.get(g.index)
                util = g.used
                plugin_data.add_output_data(
                    f"Job {sche.id} Usage on GPU Device gpu{g.index}"
                )
                # If GPU usage is [N/A], it means MIG is enabled.
                # GPU usage is not available.
                if not g.used == "[N/A]":
                    plugin_data.add_perf_data(
                        f"job_{sche.id}_gpu{g.index}_util={util}%"
                    )
                    plugin_data.add_perf_data(
                        f"job_{sche.id}_gpu{g.index}_mem_usage="
                        f"{(sche.gpu_vram[g.uuid] / g.vram) * 100}%"
                    )
                else:
                    for pid in index_pids[g.index]:
                        if g.used == "[N/A]" and gpu_sm_total and \
                                pid in gpu_mig_dict[g.index]:
                            mig_pid_info = gpu_mig_dict[g.index][pid]
                            mig_util = mig_pid_info['mig_util']
                            mig_mem_util = mig_pid_info['mig_mem_util']
                            mig_dev_id = mig_pid_info['mig_dev_id']
                            gi_id, ci_id = mig_pid_info['gi_ci_id'].split('/')
                            plugin_data.add_perf_data(
                                f"job_{sche.id}_gpu{g.index}_{mig_dev_id}_"
                                f"{gi_id}_{ci_id}_util={mig_util}%"
                            )
                            plugin_data.add_perf_data(
                                f"job_{sche.id}_gpu{g.index}_{mig_dev_id}_"
                                f"{gi_id}_{ci_id}_mem_usage={mig_mem_util}%"
                            )
    except Exception as e:
        if verbose:
            raise e


def compile(value):
    return re.compile(r"<{0}>([\s\S]*?)</{0}>".format(value))


def get_gpu_detail_info(verbose):
    mig_cmd = ['nvidia-smi', '-q', '-x']
    raw_out, err, ret = command_call(mig_cmd)
    if err and verbose:
        print(
            "Get GPU detail failed: {0},"
            "Command is: {1}".format(err, ' '.join(mig_cmd))
        )
    return raw_out, err, ret


def _get_mig_info(verbose):
    gpu_sm_total = dict()
    gpu_mig_dict = defaultdict(lambda: defaultdict(dict))
    raw_out, err, ret = get_gpu_detail_info(verbose)
    if err:
        return gpu_mig_dict
    out = raw_out.decode().strip()
    gpu_pattern = re.compile(r"<gpu id=.*>([\s\S]*?)</gpu>")
    for gpu_info in gpu_pattern.findall(out):
        if not gpu_info.strip():
            continue
        current_mig = compile('current_mig').search(gpu_info)
        if current_mig.group(1).strip().lower() != 'enabled':
            continue
        gpu_index = compile('minor_number').search(gpu_info).group(1)
        gpu_sm_total[gpu_index] = 0
        pid_res = _get_pid_resource(gpu_info)
        mig_info = _get_mig_device(gpu_info)
        for _, v in mig_info.items():
            gpu_sm_total[gpu_index] += v["sm"]
        if not pid_res or not mig_info:
            continue
        for type, res in pid_res.items():
            for pid, used_mem in res.items():
                if type in mig_info:
                    total_sm = mig_info[type]['sm']
                    used_sm = mig_info[type]['sm']
                    sm_util = round(used_sm * 100 / total_sm)
                    mem_util = round(int(used_mem) * 100 / int(
                        mig_info[type]['total_memory']))
                    mig_dev_id = mig_info[type]['mig_dev_id']
                    gpu_mig_dict[gpu_index][pid] = {
                        'gi_ci_id': type,
                        'mig_util': sm_util,
                        'mig_mem_util': mem_util,
                        'mig_dev_id': mig_dev_id,
                        'mig_total_sm': total_sm
                    }
    """
    gpu_mig_dict for example:
    {
        '0': { # gpu index
            '3568728': { # pid
                'gi_ci_id': '2/0',
                'mig_util': 10.5,   # unit: %
                'mig_memory_util': 30.1  # unit: %
                'mig_total_sm': 14  # sm counts of this mig instance
            },
        }
        ...
    }
    """
    return gpu_mig_dict, gpu_sm_total


def _get_mig_device(gpu_info):
    mig_dev_info = defaultdict(dict)
    mig_devices = compile('mig_device').findall(gpu_info)
    for mig_info in mig_devices:
        if not compile('shared').search(mig_info):
            continue
        fb_memory_usage = compile('fb_memory_usage').search(mig_info)
        if not fb_memory_usage:
            continue
        total_mem = compile('total').search(
            fb_memory_usage.group(1)
        ).group(1)
        mig_dev_id = compile('index').search(mig_info).group(1)
        gi_id = compile('gpu_instance_id').search(mig_info).group(1)
        ci_id = compile('compute_instance_id').search(mig_info).group(1)
        sm = compile('multiprocessor_count').search(mig_info).group(1)
        mig_dev_info['{0}/{1}'.format(gi_id, ci_id)]['total_memory'] = \
            convert_unit(total_mem)
        mig_dev_info['{0}/{1}'.format(gi_id, ci_id)]['sm'] = int(sm)
        mig_dev_info['{0}/{1}'.format(gi_id, ci_id)]['mig_dev_id'] = \
            int(mig_dev_id)

    """
    {
        'gi_id/ci_id': {
            'total_memory': 20096, # memory size for mig instance
            'sm': 14, # sm count for mig instance
            'mig_dev_id': 0, # mig dev id for mig instance
        }
    }
    """
    return dict(mig_dev_info)


def _get_pid_resource(gpu_info):
    pid_res_dict = defaultdict(dict)
    for proc_info in compile('process_info').findall(gpu_info):
        pid = compile('pid').search(proc_info)
        if not pid:
            continue
        used_memory = compile('used_memory').search(proc_info)
        if not used_memory:
            continue
        gi_id = compile('gpu_instance_id').search(proc_info).group(1)
        ci_id = compile('compute_instance_id').search(proc_info).group(1)
        pid_res_dict['{0}/{1}'.format(gi_id, ci_id)][pid.group(1)] = \
            convert_unit(used_memory.group(1))
    """
    pid_res_dict for example:
    {
        'gi_id/ci_id': {
            '1171437': 121, # {'pid': 'used_memory'}
        }
    }
    """
    return dict(pid_res_dict)


def _get_gpu_info():
    args = ["nvidia-smi",
            "--query-gpu=index,uuid,memory.total,utilization.gpu",
            "--format=csv,noheader,nounits"]
    out, err, ret = command_call(args)

    args = ["nvidia-smi", "--query-compute-apps=gpu_uuid,pid,used_memory",
            "--format=csv,noheader,nounits"]
    out1, err1, ret1 = command_call(args)

    if ret or ret1 or not out1:
        return {}, {}

    gpu_uuid_index_mapping = dict()

    gp_dict = {}  # all gpu info
    for gp in out.decode().strip().split('\n'):
        gp_info = GPUInfo()
        index, g_uuid, vram, used = gp.split(', ')
        gp_info.index = index
        gp_info.uuid = g_uuid
        gp_info.used = used
        gp_info.vram = int(vram)
        gp_dict[g_uuid] = gp_info

        gpu_uuid_index_mapping[gp_info.uuid] = gp_info.index

    # key: process id
    # value: tuple value for a process all used
    gp_mem_dict = defaultdict(list)

    for gp_mem in out1.decode().strip().split('\n'):
        g_uuid, g_pid, vram_used = gp_mem.split(', ')
        if g_uuid in gp_dict:
            gp_mem_dict[g_pid].append((g_uuid, vram_used))

    return gp_dict, gp_mem_dict


def _get_gpu_running_pids(sche, gp_dict, gp_mem_dict):
    index_pids = defaultdict(list)
    for pid, vram_tuple_list in gp_mem_dict.items():
        if int(pid) in sche.process.keys():
            for g in vram_tuple_list:
                sche.gpu[g[0]] = gp_dict[g[0]]
                sche.gpu_vram[g[0]] += int(g[1])
                index_pids[gp_dict[g[0]].index].append(pid)
    return index_pids
