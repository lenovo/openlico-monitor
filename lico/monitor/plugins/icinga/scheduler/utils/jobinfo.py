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

import time
from collections import defaultdict

import psutil

from lico.monitor.plugins.icinga.scheduler.utils.gpu import get_gpu_res_by_job
from lico.monitor.plugins.icinga.scheduler.utils.schedulerbase import (
    SchedulerInfo,
)


class ProcessInfo:
    # scheduler id
    s_id = None
    # object of Process
    process = None
    # CPU usage percentage
    cpu_percent = 0
    # memory usage percentage
    memory_percent = 0
    # gpu_vram_used = []


def get_job_info(scheduler, plugin_data, args):
    job_pid = scheduler.get_pid_by_job()
    sche_list = _init_sche_process(job_pid, args.verbose)
    get_job_used_info(sche_list, plugin_data, args.verbose)
    try:
        get_gpu_res_by_job()(sche_list, plugin_data, args.verbose)
    except Exception as e:
        if args.verbose:
            raise e


def get_job_used_info(sche_list, plugin_data, verbose):
    try:
        time.sleep(0.02)  # wait for cpu_percent compute
        for sche in sche_list:
            cpu_util_sum, memory_used_sum = 0, 0
            for p in sche.process.values():
                with p.process.oneshot():
                    p.cpu_percent = p.process.cpu_percent()
                    p.memory_used = p.process.memory_info().rss
                cpu_util_sum += p.cpu_percent
                memory_used_sum += p.memory_used

            plugin_data.add_output_data(
                f"Job {sche.id} CPU Utilization = {cpu_util_sum}%"
            )
            plugin_data.add_perf_data(
                f"job_{sche.id}_cpu_util={cpu_util_sum}"
            )

            plugin_data.add_output_data(
                f"Used Memory = {memory_used_sum}B"
            )
            plugin_data.add_perf_data(
                f"job_{sche.id}_mem_used={memory_used_sum}B"
            )
    except Exception as e:
        if verbose:
            raise e


def _init_sche_process(job_pid_group, verbose):
    sche_list = []
    for sche_id, pid_list in job_pid_group.items():
        sche = SchedulerInfo(id=sche_id,
                             process=defaultdict(),
                             gpu=defaultdict(),
                             gpu_vram=defaultdict(int))

        for pid in pid_list:
            try:
                proc = psutil.Process(int(pid))
            except psutil.NoSuchProcess as e:
                if verbose:
                    print(f'process {str(e).split()[-1]} of job '
                          f'{sche_id} is not exist')
                continue
            except ValueError:
                if verbose:
                    print(f'process of job is {int(pid)},'
                          f'which causes ValueError')
                continue
            except Exception as e:
                if verbose:
                    print(e)
                continue
            p_info = ProcessInfo()
            p_info.s_id = sche_id
            p_info.process = proc
            proc.cpu_percent()  # call once before real called
            sche.process[int(pid)] = p_info

        sche_list.append(sche)
    return sche_list
