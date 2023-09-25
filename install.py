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
import subprocess
import sys
from os import path

parser = argparse.ArgumentParser()
parser.add_argument(
    '-t', '--target', default='/opt/lico/pub/monitor',
    help='openlico-monitor install path'
)
args = parser.parse_args()

wheeldir = path.join(path.dirname(__file__), 'wheelhouse')
target = args.target

if not path.exists(target):
    subprocess.check_call([
        sys.executable, '-m', 'virtualenv', target,
        '--no-download', f'--extra-search-dir={wheeldir}'
    ])

subprocess.check_call([
    path.join(target, 'bin', 'python'), '-m', 'pip', 'install',
    'openlico-monitor', '--no-index', '-f', wheeldir, '-U'
])

subprocess.check_call([
   'chmod', 'u+s', path.join(target, 'bin', 'lico_set_cap')
])
