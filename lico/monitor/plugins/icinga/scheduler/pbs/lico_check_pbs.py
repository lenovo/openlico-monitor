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
    get_running_jobs_cmd = "printjob -a {0} | grep -E 'parentjob|sid'"
    job_id_cmd = ['qstat', '-rftn']

    @classmethod
    def init_cmd(cls, origin_cmd):
        from subprocess import list2cmdline  # nosec B404
        cmd = [
            'bash', '--login', '-c',
            list2cmdline(origin_cmd)
        ]
        return cmd

    def _init_sche_process(self, job_pid_group):
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
                    self.print_err(
                        f'process {str(e).split()[-1]} of job '
                        f'{sche_id} is not exist'
                    )
                    continue
                p_info = ProcessInfo()
                p_info.s_id = sche_id
                p_info.process = proc
                proc.cpu_percent()  # call once before real called
                sche.process[int(pid)] = p_info
            sche_list.append(sche)
        return sche_list

    @classmethod
    def get_pid_by_job(cls):
        job_pid_dict = defaultdict(list)
        hostname = socket.gethostname()

        jobid_out, jobid_err, jobid_ret = cls.command_call(
            cls.init_cmd(cls.job_id_cmd),
            lambda: os.seteuid(os.getuid())
        )
        if jobid_ret or not jobid_out:
            cls.print_err(jobid_out + jobid_err)
            return job_pid_dict

        server_object = re.search(r'-----\n(.*?) ',
                                  jobid_out.decode('utf-8')).group(1)
        server_name = '.' + server_object.split('.')[-1]  # .c1
        # Get the jobid of the current node
        job_id = []
        job_object = cls.get_job_object(jobid_out)
        # job_object:{'3113': ['c2', 'c1'], '3115': ['c1']}
        for key, value in job_object.items():
            if hostname in value:
                job_id.append(key)

        pattern_job_sid = re.compile(
            f'\tparentjobid:\t(.*?){server_name}\n\tsid:\t\t(.*?)\n')

        # get sid of all job
        job_out, job_err, job_ret = cls.command_call(
            cls.init_cmd(
                cls.get_running_jobs_cmd.format(' '.join([
                    i for i in job_id])).split()),
            lambda: os.setuid(0)
        )
        if job_ret or not job_out:
            cls.print_err(job_out + job_err)
            return job_pid_dict

        # format of job_sid_group like [(job_id, job_sid),]
        job_sid_group = re.findall(pattern_job_sid, job_out.decode('utf-8'))
        for job_id, job_sid in job_sid_group:
            if '-' not in job_sid:
                job_pid_all = cls.get_child_pids(job_sid, True)
                job_pid_dict[job_id] += job_pid_all
        for job_id, pids in job_pid_dict.items():
            job_pid_dict[job_id] = list(set(job_pid_dict[job_id]))
        """"
        return example:
        {'3351':[1211,222334,1111],'3352':[1211,222334,1111]}
        """
        return job_pid_dict

    @staticmethod
    def get_job_object(jobid_out):
        job_object = dict()
        pattern_jobid = re.compile(r'([\d]+)\.')
        pattern_jobid_arr = re.compile(r'([\d]+\[[\d]+\])\.')
        content_object = jobid_out.decode('utf-8').split('\n')

        for index, value in enumerate(content_object):
            job_id = pattern_jobid.findall(value)
            job_id_arr = pattern_jobid_arr.findall(value)
            if job_id:
                host_obect = content_object[index + 1].strip().split('+')
                host_list = set([i.split('/')[0] for i in host_obect])
                job_object[job_id[0]] = list(host_list)
                # host_list:['c2', 'c1']
            elif job_id_arr:
                host_obect = content_object[index + 1].strip().split('+')
                host_list = set([i.split('/')[0] for i in host_obect])
                job_object[job_id_arr[0]] = list(host_list)
        return job_object

    def get_job_by_pid(self, pid):
        response = self.get_pid_by_job()
        for jobid, values in response.items():
            if int(pid) in values:
                return jobid


def get_pbs_job_info(plugin_data, args):
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
                        Get job information for PBS;
                        """
                        )
    args = parser.parse_args()
    plugin_data = PluginData()

    if args.jobinfo:
        get_pbs_job_info(plugin_data, args)
    plugin_data.exit()
