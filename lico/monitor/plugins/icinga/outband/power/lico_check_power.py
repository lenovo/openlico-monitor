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
import re

from pyghmi.ipmi.command import Command

from lico.monitor.plugins.icinga.helper.base import MetricsBase, PluginData


class PowerMetric(MetricsBase):
    @classmethod
    def _get_value(cls, value):
        try:
            return float(value)
        except ValueError:
            return 0.0
        except TypeError:
            return 0.0

    @classmethod
    def node_power(cls):
        power = 0.0
        pattern = re.compile(r'PSU\d+_PIN')
        try:
            for data_dict in Command().get_sensor_data():
                if data_dict.name == 'Sys Power':
                    power = cls._get_value(data_dict.value)
                    break
                elif data_dict.name == 'Avg Power':
                    power = cls._get_value(data_dict.value)
                    break
                elif data_dict.name == 'Total_Power':
                    power = cls._get_value(data_dict.value)
                    break
                elif pattern.match(data_dict.name):
                    power += cls._get_value(data_dict.value)
        except Exception as e:
            cls.print_err(e)
            return []
        return [cls.build_point('node_power', power, 'float', 'W')]


def node_power(verbose):
    PowerMetric.verbose = verbose
    return PowerMetric.node_power()


def get_power_info(plugin_data, verbose):
    node_power_dict = node_power(verbose)
    if node_power_dict:
        node_power_dict = node_power_dict[0]
        plugin_data.add_output_data(
            "Power = {}{}".format(
                node_power_dict['value'],
                node_power_dict['units']
            )
        )
        plugin_data.add_perf_data(
            "{}={}{}".format(
                node_power_dict['metric'],
                node_power_dict['value'],
                node_power_dict['units']
            )
        )


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', action='store_true', help="""
    Verbose mode;
    """)
    parser.add_argument('--power', action='store_true', help="""
    Get the power state of the node;
    """)
    args = parser.parse_args()
    plugin_data = PluginData()

    if args.power:
        get_power_info(plugin_data, args.verbose)
    plugin_data.exit()
