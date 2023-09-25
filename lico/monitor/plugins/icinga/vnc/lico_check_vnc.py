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
import json

import psutil

from lico.monitor.plugins.icinga.helper.base import PluginData, StateEnum


def get_vnc_sessions(vnc_command, plugin_data):
    vnc_processes = (
        process.info
        for process in psutil.process_iter(
            ['pid', 'exe', 'cmdline', 'username']
        )
        if process.info['exe'] in vnc_command
    )
    vnc_dict = dict()
    for p in vnc_processes:
        cmd = p['cmdline']
        port = None

        for index, item in enumerate(cmd):
            if item == '-rfbport':
                port = int(cmd[index + 1])
                break
        vnc_index = int(cmd[1].split(':')[1])

        vnc_dict[vnc_index] = \
            {'pid': p["pid"], 'user': p["username"], 'port': port}
        if vnc_index:
            plugin_data.add_perf_data(f"vnc_session_{vnc_index}=0")
    if vnc_dict:
        plugin_data.add_output_data(json.dumps(vnc_dict))
        plugin_data.set_state(StateEnum.OK)


if __name__ == '__main__':
    vnc_command = ['/usr/bin/Xvnc', '/usr/bin/Xtigervnc']
    plugin_data = PluginData()
    parser = argparse.ArgumentParser()
    parser.add_argument('--vncinfo', action='store_true',
                        help="""
                        Get all VNC sessions information;
                        """
                        )
    args = parser.parse_args()
    if args.vncinfo:
        get_vnc_sessions(
            vnc_command, plugin_data
        )
    plugin_data.exit()
