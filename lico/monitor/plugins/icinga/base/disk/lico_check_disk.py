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
import os
import re

from lico.monitor.plugins.icinga.helper.base import MetricsBase, PluginData


class DiskMetrics(MetricsBase):
    mounts = '/proc/mounts'

    @classmethod
    def _is_remote_mount(cls, mount, mount_type):
        return re.search(r':', mount) \
               or ('smbfs' == mount_type and '//' == mount[:2]) \
               or mount_type.startswith('nfs') \
               or 'autofs' == mount_type \
               or 'gfs' == mount_type \
               or 'none' == mount_type

    @classmethod
    def _find_disk_space(cls):
        # Unit: GB
        total_size = 0.0
        used_size = 0.0
        if not os.path.exists(cls.mounts) and cls.verbose:
            raise Exception('Get disk space failed, %s does not exist' %
                            cls.mounts)
        with open(cls.mounts, 'r') as f:
            device_set = set()
            for mount in f:
                # Step 1. Filter the disk by the mount path
                if not mount.startswith('/dev/') \
                        and not mount.startswith('/dev2/') \
                        and not mount.startswith('zfs'):
                    continue
                # Step 2. Filter the disk mount by the remote fs
                mount_list = mount.strip().split()
                if cls._is_remote_mount(mount, mount_list[2]):
                    continue

                # Step 3. Filter the mount path with read only mode
                if mount_list[3].startswith('ro'):
                    continue

                if mount_list[0] not in device_set:
                    device_set.add(mount_list[0])
                    m_info = os.statvfs(mount_list[1])
                    total_size += \
                        1.0 * m_info.f_bsize * m_info.f_blocks
                    used_size += \
                        1.0 * m_info.f_bsize * (
                            m_info.f_blocks - m_info.f_bavail)

        return round(total_size, 1), round(used_size, 1)

    @classmethod
    def disk_total(cls):
        lico_disk_total = []
        try:
            total_size, _ = cls._find_disk_space()
            lico_disk_total = [
                cls.build_point('disk_total', total_size, 'float', 'B')
            ]
        except Exception as e:
            cls.print_err(e)
        finally:
            return lico_disk_total

    @classmethod
    def disk_used(cls):
        lico_disk_used = []
        try:
            _, used_size = cls._find_disk_space()
            lico_disk_used = [
                cls.build_point('disk_used', used_size, 'float', 'B')
            ]
        except Exception as e:
            cls.print_err(e)
        finally:
            return lico_disk_used


def disk_total(verbose):
    DiskMetrics.verbose = verbose
    return DiskMetrics.disk_total()


def disk_used(verbose):
    DiskMetrics.verbose = verbose
    return DiskMetrics.disk_used()


def get_disk_total(plugin_data, verbose):
    disk_total_dict = disk_total(verbose)
    if disk_total_dict:
        disk_total_dict = disk_total_dict[0]
        plugin_data.add_output_data("Disk total = {0}{1}".format(
            disk_total_dict['value'], disk_total_dict['units']))
        plugin_data.add_perf_data("{0}={1}{2}".format(
            disk_total_dict['metric'], disk_total_dict['value'],
            disk_total_dict['units']))


def get_disk_used(plugin_data, verbose):
    disk_used_dict = disk_used(verbose)
    if disk_used_dict:
        disk_used_dict = disk_used_dict[0]
        plugin_data.add_output_data("Disk used = {0}{1}".format(
            disk_used_dict['value'], disk_used_dict['units']))
        plugin_data.add_perf_data("{0}={1}{2}".format(disk_used_dict['metric'],
                                                      disk_used_dict['value'],
                                                      disk_used_dict['units']))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', action='store_true', help="""
    Verbose mode;
    """)
    parser.add_argument('--all', action='store_true', help="""
    Get disk capacity and used space;
    """)
    parser.add_argument('--total', action='store_true', help="""
    Get disk capacity;
    """)
    parser.add_argument('--used', action='store_true', help="""
    Get disk used space;
    """)
    args = parser.parse_args()

    plugin_data = PluginData()
    if args.total or args.all:
        get_disk_total(plugin_data, args.verbose)
    if args.used or args.all:
        get_disk_used(plugin_data, args.verbose)
    plugin_data.exit()
