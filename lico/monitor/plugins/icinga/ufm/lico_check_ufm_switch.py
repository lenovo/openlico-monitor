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
import re

import requests

from lico.monitor.plugins.icinga.helper.base import PluginData

# Disable HTTPS certificate warnings
requests.packages.urllib3.disable_warnings()


class ValidateIPAddress(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        # Matches ip_address or ip_address:port
        regexp = (
            r"^(25[0-5]|2[0-4]\d|[0-1]?\d{1,2})\."
            r"(25[0-5]|2[0-4]\d|[0-1]?\d{1,2})\."
            r"(25[0-5]|2[0-4]\d|[0-1]?\d{1,2})\."
            r"(25[0-5]|2[0-4]\d|[0-1]?\d{1,2})(:\d{1,5})?$"
        )
        if not re.match(regexp, values):
            raise argparse.ArgumentTypeError(
                f"{values} is not a valid IP address."
            )
        setattr(namespace, self.dest, values)


def build_url(ip, token, type):
    """
    Returns a URL and headers for making REST API requests

    Args:
        ip (str): The IP address of the target server.
        token (str): The authentication token to be included in the request
        headers.
        type (str): Used to determine the API endpoint. Possible values are:
            - "all_switches": To get all switches information.
            - "telemetry": To get telemetry information.

    Returns:
        tuple: A tuple containing the constructed URL and a dictionary of
        request headers.
    """
    if type == "all_switches":
        endpoint = "ufmRestV3/resources/systems?type=switch"
    if type == "telemetry":
        endpoint = "ufmRestV3/telemetry"

    return f"https://{ip}/{endpoint}", {"Authorization": f"Basic {token}"}


def get_request(url, headers=None, params=None):
    """
    Perform an HTTP GET request and return the JSON response.

    Args:
        url (str): The URL to send the GET request to.
        headers (dict, optional): A dictionary of request headers (default is
        None).
        params (dict, optional): A dictionary of query parameters to include in
        the request (default is None).

    Returns:
        dict: The JSON response obtained from the successful GET request.

    Raises:
        AssertionError: If the GET request fails (status_code is not 200).
    """
    # The 'verify' parameter is set to False to bypass SSL certificate
    # verification
    # Bypass bandit B501:request_with_no_cert_validation
    r = requests.get(
        url,
        headers=headers,
        params=params,
        verify=False,  # nosec B501
        timeout=60,
    )

    r.raise_for_status()  # Raises an exception for non-200 status codes

    return r.json()


def get_all_switches(host_ip, token):
    """
    Fetches information about all switches from the provided host IP and token.

    Args:
        host_ip (str): The IP address of the target UFM server.
        token (str): The authentication token for the UFM API.

    Returns:
        dict: A dictionary containing switch GUIDs as keys and their respective
        ports as values. The format is:
            {switch_guid: [port1, port2, ...]}.
    """
    url_all_switches, headers = build_url(host_ip, token, type="all_switches")

    res = get_request(url_all_switches, headers=headers)

    switches_ports = {elem["system_guid"]: elem["ports"] for elem in res}

    return switches_ports


def get_telemetry(host_ip, token, switches_ports):
    """Fetches telemetry data about all provided switches and ports

    Args:
        host_ip (str): The IP address of the target UFM server.
        token (str): The authentication token for the UFM API.
        switches_ports (dict): A dictionary containing switch GUIDs as keys and
        list of port GUIDs as values.

    Returns:
        dict: A dictionary containing telemetry information about all monitored
        switches and ports.
    """
    url_telemetry, headers = build_url(host_ip, token, type="telemetry")

    metrics = [
        "Infiniband_MBIn",
        "Infiniband_MBOut",
        "Infiniband_PckIn",
        "Infiniband_PckOut",
    ]

    # Request params for switch statistics
    params = {
        "type": "history",
        "membersType": "Device",
        "attributes": f"[{','.join(metrics)}]",
        "members": f"[{','.join(switches_ports.keys())}]",
        "function": "RAW",
        "start_time": "-5min",
        "end_time": "-0min",
    }

    res = get_request(url_telemetry, headers=headers, params=params)
    data = res["data"]

    if not data:
        raise Exception("no telemetry data provided by UFM API")

    # Build final result dict
    telemetry = {}
    for timestamp in data.keys():
        for guid in switches_ports.keys():
            telemetry["time"] = timestamp

            # Switch statistics, guid and name
            information = data[timestamp][params["membersType"]][guid]
            # {
            #   'statistics': {
            #       'metric1': 123,
            #       'metric2': 456,
            #       ...
            #   },
            #   'guid': 'guid1234',
            #   'name': 'switch-lico'
            # }

            # Request params for port statistics
            params["membersType"] = "Port"
            params["members"] = f"[{','.join(switches_ports[guid])}]"

            res_p = get_request(url_telemetry, headers=headers, params=params)

            # Port statistics, guid and name
            port_information = res_p["data"][timestamp][params["membersType"]]

            # Add port information to switch information
            information["ports"] = port_information
            # {
            #   'statistics': {
            #       'metric1': 123,
            #       'metric2': 456,
            #       ...
            #   },
            #   'guid': 'guidswitch1',
            #   'name': 'switch-lico'
            #   'ports': {
            #       'guidport1': {
            #           'statistics': {
            #               'metric1': 123,
            #               'metric2': 456,
            #               ...
            #           },
            #           'guid': 'guidport1',
            #           'name': 'switch-port-1'
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
        "Infiniband_MBIn": "traffic_in",
        "Infiniband_MBOut": "traffic_out",
        "Infiniband_PckIn": "packet_in",
        "Infiniband_PckOut": "packet_out",
    }

    for index, switch in enumerate(metrics["switches"]):
        name = f"switch_{index}_"
        statistics = switch["statistics"]
        p = [
            f"{name}{stat_map[k]}={v}"
            f"{'MB' if k in ['Infiniband_MBIn', 'Infiniband_MBOut'] else ''}"
            for k, v in statistics.items()
        ]
        plugin_data.add_perf_data(" ".join(p))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--host",
        action=ValidateIPAddress,
        help="UFM REST API host IP address",
    )
    parser.add_argument("--token", help="UFM REST API access token")
    args = parser.parse_args()

    switches = get_all_switches(args.host, args.token)

    telemetry = get_telemetry(args.host, args.token, switches)

    plugin_data = PluginData()
    plugin_data.add_output_data(json.dumps(telemetry))

    build_perf_data(plugin_data, telemetry)

    plugin_data.exit()
