#!/usr/local/bin/python3
#
# Copyright (C) 2019 Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from ansible.module_utils.basic import AnsibleModule

import requests
import json

TOKEN_URL = ('http://metadata.google.internal/computeMetadata/v1/'
             'instance/service-accounts/default/token')
GERRIT_URL = 'https://gerrit-review.googlesource.com'


def get_checkers(token):
    url = GERRIT_URL + '/a/plugins/checks/checkers/'
    data = requests.get(url, cookies={'o': token}).text
    return json.loads(data[4:])


def update_checker(token, existing, spec):
    """If the contents of spec differ from existing, update the checker"""
    update = False
    for k, v in spec.items():
        if existing[k] != v:
            update = True
            break
    if update:
        url = GERRIT_URL + '/a/plugins/checks/checkers/' + spec['uuid']
        data = requests.post(url, cookies={'o': token}, json=spec).text
        return json.loads(data[4:])


def create_checker(token, spec):
    """Create a checker as specified"""
    url = GERRIT_URL + '/a/plugins/checks/checkers/'
    data = requests.post(url, cookies={'o': token}, json=spec).text
    return json.loads(data[4:])


def main():
    module = AnsibleModule(
        argument_spec=dict(
            checkers=dict(required=True, type='list'),
        )
    )

    data = requests.get(TOKEN_URL,
                        headers={'Metadata-Flavor': 'Google'}).json()
    token = data['access_token']
    existing_checkers = get_checkers(token)
    existing_checker_map = {c['uuid']:c for c in existing_checkers}

    updated_checkers = []
    for spec in module.params.get('checkers'):
        if not spec.get('uuid'):
            module.fail_json(msg="Checker UUID is required",
                             checker=spec)
        existing = existing_checker_map.get(spec['uuid'])
        if existing:
            updated = update_checker(token, existing, spec)
            if updated:
                updated_checkers.append(updated)
        else:
            updated = create_checker(token, spec)
            if updated:
                updated_checkers.append(updated)

    module.exit_json(changed=(len(updated_checkers) > 0),
                     updated_checkers=updated_checkers,
                     existing_checkers=existing_checkers)


if __name__ == "__main__":
    main()
