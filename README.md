# OpenLiCO Monitor

The OpenLiCO monitor offers a package of several Python-based check plugins for icinga. Each plugin is a stand-alone command line tool. Typically, you can run  these check plugins  to determine the current status of hosts and services  on your network.

The check plugins run on:

- Linux - Tested on RHEL 8, Rocky Linux 8, SLES 15, Ubuntu Server 22

All the plugins are written in Python and licensed under Apache 2.0.

## Running the OpenLiCO Monitor Check Plugins

### Requirements

Install Python3 (>=3.6) on the remote host.

### Installation

#### Prerequisite

The package need to build before installation, and it requires some build components installed on build host.

- Golang

  Golang is used to build the program (`lico_set_cap`) which could provide privilege for the check plugins. Please refer to [Go Installation](https://go.dev/doc/install) to install Golang.

- Docker

  Docker is used to build the compile environment for the check plugins. Please refer to [Install Docker Engine](https://docs.docker.com/engine/install/) to install Docker.

Get the OpenLiCO Monitor from our Git repository to your local machine or deployment host.

```shell
git clone git@github.com:lenovo/openlico-monitor.git
```

Building the OpenLiCO Monitor packages.

```shell
make
```

Installing the OpenLiCO Monitor packages. You need to specify the installation path, and in an entire cluster, the installation path should be the same, you can install it in the default nagios plugin or under a shared directory (recommended).

```shell
# The default installation path is /opt/lico/pub/monitor.
python3 install.py
```

Tipp

> If you want to change the installation path, please run `python3 install.py --help`.

After that, you run the check plugins, for example:

```shell
# Get CPU load and utilization
python3 /opt/lico/pub/monitor/lib64/python3.6/site-packages/lico/monitor/plugins/icinga/base/cpu/lico_check_cpu.py --load --util
```

**Caution**

 Some check plugins require privilege to run, in this package, we provide a tool which could grant the plugins some super capability to run, and the example as below:

```shell
# Get the node power consumption, and it need root permission.
/opt/lico/pub/monitor/bin/lico_set_cap /opt/lico/pub/monitor/bin/python outband.power.lico_check_power --power
```

Tipp

> If you want to know more about the tool `lico_set_cap`, please run `/opt/lico/pub/monitor/venv/bin/lico_set_cap -h`


