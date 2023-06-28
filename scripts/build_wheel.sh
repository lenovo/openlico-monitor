#! /bin/bash

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

set -e

pushd /etc/yum.repos.d
  if [ $CENTOS_REPO ];then
    rm -rf CentOS*.repo
    curl -o centos.repo $CENTOS_REPO
  fi

  rm -rf epel*.repo
popd

yum makecache

yum install -y libibumad-devel

pushd /io
  for pyenv in ${PYTHON_ENVLIST[@]}
  do
    LICO_BUILD_BIN=0 /opt/python/${pyenv}/bin/pip wheel -w dist --no-deps .
    auditwheel repair dist/openlico_monitor*${pyenv}*.whl
    rm dist/openlico_monitor*${pyenv}*.whl
  done
popd
