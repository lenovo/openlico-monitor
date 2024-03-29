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

CONFIG = scripts/config
PKG_NAME = openlico-monitor

ARCH = $(shell uname -m)

GOLANG_IMAGE = golang:1.20
MANYLINUX_IMAGE = quay.io/pypa/manylinux2014_${ARCH}

VERSION = $(shell cat openlico_monitor.egg-info/PKG-INFO |perl -ne 'print $$1 if /^Version:\s+(.+)/;')
DOCKER_RUN = docker run --env-file ${CONFIG} --rm -v $(PWD):/io

.PHONY: all pkg bin wheel deps clean

all:pkg

bin:bin/lico_set_cap

bin/lico_set_cap:
	${DOCKER_RUN} ${GOLANG_IMAGE} /bin/bash /io/scripts/build_bin.sh

wheel:bin
	${DOCKER_RUN} ${MANYLINUX_IMAGE} /bin/bash /io/scripts/build_wheel.sh

deps:wheel
	${DOCKER_RUN} ${MANYLINUX_IMAGE} /bin/bash /io/scripts/download_deps.sh

pkg:deps
	mkdir -p dist
	tar -czf dist/${PKG_NAME}-${VERSION}.${ARCH}.tgz wheelhouse install.py HISTORY LICENSE README.md

clean:
	rm -rf bin/lico_set_cap wheelhouse build dist *.egg-info
