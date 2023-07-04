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
import os
import re
import socket
from collections import defaultdict

import psutil

from lico.monitor.plugins.icinga.helper.base import PluginData
from lico.monitor.plugins.icinga.scheduler.utils.jobinfo import (
    ProcessInfo, get_job_info,
)
from lico.monitor.plugins.icinga.scheduler.utils.schedulerbase import (
    SchedulerBase, SchedulerInfo,
)


class SchedulerJobInfo(SchedulerBase):
    get_running_jobs_cmd = 'bjobs -UF {0} -u all'
    convert_states = {
        'running': '-r',
        'pending': '-p'
    }

    @classmethod
    def init_cmd(cls, states):
        from subprocess import list2cmdline  # nosec B404
        cmd = [
            'bash', '--login', '-c',
            list2cmdline(cls.get_running_jobs_cmd.format(
                cls.convert_states[states]).split())
        ]
        return cmd

    @classmethod
    def build_point(cls, metric, value, value_type, unit):
        return {
            'metric': metric,
            'value': value,
            'type': value_type,
            'units': unit
        }

    @classmethod
    def _init_sche_process(cls, job_pid_group):
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
                    cls.print_err(f'process {str(e).split()[-1]} of job '
                                  f'{sche_id} is not exist')
                    continue
                except ValueError:
                    cls.print_err(f'process of job is {int(pid)},'
                                  f'which causes ValueError')
                    continue
                except Exception as e:
                    cls.print_err(e)
                    # print(e)
                    continue
                p_info = ProcessInfo()
                p_info.s_id = sche_id
                p_info.process = proc
                proc.cpu_percent()  # call once before real called
                sche.process[int(pid)] = p_info

            sche_list.append(sche)
        return sche_list

    @classmethod
    def get_pid_by_job(cls, states='running'):
        job_pid_dict = dict()
        hostname = socket.gethostname()
        job_out, job_err, job_ret = cls.command_call(
            cls.init_cmd(states), lambda: os.seteuid(os.getuid())
        )
        if job_ret or not job_out:
            cls.print_err(job_out + job_err)
            return job_pid_dict
        split_str = "-" * 78
        data = job_out.decode().strip().split(split_str)

        for item in data:
            jobid_pattern = re.compile(r"Job <([^<|^>]+)>,")
            pattern = jobid_pattern.search(item.strip())
            jobid = pattern.groups()[0] if pattern else None

            res_pattern = re.compile(r"Resource usage collected.([^\n]*)")
            pattern = res_pattern.search(item)
            res = pattern.groups()[0] if pattern else ""

            if "HOST" in res:
                res = res.split("HOST:")
                for info in res[1:]:
                    host_pattern = re.compile(r"([^;]+);")
                    pattern = host_pattern.match(info.strip())
                    host = pattern.groups()[0] if pattern else None
                    if host != hostname:
                        continue
                    pids_pattern = re.compile(r"PIDs:([^;]*);")
                    pattern = pids_pattern.search(info)
                    pids = pattern.groups()[0] if pattern else ""
                    pids = pids.strip().split(" ")
                    job_pid_dict[jobid] = pids
            else:
                task_on_host_pattern = re.compile(
                    r"Started\s\d+\sTask\(s\)\son\sHost\(s\)\s([^,]*)", re.I)
                pattern = task_on_host_pattern.search(item.strip())
                if not pattern:
                    continue
                hosts = pattern.groups()[0]
                host_list = re.findall(r"<(\d+\*)?(.+)>", hosts)
                if not host_list or \
                        host_list[0][1].lower() != hostname.lower():
                    continue
                pids_pattern = re.compile("PIDs:[^;]+")
                pids = pids_pattern.findall(res)
                pid_all = []
                for pid in pids:
                    pid_pattern = re.compile(r"\d+")
                    pid_list = pid_pattern.findall(pid)
                    pid_all += pid_list
                job_pid_dict[jobid] = pid_all
        """"
        return example:
        {'3351':[1211,222334,1111],'3352':[1211,222334,1111]}
        """
        return job_pid_dict

    @classmethod
    def get_job_by_pid(cls, pid):
        response = cls.get_pid_by_job()
        for jobid, values in response.items():
            if pid in values:
                return jobid


def get_lsf_job_info(plugin_data, args):
    SchedulerJobInfo.verbose = args.verbose
    get_job_info(SchedulerJobInfo, plugin_data, args)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', action='store_true',
                        help="""
                        Verbose mode;
                        """
                        )
    parser.add_argument('--jobinfo', action='store_true',
                        help="""
                        Get job information for LSF;
                        """
                        )
    args = parser.parse_args()
    plugin_data = PluginData()

    if args.jobinfo:
        get_lsf_job_info(plugin_data, args)
    plugin_data.exit()
