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

import sys
from abc import ABCMeta
from subprocess import PIPE, Popen

import psutil


class SchedulerBase(metaclass=ABCMeta):
    verbose = False

    @classmethod
    def print_err(cls, msg):
        if cls.verbose:
            sys.stderr.write(str(msg))

    @classmethod
    def command_call(cls, cmd, preexec_fn=None):
        out = ''
        try:
            process = Popen(
                cmd,
                stderr=PIPE,
                stdout=PIPE,
                preexec_fn=preexec_fn
            )
            out, err = process.communicate()
            ret = process.poll()
        except Exception as e:
            err = str(e)
            ret = -1
        return out, err, ret

    @classmethod
    def get_child_pids(cls, parent_id, recursive=False):
        pid_all = []
        if psutil.pid_exists(int(parent_id)):
            process_info = psutil.Process(int(parent_id))
            child_object = process_info.children(recursive=recursive)
            pid_all = [str(i.pid) for i in child_object] + [parent_id]
        return pid_all


class SchedulerInfo:
    __slots__ = ['id', 'process', 'gpu', 'gpu_vram']

    def __init__(self, id, process: dict, gpu: dict, gpu_vram: dict):
        # scheduler id
        self.id = id
        # all process of a job
        self.process = process  # defaultdict(ProcessInfo)
        # all gpu of a job
        self.gpu = gpu
        self.gpu_vram = gpu_vram
