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


from libc.stdint cimport uint16_t, uint64_t


cdef extern from "<infiniband/umad.h>":
    enum: UMAD_CA_NAME_LEN
    enum: UMAD_MAX_DEVICES
    enum: UMAD_CA_MAX_PORTS

    enum: SYS_INFINIBAND
    enum: SYS_CA_PORTS_DIR

    ctypedef struct umad_port_t:
        char ca_name[UMAD_CA_NAME_LEN]
        int portnum
        unsigned base_lid
        unsigned lmc
        unsigned sm_lid
        unsigned sm_sl
        unsigned state      # 0:??? 1:Down 2:Initializing 3:Armed 4:Active
        unsigned phys_state # 0:No state change 1:Sleep 2:Polling
                            # 3:Disabled 4:PortConfigurationTraining
                            # 5:LinkUp 6:LinkErrorRecovery 7:PhyTest
        unsigned rate
        uint64_t capmask
        uint64_t gid_prefix
        uint64_t port_guid
        char link_layer[UMAD_CA_NAME_LEN]

    ctypedef struct umad_ca_t:
        char ca_name[UMAD_CA_NAME_LEN]
        unsigned node_type
        int numports
        char fw_ver[20]
        char ca_type[40]
        char hw_ver[20]
        uint64_t node_guid
        uint64_t system_guid
        umad_port_t *ports[UMAD_CA_MAX_PORTS]

    cdef int umad_init()
    cdef int umad_done()

    cdef int umad_get_cas_names(char cas[][UMAD_CA_NAME_LEN], int max)

    cdef int umad_get_ca(char *ca_name, umad_ca_t * ca)
    cdef int umad_release_ca(umad_ca_t * ca)

    cdef int umad_get_port(char *ca_name, int portnum, umad_port_t *port);
    cdef int umad_release_port(umad_port_t *port);
