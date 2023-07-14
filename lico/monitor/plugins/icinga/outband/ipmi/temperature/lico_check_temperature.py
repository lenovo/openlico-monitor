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
import warnings

warnings.filterwarnings('ignore')

import argparse

from pyghmi.ipmi.command import Command

from lico.monitor.plugins.icinga.helper.base import MetricsBase, PluginData


class TempMetric(MetricsBase):
    @classmethod
    def node_temperature(cls):
        try:
            valid_val = None
            for data_dict in Command().get_sensor_data():
                if data_dict.name.lower() == 'ambient temp':
                    valid_val = data_dict.value
                    break
                elif data_dict.name.lower() == 'inlet_temp':
                    valid_val = data_dict.value
                    break
            if valid_val is not None:
                temp = float(valid_val)
            else:
                raise Exception("Unable to get temperature!")
        except Exception as e:
            cls.print_err(e)
            return []
        return [cls.build_point('node_temp', temp, 'float', '')]


def node_temp(verbose):
    TempMetric.verbose = verbose
    return TempMetric.node_temperature()


def get_temperature_info(plugin_data, verbose):
    node_temp_dict = node_temp(verbose)
    if node_temp_dict:
        node_temp_dict = node_temp_dict[0]
        plugin_data.add_output_data(
            "Temperature = {}{}".format(
                node_temp_dict['value'],
                node_temp_dict['units']
            )
        )
        plugin_data.add_perf_data(
            "{}={}{}".format(
                node_temp_dict['metric'],
                node_temp_dict['value'],
                node_temp_dict['units']
            )
        )


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', action='store_true', help="""
    Verbose mode;
    """)
    parser.add_argument('--temperature', action='store_true', help="""
    Get the temperature of the node;
    """)
    args = parser.parse_args()
    plugin_data = PluginData()

    if args.temperature:
        get_temperature_info(plugin_data, args.verbose)
    plugin_data.exit()
