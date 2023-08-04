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
import abc
import http
import logging
from tempfile import NamedTemporaryFile
from typing import List, Tuple

import redfish
from attrs import define


class VendorGeneric(abc.ABCMeta):
    name = "Generic"

    health = dict()
    power = dict()
    temperature = dict()


class VendorLenovo(VendorGeneric):
    name = "Lenovo"

    health = {
        "uri": "/redfish/v1/Systems/1/LogServices/ActiveLog/Entries/",
        "sensor_key": "MessageArgs"
    }
    power = {
        "uri": "/redfish/v1/Chassis/1/Power/",
        "property": "PowerControl",
        "identify": {
            "key": "Name",
            "values": ["Server Power Control", ]
        },
        "metric": "PowerConsumedWatts"
    }
    temperature = {
        "uri": "/redfish/v1/Chassis/1/Thermal/",
        "property": "Temperatures",
        "identify": {
            "key": "Name",
            "values": ["Ambient Temp", ]
        },
        "metric": "ReadingCelsius"
    }


class VendorDell(VendorGeneric):
    name = "Dell"

    health = {
        "uri": "/redfish/v1/Managers"
               "/iDRAC.Embedded.1/LogServices/FaultList/Entries",
        "sensor_key": "MessageArgs"
    }
    power = {
        "uri": "/redfish/v1/Chassis/1/Power/",
        "property": "PowerControl",
        "identify": {
            "key": "Name",
            "values": ["Server Power Control", ]
        },
        "metric": "PowerConsumedWatts"
    }
    temperature = {
        "uri": "/redfish/v1/Chassis/System.Embedded.1/Thermal/",
        "property": "Temperatures",
        "identify": {
            "key": "Name",
            # System Board Exhaust Temp
            "values": ["System Board Inlet Temp", ]
        },
        "metric": "ReadingCelsius"
    }


class VendorHPE(VendorGeneric):
    name = "HPE"

    health = {
        "uri": "/redfish/v1/Systems/1/LogServices/IML/Entries/",
        "sensor_key": "Oem,Hpe,ClassDescription",
    }
    power = {
        "uri": "/redfish/v1/Chassis/1/Power/",
        "property": "PowerControl",
        "identify": {
            "key": "MemberId",
            "values": ["0", ]
        },
        "metric": "PowerConsumedWatts"
    }
    temperature = {
        "uri": "/redfish/v1/Chassis/1/Thermal/",
        "property": "Temperatures",
        "identify": {
            "key": "Name",
            "values": ["01-Inlet Ambient", ]
        },
        "metric": "ReadingCelsius"
    }


@define
class MetricData:
    url: str
    identify: dict
    metric: dict


class RedfishConnection:
    def __init__(self, cli_args):
        self.cli_args = cli_args
        self.init_connection()
        self._get_base_url()

    def init_connection(self):
        self.connection = redfish.redfish_client(
            base_url=f"https://{self.cli_args.host}",
            max_retry=self.cli_args.max_attempt, timeout=self.cli_args.timeout)
        self.connection.login(username=self.cli_args.username,
                              password=self.cli_args.password,
                              auth="session")

    def _get_base_url(self):
        rep = self.rf_get('/redfish')
        base_url = rep.get("v1")
        if base_url is None:
            raise Exception("Only support redfish v1.")
        self.base_url = base_url

    def close(self):
        self.connection.logout()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

    def rf_get(self, rf_url):
        rep = self.connection.get(rf_url, None)
        if rep.status >= http.HTTPStatus.BAD_REQUEST.value:
            self.raise_error(rep.dict, rf_url)
        return rep.dict

    def rf_post(self):
        pass

    @staticmethod
    def raise_error(err_data, rf_url):
        raise Exception(f"{rf_url}: {err_data}")

    @property
    def sysinfo(self):
        overview = self.connection.get(self.base_url).dict
        if 'Systems' not in overview:
            raise Exception('Redfish not ready')
        systems = overview['Systems']['@odata.id']
        systems = self.connection.get(systems).dict.get("Members", [])
        if self.cli_args.sys_url:
            for system in systems:
                if system['@odata.id'] == self.cli_args.sys_url:
                    self.sysurl = self.cli_args.sys_url
                    break
            else:
                raise Exception(
                    'Specified sysurl not found: {0}'.format(
                        self.cli_args.sys_url))
        else:
            if len(systems) != 1:
                raise Exception(
                    'Multi system manager, sysurl is required parameter')
            self.sysurl = systems[0]['@odata.id']
        return self.connection.get(self.sysurl).dict

    def get_service_url(self, service, base_url=None):
        base_url = base_url if base_url is not None else self.base_url
        collection = self.rf_get(f'{base_url}{service}')
        members = collection.get("Members")
        service_urls = []
        for member in members:
            service_urls.append(member.get("@odata.id"))

        return service_urls

    def get_metric_by_identify_from_service(
            self, service_urls: List, res_type: str, model_property: str,
            identify: Tuple, metric: str):
        metric_data_list = []
        for service_url in service_urls:
            complete_url = self.url_path_join(service_url, res_type)
            service_data = self.rf_get(service_url)
            if service_data.get(res_type):
                data = self.rf_get(complete_url)
                property_data = data.get(model_property)
                metric_data_list += self.parse_property_by_identify(
                    property_data, identify, metric, complete_url)

        return metric_data_list

    def get_metric_by_identify_from_res(
            self, data_url: str, model_property: str, identify: Tuple,
            metric: str):
        data = self.rf_get(data_url)
        property_data = data.get(model_property)
        metric = self.parse_property_by_identify(
            property_data, identify, metric, data_url)
        return metric

    def parse_property_by_identify(self, property_data: List, identify: Tuple,
                                   metric: str, metric_url: str):
        metric_data_list = []
        ident_key, ident_values = identify
        if isinstance(property_data, list):
            for pro in property_data:
                if isinstance(pro, dict):
                    pro_value = pro.get(ident_key)
                    if pro_value in ident_values:
                        metric_obj = MetricData(
                            url=metric_url,
                            identify={ident_key: pro_value},
                            metric={metric: pro.get(metric)})
                        metric_data_list.append(metric_obj)

        return metric_data_list

    @staticmethod
    def parse_identify(identify):
        identify_list = identify.split('=')
        if len(identify_list) > 1:
            ident_key = identify_list[0]
            ident_values = identify_list[1:]

            return ident_key, ident_values
        return None, []

    @staticmethod
    def url_path_join(*paths):
        return "/".join(
            [path.rstrip(
                "/") if path.endswith("/") else path for path in paths]
        ) + "/"

    @staticmethod
    def url_verify(new_url, old_url):
        return RedfishConnection.url_path_join(
            new_url) == RedfishConnection.url_path_join(
            old_url)


class RedfishLogger:
    def __init__(self, verbose):
        self.verbose = verbose
        self.logfile = None

    def set_logger(self):
        if not self.verbose:
            self.logfile = NamedTemporaryFile()
            loggerformat = \
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            return redfish.redfish_logger(
                self.logfile.name, loggerformat, logging.ERROR)

    def close(self):
        if self.logfile is not None:
            self.logfile.close()
