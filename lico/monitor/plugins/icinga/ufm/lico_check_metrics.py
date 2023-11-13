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

from lico.monitor.plugins.icinga.helper.base import PluginData
from lico.monitor.plugins.icinga.ufm import common


def get_telemetry(host, token, switches_ports):
    """Creates a one-time monitoring session and recieves data for all switches
    and ports

    Args:
        host (str): The base URL of the target UFM server API.
        token (str): The authentication token for the UFM API.
        switches_ports (dict): A dictionary containing switch GUIDs as keys and
        list of port GUIDs as values.

    Returns:
        dict: A dictionary containing telemetry information about all monitored
        switches and ports.
    """
    ufm_req = common.UfmRequest(
        host, token, request_type="monitoring_snapshot"
    )

    metrics = [
        "Infiniband_MBInRate",
        "Infiniband_MBOutRate",
        "Infiniband_PckInRate",
        "Infiniband_PckOutRate",
    ]
    objects = ["Grid.default." + s for s in switches_ports.keys()]

    # Request data for monitoring session telemetry
    ddata = {
        "scope_object": "Device",
        # if set to 'Device' will retrieve switch statistics
        # if set to 'Port' will retrieve stats for every port of the switch
        "monitor_object": "Device",
        "attributes": metrics,
        "objects": objects,
        "functions": ["RAW"],
        "interval": 2,
    }

    res = ufm_req.post(data=ddata)

    if not res:
        raise Exception("no telemetry data provided by UFM API")

    # Build final result dict
    telemetry = {}
    for _, device in res.items():
        for guid in switches_ports.keys():
            # Switch statistics, guid and name
            information = device["Device"][guid]
            time = information.pop("last_updated")
            telemetry["time"] = (
                time if "time" not in telemetry else telemetry["time"]
            )
            information["guid"] = guid
            # {
            #   'statistics': {
            #       'metric1': 123,
            #       'metric2': 456,
            #       ...
            #   },
            #   'guid': 'guid1234',
            #   'dname': 'switch-lico'
            # }

            # Request data for port statistics
            ddata["monitor_object"] = "Port"
            ddata["objects"] = [f"Grid.default.{guid}"]

            res_p = ufm_req.post(data=ddata)

            for _, ports in res_p.items():
                # Port statistics, guid and name
                port_information = ports["Port"]
                for port_guid, v in port_information.items():
                    v.pop("last_updated")
                    v["guid"] = port_guid

            # Add port information to switch information
            information["ports"] = port_information
            # {
            #   'statistics': {
            #       'metric1': 123,
            #       'metric2': 456,
            #       ...
            #   },
            #   'guid': 'guidswitch1',
            #   'dname': 'switch-lico'
            #   'ports': {
            #       'guidport1': {
            #           'statistics': {
            #               'metric1': 123,
            #               'metric2': 456,
            #               ...
            #           },
            #           'guid': 'guidport1',
            #           'dname': 'switch-port-1'
            #       },
            #       ...
            #   },
            # }

            telemetry.setdefault("switches", []).append(information)

    return telemetry


def build_perf_data(plugin_data, metrics):
    """Converts metrics returned by telemetry API call into performance data
    which can be parsed by Icinga
    """
    stat_map = {
        "Infiniband_MBInRate": "traffic_in",
        "Infiniband_MBOutRate": "traffic_out",
        "Infiniband_PckInRate": "packet_in",
        "Infiniband_PckOutRate": "packet_out",
    }

    for index, switch in enumerate(metrics["switches"]):
        name = f"ufm_switch_{index}_"
        statistics = switch["statistics"]
        p = [
            f"{name}{stat_map[k]}={v}" f"{'MB' if 'MB' in k else ''}"
            for k, v in statistics.items()
        ]
        plugin_data.add_perf_data(" ".join(p))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Retrieves telemetry data for all switches and ports from \
            UFM REST API"
    )
    parser.add_argument(
        "--host",
        action=common.ValidateIPAddress,
        help="UFM REST API host base URL",
    )
    parser.add_argument("--token", help="UFM REST API access token")
    args = parser.parse_args()

    switches = common.get_all_switches(args.host, args.token)

    telemetry = get_telemetry(args.host, args.token, switches)

    plugin_data = PluginData()
    plugin_data.add_output_data(json.dumps(telemetry))

    build_perf_data(plugin_data, telemetry)

    plugin_data.exit()
