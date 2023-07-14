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
import json

import pyghmi.constants as pygconstants
from pyghmi.ipmi.command import Command

from lico.monitor.plugins.icinga.helper.base import MetricsBase, PluginData


class HealthMetric(MetricsBase):

    @classmethod
    def _str_health(cls, health):
        if isinstance(health, str):
            return health
        if pygconstants.Health.Failed & health:
            health = 'failed'
        elif pygconstants.Health.Critical & health:
            health = 'critical'
        elif pygconstants.Health.Warning & health:
            health = 'warning'
        else:
            health = 'ok'
        return health

    @classmethod
    def node_health(cls):
        try:
            # Example for health_info
            '''
            {
                'badreadings': [
                    {
                        'value': None,
                        'states': [
                            'Event log full',
                            'Event log nearly full'
                        ],
                        'state_ids': [
                            1076996,
                            1076997
                        ],
                        'units': '',
                        'imprecision': None,
                        'name':
                        'SEL Fullness',
                        'type':
                        'Event Log Disabled',
                        'unavailable': 0,
                        'health': 1
                    },
                    {
                        'value': None,
                        'states': [
                            'Present',
                            'Throttled'
                        ],
                        'state_ids': [487175, 487178],
                        'units': '',
                        'imprecision': None,
                        'name': 'CPU 1 Status',
                        'type': 'Processor',
                        'unavailable': 0, 'health': 1
                    },
                    {
                        'value': None,
                        'states': [
                            'Configuration error', 'Present', 'Throttled'
                        ],
                        'state_ids': [487173, 487175, 487178],
                        'units': '',
                        'imprecision': None,
                        'name': 'CPU 2 Status',
                        'type': 'Processor',
                        'unavailable': 0, 'health': 5
                    }
                ],
                'health': 5
            }
            '''
            # The type of the element of badreadings as following:
            # <class 'pyghmi.ipmi.sdr.SensorReading'>
            health_info = Command().get_health()
            if 'health' not in health_info:
                return []
            health_info['health'] = cls._str_health(health_info['health'])
            badreadings = health_info['badreadings']
            critical_count = 0
            for idx, value in enumerate(badreadings):
                sensor_info = value.__dict__
                sensor_info["states"] = ",".join(sensor_info["states"])
                health_str = cls._str_health(sensor_info["health"])
                sensor_info["health"] = health_str
                critical_count += 1 if health_str == "critical" else 0
                badreadings[idx] = sensor_info

        except Exception as e:
            cls.print_err(e)
            return []

        return [cls.build_point(
            "node_health", critical_count, "string", '', health_info)]


def node_health(verbose):
    HealthMetric.verbose = verbose
    return HealthMetric.node_health()


def get_health_info(plugin_data, verbose):
    node_health_dict = node_health(verbose)
    if node_health_dict:
        node_health_dict = node_health_dict[0]
        plugin_data.add_output_data(json.dumps(node_health_dict['output']))
        plugin_data.add_perf_data(
            "node_health_critical_count={}".format(node_health_dict['value']))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', action='store_true', help="""
    Verbose mode;
    """)
    parser.add_argument('--health', action='store_true', help="""
    Get health information of the node;
    """)
    args = parser.parse_args()
    plugin_data = PluginData()
    if args.health:
        get_health_info(plugin_data, args.verbose)
    plugin_data.exit()
