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

cimport ibumad
from ibumad cimport (
    SYS_CA_PORTS_DIR, SYS_INFINIBAND, UMAD_CA_MAX_PORTS, UMAD_CA_NAME_LEN,
    UMAD_MAX_DEVICES,
)

from functools import lru_cache
from os import path

if ibumad.umad_init() < 0:
    raise ImportError("can't init UMAD library")

class InfinibandUmadError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return f'ibumad api error: {self.message}'

@lru_cache(maxsize=1)
def get_device_list():
    cdef char names[UMAD_MAX_DEVICES][UMAD_CA_NAME_LEN]

    n = ibumad.umad_get_cas_names(names, UMAD_MAX_DEVICES)
    if n < 0:
        raise InfinibandUmadError("can't list IB device names")

    return [InfiniBandDevice(names[i]) for i in range(n)]

cdef generate_port(const ibumad.umad_port_t* port):
    if port is NULL:
        return None
    else:
        return InfiniBandPort(
            ca_name=port[0].ca_name,
            portnum=port[0].portnum,
            base_lid=port[0].base_lid,
            lmc = port[0].lmc,
            sm_lid=port[0].sm_lid,
            sm_sl=port[0].sm_sl,
            state=port[0].state,
            phys_state=port[0].phys_state,
            rate=port[0].rate,
            capmask=port[0].capmask,
            gid_prefix=port[0].gid_prefix,
            port_guid=port[0].port_guid,
            link_layer=port[0].link_layer
        )


class InfiniBandPort:
    def __init__(
        self, ca_name, portnum, base_lid, lmc, sm_lid,
        sm_sl, state, phys_state, rate, capmask, gid_prefix,
        port_guid, link_layer
    ):
        self.ca_name = ca_name
        self.portnum = portnum
        self.base_lid = base_lid
        self.lmc = lmc
        self.sm_lid = sm_lid
        self.sm_sl = sm_sl
        self.state = state
        self.phys_state = phys_state
        self.rate = rate
        self.capmask = capmask
        self.gid_prefix = gid_prefix
        self.port_guid = port_guid
        self.link_layer = link_layer

    @property
    def io_counters(self):
        return InfiniBandPortCounter(self.ca_name, self.portnum)

    def as_dict(self):
        return dict(
            portnum=self.portnum,
            state=self.state,
            phys_state=self.phys_state,
            rate=self.rate,
            base_lid=self.base_lid,
            lmc=self.lmc,
            sm_lid=self.sm_lid,
            capmask='0x{:x}'.format(self.capmask),
            port_guid='0x{:x}'.format(self.port_guid),
            link_layer=self.link_layer,
            io_counters=self.io_counters.as_dict()
        )


class InfiniBandPortCounter:
    def __init__(self, ca_name, portnum):
        counters_path = path.join(
            bytes.decode(<char*>SYS_INFINIBAND), bytes.decode(ca_name),
            bytes.decode(<char*>SYS_CA_PORTS_DIR), str(portnum),
            "counters"
        )
        
        if path.exists(counters_path):
            self._xmit_data = self._gen_counters_data_func(counters_path, 'port_xmit_data', 4)
            self._rcv_data = self._gen_counters_data_func(counters_path, 'port_rcv_data', 4)
            self._xmit_packets = self._gen_counters_data_func(counters_path, 'port_xmit_packets')
            self._rcv_packets = self._gen_counters_data_func(counters_path, 'port_rcv_packets')
        else:
            func = lambda: 0
            self._xmit_data = func
            self._rcv_data = func
            self._xmit_packets = func
            self._rcv_packets = func

    @property
    def xmit_data(self):
        return self._xmit_data()

    @property
    def rcv_data(self):
        return self._rcv_data()

    @property
    def xmit_packets(self):
        return self._xmit_packets()

    @property
    def rcv_packets(self):
        return self._rcv_packets()

    def _gen_counters_data_func(self, counters_path, counter_name, multiplier = 1):            
        full_counter_path = path.join(counters_path, counter_name)
        def func():
            with open(full_counter_path) as f:
                return int(f.read()) * multiplier
        return func

    def as_dict(self):
        return dict(
            xmit_data=self.xmit_data,
            rcv_data=self.rcv_data,
            xmit_packets=self.xmit_packets,
            rcv_packets=self.rcv_packets
        )


cdef class InfiniBandDevice:
    cdef ibumad.umad_ca_t ca

    def __cinit__(self, const char* ca_name):
        if ibumad.umad_get_ca(ca_name, &self.ca) < 0:
            raise InfinibandUmadError(f"can't get IB device {ca_name}")

    def __dealloc__(self):
        ibumad.umad_release_ca(&self.ca)

    @property
    def name(self):
        return self.ca.ca_name

    @property
    def node_type(self):
        return self.ca.node_type

    @property
    def fw_ver(self):
        return self.ca.fw_ver

    @property
    def ca_type(self):
        return self.ca.ca_type

    @property
    def numports(self):
        return self.ca.numports

    @property
    def hw_ver(self):
        return self.ca.hw_ver

    @property
    def node_guid(self):
        return self.ca.node_guid

    @property
    def system_guid(self):
        return self.ca.system_guid

    @property
    def ports(self):
        port_list = (
            generate_port(self.ca.ports[idx])
            for idx in range(<int>UMAD_CA_MAX_PORTS)
        )
        return [
            port for port in port_list
            if port is not None
        ]

    def as_dict(self):
        return dict(
            name=self.name,
            ca_type=self.ca_type,
            numports=self.numports,
            fw_ver=self.fw_ver,
            hw_ver=self.hw_ver,
            node_guid='0x{:x}'.format(self.node_guid),
            system_guid='0x{:x}'.format(self.system_guid),
            ports=[port.as_dict() for port in self.ports]
        )
