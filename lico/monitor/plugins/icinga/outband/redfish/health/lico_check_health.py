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
import json
from enum import IntEnum

from redfish.rest.v1 import RetriesExhaustedError

from lico.monitor.plugins.icinga.helper.base import MetricsBase, PluginData
from lico.monitor.plugins.icinga.outband.redfish.common import (
    RedfishConnection,
)


class StateEnum(IntEnum):
    OK = 0
    Informational = 1
    Warning = 2
    Critical = 3


class HealthMetric(MetricsBase):
    @classmethod
    def node_health(cls, conn, args):
        """
        return example:
        [OK] - {"badreadings": [{"Id": "2596881", "Message": "Power Supply
        1 has lost input.", "Severity": "Power Supply 1 has lost input.",
        "Name": "LogEntry"}, {"Id": "2596882", "Message": "Non-redundant:
        Sufficient Resources from Redundancy Degraded or Fully Redundant
        for Power Resource has asserted.", "Severity": "Non-redundant:
        Sufficient Resources from Redundancy Degraded or Fully Redundant
        for Power Resource has asserted.", "Name": "LogEntry"}],
        "health": "Warning"} | node_health_critical_count=0
        """
        try:
            critical_count = 0
            summary = {'badreadings': [], 'health': None}
            service_urls = conn.get_service_url(args.res_instance)
            health = StateEnum.OK
            for service_url in service_urls:
                systems_info = conn.rf_get(service_url)
                logservices_path = systems_info.get(
                    "LogServices").get('@odata.id')
                log_path = conn.url_path_join(logservices_path, args.res_type)
                if not cls.check_log_path(logservices_path, log_path):
                    continue
                log_info = conn.rf_get(log_path)
                entries_path = log_info.get(
                    "Entries").get('@odata.id')
                entries_info = conn.rf_get(entries_path)
                count = entries_info.get("Members@odata.count")
                if count > 0:
                    for entries in entries_info.get('Members'):
                        res_dict = {'Id': entries.get('Id'),
                                    'Message': entries.get('Message'),
                                    'Severity': entries.get('Severity'),
                                    'Name': entries.get('Name')}
                        cur_health = entries.get('Severity')
                        health = cls.get_latest_health(health, cur_health)
                        if cur_health == 'Critical':
                            critical_count += 1
                        summary['badreadings'].append(res_dict)
            summary['health'] = health.name
            if not summary['badreadings']:
                return []
        except Exception as e:
            cls.print_err(e)
            return []
        return [cls.build_point("node_health", critical_count,
                                "string", '', summary)]

    @classmethod
    def get_latest_health(cls, health: StateEnum, cur: str):
        level = health
        try:
            cur_health = StateEnum[cur]
            if cur_health > health:
                level = cur_health
        except KeyError as e:
            cls.print_err(e)
        finally:
            return level

    @classmethod
    def check_log_path(cls, logservices_path, log_path):
        logservices_info = conn.rf_get(logservices_path).get('Members')
        logservices_list = \
            [i.get('@odata.id') for i in logservices_info]
        is_matched = False
        for logservices in logservices_list:
            is_matched = conn.url_verify(log_path, logservices)
            if is_matched:
                break
        else:
            cls.print_err(f'Url {log_path} verification failure,'
                          f'please check the parameters entered')
        return is_matched


def node_health(conn, args):
    HealthMetric.verbose = args.verbose
    return HealthMetric.node_health(conn, args)


def get_health_info(plugin_data, conn, args):
    node_health_dict = node_health(conn, args)
    if node_health_dict:
        node_health_dict = node_health_dict[0]
        plugin_data.add_output_data(json.dumps(node_health_dict['output']))
        plugin_data.add_perf_data(
            "node_health_critical_count={}".format(node_health_dict['value']))


def parse_command_line():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter, add_help=False)

    group = parser.add_argument_group(title="require arguments")
    group.add_argument('--host', help="BMC IP address;")
    group.add_argument('--username', help="BMC login user;")
    group.add_argument('--password', help="BMC login password;")

    group = parser.add_argument_group(title="optional arguments")
    group.add_argument('--res_instance', default='Systems', help="""
    resource instances, default is Systems;
    """)
    group.add_argument('--res_type', default='ActiveLog', help="""
    Resource type, default is ActiveLog;
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
            get_health_info(plugin_data, conn, args)
    except RetriesExhaustedError:
        if args.verbose:
            print("The maximum number of attempts has been reached.")
    except Exception as e:
        if args.verbose:
            print(e)
    finally:
        plugin_data.exit()
