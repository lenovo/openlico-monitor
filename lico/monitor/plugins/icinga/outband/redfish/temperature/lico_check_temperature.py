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
            services = conn.sysinfo.get('Links', {}).get(
                args.res_instance)
            service_urls = [serv.get('@odata.id') for serv in services]
            metrics = conn.get_metric_by_identify(
                service_urls, args.res_type, args.property,
                args.identify, args.metric)
            if len(metrics) < 1 and metrics[0].metric.get(args.metric):
                raise Exception("Temperature information not found!")
            temp = metrics[0].metric.get(args.metric)
        except Exception as e:
            cls.print_err(e)
            return []
        return [cls.build_point('node_temp', float(temp), 'float', '')]


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
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', help="BMC IP address;", required=True)
    parser.add_argument('--username', help="BMC login user;", required=True)
    parser.add_argument('--password', help="BMC login password;",
                        required=True)
    parser.add_argument('--sys_url', default=None, help="""
    Redfish system url, default is None;
    """)
    parser.add_argument('--res_instance', default='Chassis', help="""
    Resource instances, default is Chassis;
    """)
    parser.add_argument('--res_type', default='Thermal', help="""
    Resource type, default is Thermal;
    """)
    parser.add_argument('--property', default='Temperatures', help="""
    Resource property, default is Temperatures;
    """)
    parser.add_argument('--identify', default='Name=Ambient Temp', help="""
    Resource object identify, default is 'Name=Ambient Temp';
    """)
    parser.add_argument('--metric', default='ReadingCelsius', help="""
    Resource object metric, default is ReadingCelsius;
    """)
    parser.add_argument('--timeout', default=5, type=int, help="""
    Timeout in seconds, default is 5s;
    """)
    parser.add_argument('--max_attempt', default=1, type=int, help="""
    Max attempt times, default is 1;
    """)
    parser.add_argument('--verbose', action='store_true', help="""
    Verbose mode;
    """)
    result = parser.parse_args()
    return result


if __name__ == '__main__':
    args = parse_command_line()
    plugin_data = PluginData()

    try:
        with RedfishConnection(args) as conn:
            get_temperature_info(plugin_data, conn, args)
    except Exception as e:
        if args.verbose:
            raise e
    finally:
        plugin_data.exit()
