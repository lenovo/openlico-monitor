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

from lico.monitor.plugins.icinga.helper.base import MetricsBase, PluginData
from lico.monitor.plugins.icinga.outband.redfish import common
from lico.monitor.plugins.icinga.outband.redfish.common import (
    RedfishConnection, RedfishLogger,
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
    def node_power(cls, conn, args):

        try:
            if args.data_url:
                metrics = conn.get_metric_by_identify_from_res(
                    args.data_url, args.property, args.identify, args.metric
                )
            else:
                services = conn.sysinfo.get('Links', {}).get(
                    args.res_instance)
                service_urls = [serv.get('@odata.id') for serv in services]

                metrics = conn.get_metric_by_identify_from_service(
                    service_urls, args.res_type, args.property,
                    args.identify, args.metric)

            if len(metrics) < 1 or args.metric not in metrics[0].metric:
                raise Exception("Power information not found!")
            power_value = cls._get_value(metrics[0].metric.get(args.metric))
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
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', help="BMC IP address;", required=True)
    parser.add_argument('--username', help="BMC login user;", required=True)
    parser.add_argument('--password', help="BMC login password;",
                        required=True)
    # positioning uri
    parser.add_argument('--sys_url', default=None, help="""
           Redfish system url, default is None;
           """)
    parser.add_argument('--res_instance', default='Chassis', help="""
        Resource instances, default is Chassis;
        """)
    parser.add_argument('--res_type', default='Power', help="""
        Resource type, default is Power;
        """)
    parser.add_argument('--data_url', default=None, help="""
        Resource uri, default is None.
        If this parameter is specified, the vendor parameter is invalid.
        property, identify, metric need to match this parameter;
        """)
    parser.add_argument('--vendor', choices=['Dell', 'HPE', 'Lenovo'], help="""
        Server vendor.
        If this parameter is specified, property, identify, metric are invalid;
        """)
    # positioning metric
    parser.add_argument('--property', default='PowerControl', help="""
        Resource property, default is PowerControl;
        """)
    parser.add_argument(
        '--identify', default='Name=Server Power Control',
        help="""
        Resource object identify, default is 'Name=Server Power Control',
        this argument is a comma-separated list.
        For example: 'Name=CPU Sub-system Power,Memory Sub-system Power';
        """)
    parser.add_argument('--metric', default='PowerConsumedWatts', help="""
        Resource object metric, default is PowerConsumedWatts;
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
    logger = RedfishLogger(args.verbose)
    plugin_data = PluginData()

    try:
        logger.set_logger()
        with RedfishConnection(args) as conn:
            if args.vendor is not None and args.data_url is None:
                vendor = getattr(common, f"Vendor{args.vendor}")
                args.identify = (
                    vendor.power.get("identify").get("key"),
                    vendor.power.get("identify").get("values")
                )
                args.data_url = vendor.power.get("uri")
                args.property = vendor.power.get("property")
                args.metric = vendor.power.get("metric")
            else:
                args.identify = conn.parse_identify(str(args.identify))

            get_power_info(plugin_data, conn, args)
    except Exception as e:
        if args.verbose:
            raise e
    finally:
        plugin_data.exit()
        logger.close()
