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


import os
from glob import glob
from subprocess import check_call

from Cython.Distutils import build_ext as _build_ext
from setuptools import Extension, setup


class build_ext(_build_ext):

    def initialize_options(self):
        super().initialize_options()
        self.binsrc = f'bin{os.sep}*.go'

    def _compile(self, workspace, source):
        check_call(
            [
                'go', 'build', source
            ],
            preexec_fn=lambda: os.chdir(workspace)
        )

    def run(self):
        super().run()
        if os.environ.get('LICO_BUILD_BIN', '1') == '1':
            for src in glob(self.binsrc):
                self._compile(*os.path.split(src))


setup(
    ext_modules=[
        Extension(
            name='lico.monitor.libs._infiniband',
            sources=[
                'src/infiniband.pyx',
            ],
            include_dirs=['include'],
            libraries=['ibumad']
        )
    ],
    cmdclass={
        'build_ext': build_ext
    }
)
