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

import argparse
import os
import socket

from lico.monitor.plugins.icinga.helper.base import PluginData
from lico.monitor.plugins.icinga.scheduler.utils.jobinfo import get_job_info
from lico.monitor.plugins.icinga.scheduler.utils.schedulerbase import (
    SchedulerBase,
)


class SchedulerJobInfo(SchedulerBase):
    get_running_jobs_cmd = \
        'squeue -w {0} --states={1} --Format=JOBID --noheader'
    get_job_pids_cmd = ['scontrol', 'listpids']

    @classmethod
    def get_pid_by_job(cls, states='running'):
        job_pid_dict = dict()
        hostname = socket.gethostname()
        job_out, job_err, job_ret = cls.command_call(
            cls.get_running_jobs_cmd.format(hostname, states).split(),
            lambda: os.seteuid(os.getuid())
        )
        if job_ret or not job_out:
            cls.print_err(job_out + job_err)
            return job_pid_dict

        job_ids_list = job_out.decode().strip().split()
        pids_out, pids_err, pids_ret = cls.command_call(
            cls.get_job_pids_cmd,
            lambda: os.seteuid(os.getuid())
        )
        if pids_ret or not pids_out:
            cls.print_err(pids_out + pids_err)
            return job_pid_dict

        pid_job_list = pids_out.decode().strip().split('\n')[1:]
        for pid_str in pid_job_list:
            pid_list = pid_str.strip().split()
            if pid_list[1] not in job_ids_list:
                break
            if pid_list[1] in job_pid_dict:
                job_pid_dict[pid_list[1]].append(pid_list[0])
            else:
                job_pid_dict[pid_list[1]] = [pid_list[0]]
        return job_pid_dict

    @classmethod
    def get_job_by_pid(cls, pid):
        output, err, ret = cls.command_call(
            ['scontrol', 'pidinfo', pid]
        )
        '''
        Slurm job id 84058 ends at Wed Jan 15 13:54:04 2020
        slurm_get_rem_time is 31533115'
        '''
        if ret:
            cls.print_err('Failed to get slurm jobid %s' % err)
            return

        job_info = bytes.decode(output).split()[1]
        if job_info.startswith("JobId"):
            jobid = job_info.split("=")[-1]
        else:
            jobid = bytes.decode(output).split()[3]
        return jobid


def get_slurm_job_info(plugin_data, args):
    SchedulerJobInfo.verbose = args.verbose
    get_job_info(SchedulerJobInfo, plugin_data, args)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', action='store_true', help="""
    Verbose mode;
    """)
    parser.add_argument('--jobinfo', action='store_true', help="""
    Get job information for SLURM;
    """)
    args = parser.parse_args()
    plugin_data = PluginData()
    if args.jobinfo:
        get_slurm_job_info(plugin_data, args)
    plugin_data.exit()
