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

from collections import defaultdict

from lico.monitor.plugins.icinga.gpu.lico_check_intel_xpu import XPUMetric


class GPUInfo:
    index = None
    uuid = None
    vram = 0
    # utilization rate
    used = 0


def _get_xpu_device_info():
    try:
        xpu_info = XPUMetric.output
        discovery_list = xpu_info['discovery_command_n_output']
        ps_list = xpu_info['ps_command_n_output']
    except Exception:
        return [], []
    else:
        return discovery_list, ps_list


def _format_gpu_info():
    gpu_uuid_index_mapping = defaultdict()
    gp_dict = defaultdict()  # all gpu info
    gp_mem_dict = defaultdict(list)
    discovery_list, ps_list = _get_xpu_device_info()
    for n in range(len(discovery_list)):
        discovery = discovery_list[n]
        proc_list = ps_list[n]
        memory_used = XPUMetric.xpu_memory_used()[n]['value']
        if "memory_physical_size_byte" in discovery.keys():
            mem = str(int(
                discovery['memory_physical_size_byte']
            )/1024/1024)
        else:
            mem = discovery['memory_physical_size']
        gp_info = GPUInfo()
        index, g_uuid, vram, used = \
            n, \
            discovery['uuid'], \
            mem, \
            XPUMetric.xpu_util()[n]['value']
        gp_info.index = index
        gp_info.uuid = g_uuid
        gp_info.used = used
        gp_info.vram = int(float(vram))
        gp_dict[g_uuid] = gp_info
        gpu_uuid_index_mapping[gp_info.uuid] = gp_info.index
        for proc in proc_list["device_util_by_proc_list"]:
            g_uuid, g_pid, vram_used = g_uuid, \
                                   proc["process_id"], \
                                   memory_used
            if g_uuid in gp_dict:
                gp_mem_dict[g_pid].append((g_uuid, vram_used))
    return gp_dict, gp_mem_dict


def get_gpu_res_by_job(sche_list, plugin_data, verbose):
    try:
        gp_dict, gp_mem_dict = _format_gpu_info()
        for sche in sche_list:
            index_pids = defaultdict(list)
            for pid, vram_tuple_list in gp_mem_dict.items():
                if int(pid) in sche.process.keys():
                    for g in vram_tuple_list:
                        sche.gpu[g[0]] = gp_dict[g[0]]
                        sche.gpu_vram[g[0]] = int(g[1])
                        # For XPU: use '=' instead '+=',because xpu not
                        # provides the mem used of pid.
                        index_pids[gp_dict[g[0]].index].append(pid)
            for g in sche.gpu.values():
                util = g.used
                plugin_data.add_output_data(
                    f"Job {sche.id} Usage on GPU Device gpu{g.index}"
                )
                for pid in index_pids[g.index]:
                    plugin_data.add_perf_data(
                        f"job_{sche.id}_gpu{g.index}_util={util}%"
                    )
                plugin_data.add_perf_data(
                    f"job_{sche.id}_gpu{g.index}_mem_usage="
                    f"{round((sche.gpu_vram[g.uuid] / g.vram) * 100, 1)}%"
                )
    except Exception as e:
        if verbose:
            raise e
