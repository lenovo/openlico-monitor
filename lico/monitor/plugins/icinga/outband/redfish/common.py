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
import http

import redfish
from attrs import define


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

    def get_service_url(self, service, base_url=None):
        base_url = base_url if base_url is not None else self.base_url
        collection = self.rf_get(f'{base_url}{service}')
        members = collection.get("Members")
        service_urls = []
        for member in members:
            service_urls.append(member.get("@odata.id"))

        return service_urls

    def get_metric_by_identify(self, service_urls, physical_enclosure,
                               model_property, identify: dict, metric):
        metric_data_list = []
        for service_url in service_urls:
            complete_url = service_url + '/' + physical_enclosure
            service_data = self.rf_get(service_url)
            if service_data.get(physical_enclosure):
                data = self.rf_get(complete_url)
                property_data = data.get(model_property)
                metric_data_list += self.parse_property_by_identify(
                    property_data, identify, metric, complete_url)

        return metric_data_list

    def parse_property_by_identify(self, property_data, identify,
                                   metric, metric_url):
        metric_data_list = []
        ident_key, ident_values = self.parse_identify(identify)

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
