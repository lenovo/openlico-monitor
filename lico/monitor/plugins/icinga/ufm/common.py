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
import configparser
import json
import re

import requests

# Disable HTTPS certificate warnings
requests.packages.urllib3.disable_warnings()


class ValidateIPAddress(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        # Matches http<s>://ip_address or http<s>://ip_address:port
        regexp = (
            r"^(https?://)?"
            r"(25[0-5]|2[0-4]\d|[0-1]?\d{1,2})\."
            r"(25[0-5]|2[0-4]\d|[0-1]?\d{1,2})\."
            r"(25[0-5]|2[0-4]\d|[0-1]?\d{1,2})\."
            r"(25[0-5]|2[0-4]\d|[0-1]?\d{1,2})(:\d{1,5})?$"
        )
        if not re.match(regexp, values):
            raise argparse.ArgumentTypeError(
                f"{values} is not a valid IP address."
            )
        setattr(namespace, self.dest, values)


class UfmRequest:
    """Represents a HTTP client for making requests to UFM REST API

    Attributes:
        url (str): The constructed URL for the API endpoint.
        headers (dict): The headers for the HTTP requests.
    """

    def __init__(self, base, token, request_type):
        """Initializes a new UfmRequest instance

        Args:
            base (str): The base URL of the target server.
            token (str): The authentication token to be included in the request
            headers.
            request_type (str): Used to determine the API endpoint. Possible
            values are:
                - "all_switches": To get all switches information.
                - "monitoring_snapshot": To get monitoring data.
                - "monitoring_start": To start a new monitoring session.
        """
        self.url = f"{base}/{self._determine_endpoint(request_type)}"
        self.headers = {"Authorization": f"Basic {token}"}

    def _determine_endpoint(self, request_type):
        if request_type == "all_switches":
            endpoint = "ufmRestV3/resources/systems?type=switch"
        if request_type == "monitoring_snapshot":
            endpoint = "ufmRestV3/monitoring/snapshot"
        if request_type == "monitoring_start":
            endpoint = "ufmRestV3/monitoring/start"
        return endpoint

    def get(self, params=None):
        """
        Perform an HTTP GET request and return the JSON response.

        Args:
            params (dict, optional): A dictionary of query parameters to
            include in the request (default is None).

        Returns:
            dict: The JSON response obtained from the successful GET request.

        Raises:
            requests.exceptions.HTTPError: If the GET request fails
            (status_code is not between 200 and 299).
        """
        # The 'verify' parameter is set to False to bypass SSL certificate
        # verification
        # Bypass bandit B501:request_with_no_cert_validation
        r = requests.get(
            self.url,
            headers=self.headers,
            params=params,
            verify=False,  # nosec B501
            timeout=30,
        )

        r.raise_for_status()  # Raises an exception for non-200 status codes
        return r.json()

    def post(self, data):
        """
        Perform an HTTP POST request and return the response according to
        response 'Content-Type'. Performs automatic conversion of request data
        into json object.

        Args:
            data (dict): A dictionary of query data to include in the request.

        Returns:
            dict: The response obtained from the successful POST request. This
            response is json decoded if 'Content-Type' == 'application/json'

        Raises:
            requests.exceptions.HTTPError: If the POST request fails
            (status_code is not between 200 and 299).
        """
        r = requests.post(
            self.url,
            data=json.dumps(data),
            headers=self.headers,
            verify=False,  # nosec B501
            timeout=30,
        )

        r.raise_for_status()

        if r.headers["Content-Type"] == "application/json":
            return r.json()
        return r


def get_all_switches(host, token):
    """
    Fetches information about all switches from the provided host IP and token.

    Args:
        host (str): The base URL of the target UFM server API.
        token (str): The authentication token for the UFM API.

    Returns:
        dict: A dictionary containing switch GUIDs as keys and their respective
        ports as values. The format is:
            {switch_guid: [port1, port2, ...]}.
    """
    ufm_req = UfmRequest(host, token, request_type="all_switches")

    res = ufm_req.get()

    switches_ports = {elem["system_guid"]: elem["ports"] for elem in res}

    return switches_ports


def read_config_file(file_path):
    config = configparser.ConfigParser()
    # Preserve case
    config.optionxform = str
    config.read(file_path)

    try:
        params = dict(config.items("UFM_PLUGIN"))
    except configparser.NoSectionError:
        # Wrong config file, exit gracefully
        host, token = None, None
    else:
        host = params["UFM_HOST"].strip("'")
        token = params["UFM_TOKEN"].strip("'")

    return host, token
