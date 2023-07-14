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
    def node_power(cls, connection, cmd_args):

        try:
            service_urls = connection.get_service_url(cmd_args.root_service)
            metrics = conn.get_metric_by_identify(
                service_urls, cmd_args.res_type, cmd_args.property,
                cmd_args.identify, cmd_args.metric)
            for metric_data in metrics:
                value = sum(metric_data.metric.values())
            power_value = cls._get_value(value)
        except Exception as e:
            cls.print_err(e)
            return []
        return [cls.build_point(
            'node_power', power_value, 'float', 'W')]


def node_power(conn, args):
    PowerMetric.verbose = args.verbose
    return PowerMetric.node_power(conn, args)


def get_power_info(plugin_data, conn, args):
    node_power_dict = node_power(conn, args)
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


def parse_command_line():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter, add_help=False)

    group = parser.add_argument_group(title="Require Arguments")
    group.add_argument('--host', help="BMC IP address;")
    group.add_argument('--username', help="BMC login user;")
    group.add_argument('--password', help="BMC login password;")

    group = parser.add_argument_group(title="Optional Arguments")
    group.add_argument('--root-service', default='Chassis', help="""
        Resource instances, default is Chassis;
        """)
    group.add_argument('--res_type', default='Power', help="""
        Resource type, default is Power;
        """)
    group.add_argument('--property', default='PowerControl', help="""
        Resource property, default is PowerControl;
        """)
    group.add_argument(
        '--identify', default='Name=Server Power Control',
        help="""
        Resource object identify, default is 'Name=Server Power Control',
        this argument is a comma-separated list.
        For example: 'Name=CPU Sub-system Power,Memory Sub-system Power';
        """)
    group.add_argument('--metric', default='PowerConsumedWatts', help="""
        Resource object metric, default is PowerConsumedWatts;
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
            get_power_info(plugin_data, conn, args)
    except Exception as e:
        if args.verbose:
            print(e)
    finally:
        plugin_data.exit()
