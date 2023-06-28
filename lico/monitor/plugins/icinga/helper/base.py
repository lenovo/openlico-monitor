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
from enum import IntEnum
from subprocess import PIPE, Popen


class MetricsBase:
    verbose = False

    @classmethod
    def build_point(cls, metric, value, value_type, unit, output='',
                    state='', index=''):
        return {
            'metric': metric,
            'value': value,
            'type': value_type,
            'units': unit,
            'output': output,
            'state': state,
            'index': index
        }

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


class StateEnum(IntEnum):
    OK = 0
    Warning = 1
    Critical = 2
    Unknown = 3


class PluginData:
    def __init__(self):
        self._output_data = list()
        self._perf_data = list()
        self._state = StateEnum.OK

    def add_output_data(self, data):
        self._output_data.append(data)

    def get_output_data(self, out_list=False):
        if out_list:
            return self._output_data
        else:
            return ', '.join(self._output_data)

    def overwrite_data(self, output_data):
        self._output_data = output_data

    def add_perf_data(self, data):
        self._perf_data.append(data)

    def get_perf_data(self):
        return " ".join(self._perf_data)

    def set_state(self, state: StateEnum):
        if state > self._state:
            self._state = state

    def get_state(self):
        return self._state.name

    def get_plugin_output(self):
        if self._output_data:
            return f"[{self.get_state()}] - " + self.get_output_data() + \
                   " | " + self.get_perf_data()

    def exit(self):
        plugin_output = self.get_plugin_output()
        if plugin_output:
            print(plugin_output)
