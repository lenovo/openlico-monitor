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


def start_monitoring_session(host_ip, token, switches_ports):
    """Creates a UFM monitoring session and returns the session id

    Args:
        host_ip (str): The IP address of the target UFM server.
        token (str): The authentication token for the UFM API.
        switches_ports (dict): A dictionary containing switch GUIDs as keys and
        list of port GUIDs as values.

    Returns:
        dict: A dictionary with a single key value pair

        { 'session_id': the id of the created monitoring session }
    """
    ufm_req = common.UfmRequest(
        host_ip, token, request_type="monitoring_start"
    )

    metrics = [
        "Infiniband_MBIn",
        "Infiniband_MBOut",
        "Infiniband_PckIn",
        "Infiniband_PckOut",
    ]
    objects = ["Grid.default." + s for s in switches_ports.keys()]

    # Request data for monitoring session start
    data = {
        "scope_object": "Device",
        "monitor_object": "Device",
        "attributes": metrics,
        "objects": objects,
        "functions": ["RAW"],
        "interval": 2,
    }

    res = ufm_req.post(data=data)

    return {"session_id": int(res.headers["Location"].split("/")[-1])}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Creates a UFM monitoring session"
    )
    parser.add_argument(
        "--host",
        action=common.ValidateIPAddress,
        help="UFM REST API host IP address",
    )
    parser.add_argument("--token", help="UFM REST API access token")
    args = parser.parse_args()

    switches = common.get_all_switches(args.host, args.token)

    session_id = start_monitoring_session(args.host, args.token, switches)

    plugin_data = PluginData()
    plugin_data.add_output_data(json.dumps(session_id))
    plugin_data.add_perf_data(f"session_id={session_id['session_id']}")

    plugin_data.exit()
