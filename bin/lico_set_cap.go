/*
 * Copyright 2015-2023 Lenovo
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package main

import (
        "fmt"
        "log"
        "os"
        "os/exec"
)

const usage = `
Usage:
    %s python_path module_path [options]

    python_path: Should specify an absolute path for python interpreter.
    module_path: Should specify the module path.
    options: Options for the specified module, refer to the module help.

Example:
    %s /usr/bin/python3 base.cpu.lico_check_cpu --util
`

func main() {
        var args = os.Args
        var prog = args[0]
        if len(args) < 3 {
                fmt.Printf(usage, prog, prog)
                os.Exit(-1)
        }

        opts := []string{"-m", "lico.monitor.plugins.icinga." + args[2]}
        for _, elem := range args[3:] {
                opts = append(opts, elem)
        }

        cmd := exec.Command(args[1], opts...)
        cmd.Stdout = os.Stdout
        cmd.Stderr = os.Stderr

        err := cmd.Run()
        if err != nil {
                log.Fatalf("cmd.Run() failed with %s\n", err)
        }
}
