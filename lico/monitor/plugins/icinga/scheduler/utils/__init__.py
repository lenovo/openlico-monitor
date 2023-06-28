from enum import IntEnum
from subprocess import PIPE, Popen


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
        process = Popen(
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
