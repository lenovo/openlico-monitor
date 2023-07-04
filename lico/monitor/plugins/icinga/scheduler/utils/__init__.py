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

from enum import IntEnum
from subprocess import PIPE, Popen  # nosec B404


class UnitEnum(IntEnum):
    B = 0
    KiB = 1
    MiB = 2
    GiB = 3
    TiB = 4


def convert_unit(value, new_unit=UnitEnum.MiB.name):
    size, unit = value.strip().split()
    if unit != new_unit:
        size = 1024 ** (UnitEnum[unit] - UnitEnum[new_unit])
    return size


def command_call(cmd, preexec_fn=None):
    out = ''
    try:
        process = Popen(  # nosec B603
            cmd,
            stderr=PIPE,
            stdout=PIPE,
            preexec_fn=preexec_fn
        )
        out, err = process.communicate()
        ret = process.poll()
    except Exception as e:
        err = str(e)
        ret = -1
    return out, err, ret
