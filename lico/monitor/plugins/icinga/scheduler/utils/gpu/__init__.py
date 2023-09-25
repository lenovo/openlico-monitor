#! /usr/bin/python3
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

from importlib import import_module

from lico.monitor.plugins.icinga.scheduler.utils import command_call

CHECK_GPU = {
    "nvidia": ["which", "nvidia-smi"],
    "intel": ["which", "xpumcli"]
}


def get_gpu_res_by_job():
    get_gpu_res_by_job = None
    try:
        for k, v in CHECK_GPU.items():
            out, err, ret = command_call(v)
            if ret == 0:
                get_gpu_res_by_job = import_module(
                    "lico.monitor.plugins.icinga.scheduler.utils.gpu." + k
                ).get_gpu_res_by_job
                break
    except Exception as e:
        raise e
    return get_gpu_res_by_job
