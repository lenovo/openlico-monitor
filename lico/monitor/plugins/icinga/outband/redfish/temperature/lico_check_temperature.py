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

from lico.monitor.plugins.icinga.helper.base import MetricsBase, PluginData
from lico.monitor.plugins.icinga.outband.redfish.common import (
    RedfishConnection,
)


class TempMetric(MetricsBase):
    @classmethod
    def node_temperature(cls, conn, args):
        try:
            service_urls = conn.get_service_url(args.root_service)
            metrics = conn.get_metric_by_identify(
                service_urls, args.res_type, args.property,
                args.identify, args.metric)
            if len(metrics) < 1 and metrics[0].metric.get(args.metric):
                raise Exception("Temperature information not found!")
            temp = metrics[0].metric.get(args.metric)
        except Exception as e:
            cls.print_err(e)
            return []
        return [cls.build_point('node_temp', temp, 'float', '')]


def node_temp(conn, args):
    TempMetric.verbose = args.verbose
    return TempMetric.node_temperature(conn, args)


def get_temperature_info(plugin_data, conn, args):
    node_temp_dict = node_temp(conn, args)
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


def parse_command_line():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter, add_help=False)

    group = parser.add_argument_group(title="Require Arguments")
    group.add_argument('--host', help="BMC IP address;")
    group.add_argument('--username', help="BMC login user;")
    group.add_argument('--password', help="BMC login password;")

    group = parser.add_argument_group(title="Optional Arguments")
    group.add_argument('--root_service', default='Chassis', help="""
    Resource instances, default is Chassis;
    """)
    group.add_argument('--res_type', default='Thermal', help="""
    Resource type, default is Thermal;
    """)
    group.add_argument('--property', default='Temperatures', help="""
    Resource property, default is Temperatures;
    """)
    group.add_argument('--identify', default='Name=Ambient Temp', help="""
    Resource object identify, default is 'Name=Ambient Temp';
    """)
    group.add_argument('--metric', default='ReadingCelsius', help="""
    Resource object metric, default is ReadingCelsius;
    """)
    group.add_argument('--timeout', default=5, type=int, help="""
    Timeout in seconds, default is 5s;
    """)
    group.add_argument('--max_attempt', default=1, type=int, help="""
    Max attempt times, default is 1;
    """)
    group.add_argument('--verbose', action='store_true', help="""
    Verbose mode;
    """)
    group.add_argument("-h", "--help", action='store_true',
                       help="show this help message and exit")

    result = parser.parse_args()
    if result.help:
        parser.print_help()
        print("")
        exit(0)

    return result


if __name__ == '__main__':
    args = parse_command_line()
    plugin_data = PluginData()

    try:
        with RedfishConnection(args) as conn:
            get_temperature_info(plugin_data, conn, args)
    except Exception as e:
        if args.verbose:
            print(e)
    finally:
        plugin_data.exit()
