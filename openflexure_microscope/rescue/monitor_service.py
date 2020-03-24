#!/bin/python
#
# Copyright 2016 Flavio Garcia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Usage: monitor_process.py <service_name>
#
# Example(crontab, every 5 minutes):
# */5 * * * * /root/bin/monitor_service.py prosody > /dev/null 2>&1
#

import sys
import subprocess


class ServiceMonitor(object):
    def __init__(self, service):
        self.service = service

    def is_active(self):
        """Return True if service is running"""
        for line in self.status():
            if "Active:" in line:
                if "(running)" in line:
                    return True
        return False

    def status(self):
        cmd = f"/bin/systemctl status {self.service}.service"
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        stdout_list = proc.communicate()[0].decode().split("\n")
        return stdout_list

    def start(self):
        cmd = f"/bin/systemctl start {self.service}.service"
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        proc.communicate()

    def stop(self):
        cmd = f"/bin/systemctl stop {self.service}.service"
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        proc.communicate()

    def log(self, n_lines: int = 100):
        cmd = f"/bin/journalctl -u {self.service}.service -n {n_lines} --no-pager"
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        stdout_list = proc.communicate()[0].decode().split("\n")
        return stdout_list
