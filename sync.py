#!/usr/bin/env python
# pylint: disable=missing-docstring,invalid-name
import warnings
import os
from os.path import dirname, join, realpath
import sys
import xml.etree.ElementTree as ET
import getpass
import argparse
import logging
import asyncio
import async_timeout
import aiohttp
import uvloop
import requests
import json


TEMPLATE_ID = 'id'

EA_FOLDER_NAME = 'extension_attributes'

SCRIPTS_FOLDER_NAME = 'scripts'
TEMPLATE_NAME = 'name'
TEMPLATE_CATEGORY = 'category'

logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)7s: %(message)s',
    stream=sys.stderr,
)
LOG = logging.getLogger('')

# The Jenkins file will contain a list of changes scripts and eas
# in $scripts and $eas.
# Use this variable to add a Slack emoji in front of each item if
# you use a post-build action for a Slack custom message
SLACK_EMOJI = ":white_check_mark: "
SUPPORTED_SCRIPT_EXTENSIONS = ['sh', 'py', 'pl', 'swift', 'rb']
SUPPORTED_EA_EXTENSIONS = ['sh', 'py', 'pl', 'swift', 'rb']
CATEGORIES = []
AUTH = None
CLASSIC_HEADERS = {
    'Accept': 'application/xml',
    'Content-Type': 'application/xml'
}


def check_for_changes():
    """Looks for files that were changed between the current commit and
       the last commit so we don't upload everything on every run
         --jenkins will utilize $GIT_PREVIOUS_COMMIT and $GIT_COMMIT
           environmental variables
         --update_all can be invoked to upload all scripts and
           extension attributes
    """
    # This line will work with the environmental variables in Jenkins
    if args.jenkins:
        git_changes = os.popen(
            "git diff --name-only $GIT_PREVIOUS_COMMIT $GIT_COMMIT").read(
        ).split('\n')

    # Compare the last two commits to determine the list of files that
    # were changed
    else:
        git_commits = os.popen(
            'git log -2 --pretty=oneline --pretty=format:"%h"').read().split(
            '\n')
        command = "git diff --name-only" + " " + \
                  git_commits[1] + " " + git_commits[0]
        git_changes = os.popen(command).read().split('\n')

    for i in git_changes:
        if 'extension_attributes/' in i and i.split(
                '/')[1] not in changed_ext_attrs:
            changed_ext_attrs.append(i.split('/')[1])

    for i in git_changes:
        if 'scripts/' in i and i.split('/')[1] not in changed_scripts:
            changed_scripts.append(i.split('/')[1])


def write_jenkins_file():
    """Write changed_ext_attrs and changed_scripts to jenkins file.
        $eas will contains the changed extension attributes,
        $scripts will contains the changed scripts
        If there are no changes, the variable will be set to 'None'
    """

    if not changed_ext_attrs:
        contents = "eas=" + "None"
    else:
        contents = "eas=" + SLACK_EMOJI + changed_ext_attrs[0] + '\\n' + '\\'
        for changed_ext_attr in changed_ext_attrs[1:]:
            contents = contents + '\n' + SLACK_EMOJI + \
                       changed_ext_attr + '\\n' + '\\'

    if not changed_scripts:
        contents = contents.rstrip('\\') + '\n' + "scripts=" + "None"

    else:
        contents = contents.rstrip(
            '\\'
        ) + '\n' + "scripts=" + SLACK_EMOJI + changed_scripts[0] + '\\n' + '\\'
        for changed_script in changed_scripts[1:]:
            contents = contents + '\n' + SLACK_EMOJI + \
                       changed_script + '\\n' + '\\'

    with open('jenkins.properties', 'w') as f:
        f.write(contents)


async def upload_extension_attributes(session, url, semaphore):
    my_path = dirname(realpath(__file__))
    if not changed_ext_attrs and not args.update_all:
        print('No Changes in Extension Attributes')
        return
    ext_attrs = [
        f.name for f in os.scandir(join(my_path, EA_FOLDER_NAME))
        if f.is_dir() and f.name in changed_ext_attrs
    ]
    if args.update_all:
        print("Copying all extension attributes...")
        ext_attrs = [
            f.name for f in os.scandir(join(my_path, EA_FOLDER_NAME))
            if f.is_dir()
        ]
    tasks = []
    for ea in ext_attrs:
        task = asyncio.ensure_future(
            upload_extension_attribute(session, url, ea, semaphore))
        tasks.append(task)
    await asyncio.gather(*tasks)


async def upload_extension_attribute(session, url, ext_attr, semaphore):
    print('uploading ', ext_attr)

    script_file = (EA_FOLDER_NAME, ext_attr)
    if not script_file:
        return

    async with semaphore:
        with async_timeout.timeout(args.timeout):
            template = await get_template(session, url, EA_FOLDER_NAME, ext_attr,
                                          '/JSSResource/computerextensionattributes/name/')
            ea_name = template.find(TEMPLATE_NAME).text
            async with session.get(
                    url + '/JSSResource/computerextensionattributes/name/' + ea_name,
                    auth=AUTH,
                    headers=CLASSIC_HEADERS) as resp:
                template.find('input_type/script').text = script_file
                if args.verbose:
                    print(ET.tostring(template))
                    print('response status initial get: ', resp.status)
                if resp.status == 200:
                    put_url = url + '/JSSResource/computerextensionattributes/name/' + ea_name
                    resp = await session.put(
                        put_url,
                        auth=AUTH,
                        data=ET.tostring(template),
                        headers=CLASSIC_HEADERS)
                else:
                    post_url = url + '/JSSResource/computerextensionattributes/id/0'
                    resp = await session.post(
                        post_url,
                        auth=AUTH,
                        data=ET.tostring(template),
                        headers=CLASSIC_HEADERS)
    if args.verbose:
        print('response status: ', resp.status)
        print('EA: ', ext_attr)
        print('EA Name: ', template.find(TEMPLATE_NAME).text)
    if resp.status in (201, 200):
        print('Uploaded Extension Attribute: %s' % template.find(TEMPLATE_NAME).text)
    else:
        print('Error uploading script: %s' % template.find(TEMPLATE_NAME).text)
        print('Error: %s' % resp.status)
    return resp.status


async def upload_scripts(session, url, semaphore):
    my_path = dirname(realpath(__file__))

    scripts = []
    if changed_scripts and not args.update_all:
        print('No Changes in Scripts')
        scripts = [
            f.name for f in os.scandir(join(my_path, SCRIPTS_FOLDER_NAME)) if f.is_dir() and f.name in changed_scripts
        ]
    if args.update_all:
        print('Copying all scripts...')
        scripts = [
            f.name for f in os.scandir(join(my_path, SCRIPTS_FOLDER_NAME))
            if f.is_dir()
        ]

    tasks = []
    for script in scripts:
        task = asyncio.ensure_future(
            upload_script(session, url, script, semaphore))
        tasks.append(task)

    await asyncio.gather(*tasks)


async def upload_script(session, url: str, script: str, semaphore):
    new_script_contents = file_contents(SCRIPTS_FOLDER_NAME, script, SUPPORTED_SCRIPT_EXTENSIONS)
    if not new_script_contents:
        return

    async with semaphore:
        with async_timeout.timeout(args.timeout):
            template = await get_template(session, url, SCRIPTS_FOLDER_NAME, script, '/JSSResource/scripts/name')

            script_id = template.find(TEMPLATE_ID).text
            script_name = template.find(TEMPLATE_NAME).text

            resp = await session.get(
                url + '/uapi/v1/scripts/' + script_id,
                headers=HEADERS)

            if resp.status != 200:
                print("Error obtaining existing script: " + script_name)
                return resp.status

            script_to_put = await resp.json()
            script_to_put['scriptContents'] = new_script_contents

            resp = await session.put(
                url + '/uapi/v1/scripts/' + script_id,
                data=json.dumps(script_to_put),
                headers=HEADERS)

            if resp.status in (400, 404, 415):
                resp = await session.post(
                    url + '/uapi/v1/scripts',
                    data=script_to_put,
                    headers=HEADERS)

            if resp.status in (201, 200):
                print('Uploaded script: %s' % script_name)
            else:
                print('Error uploading script: %s' % script_name)
                print('Error: %s' % resp.status)

    return resp.status


async def get_template(session, url: str, dir_name: str, file_name: str, endpoint: str):
    try:
        script_content = file_contents(dir_name, file_name, ['xml'])
        template = ET.fromstring(script_content)
    except IndexError:
        with async_timeout.timeout(args.timeout):

            async with session.get(
                    url + endpoint + file_name,
                    auth=AUTH,
                    headers=CLASSIC_HEADERS) as resp:
                if resp.status == 200:
                    template = ET.fromstring(await resp.text())
                else:
                    template = ET.parse(join(dirname(realpath(__file__)), 'templates/script.xml')).getroot()

    # name is mandatory, so we use the filename if nothing is set in a template
    if args.verbose:
        print(ET.tostring(template))

    if template.find(TEMPLATE_CATEGORY) is not None and template.find(TEMPLATE_CATEGORY).text not in CATEGORIES:
        c = template.find(TEMPLATE_CATEGORY).text
        template.remove(template.find(TEMPLATE_CATEGORY))
        if args.verbose:
            print(
                f'''WARNING: Unable to find category "{c}" in the JSS,
                    setting to None''')
    if template.find(TEMPLATE_NAME) is None:
        ET.SubElement(template, TEMPLATE_NAME).text = file_name
    elif not template.find(TEMPLATE_NAME).text or template.find(
            TEMPLATE_NAME).text is None:
        template.find(TEMPLATE_NAME).text = file_name
    return template


async def get_existing_categories(session, url: str, semaphore):
    all_categories = list()
    page = 0
    more_to_find = True
    async with semaphore:
        with async_timeout.timeout(args.timeout):

            while more_to_find:
                async with session.get(
                        url + '/uapi/v1/categories?page=' + str(page),
                        headers=HEADERS) as resp:

                    if resp.status in (200, 201):
                        categories_json = await resp.json()

                        if categories_json['totalCount'] < 100:
                            more_to_find = False

                        all_categories.extend(e[TEMPLATE_NAME] for e in categories_json['results'])
                        page = page + 1
                    else:
                        print('Error retrieving all categories')
                        return all_categories

    return all_categories


async def main():
    semaphore = asyncio.BoundedSemaphore(args.limit)
    async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(
                ssl=args.do_not_verify_ssl)) as session:
        CATEGORIES.extend(await get_existing_categories(
            session, args.url, semaphore))
        await upload_scripts(session, args.url, semaphore)
        await upload_extension_attributes(session, args.url, semaphore)


def file_contents(folder_name: str, file_name: str, extensions: list):
    file = [
        f.name for f in os.scandir(join(folder_name, file_name))
        if f.is_file() and f.name.split('.')[-1] in extensions
    ]

    if not file:
        print('Warning: No contents found for file/%s in dir /%s' % file_name, folder_name)
        return None  # Need to skip if no script.

    my_path = dirname(realpath(__file__))
    with open(join(my_path, folder_name, file_name, file[0]), 'r') as f:
        return f.read()


def configure_auth(arguments) -> (str, dict, str):
    auth = aiohttp.BasicAuth(arguments.username, arguments.password)

    r = requests.post(args.url + "/uapi/auth/tokens", auth=(arguments.username, arguments.password))
    token = ''
    if r.status_code == 200:
        token = r.json()['token']
    else:
        print('Could not authenticate to Jamf Pro with supplied username and password.')
        exit(1)

    headers = {"Authorization": "Bearer " + token,
               "Accept": "application/json",
               "Content-Type": "application/json"}

    return auth, headers, token


if __name__ == '__main__':
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

    parser = argparse.ArgumentParser(description='Sync repo with Jamf Pro')
    parser.add_argument('--url')
    parser.add_argument('--username')
    parser.add_argument('--password')
    parser.add_argument('--limit', type=int, default=5)
    parser.add_argument('--timeout', type=int, default=60)
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument('--do_not_verify_ssl', action='store_false')
    parser.add_argument('--update_all', action='store_true')
    parser.add_argument('--jenkins', action='store_true')
    args = parser.parse_args()

    if args.limit > 25:
        print('limit argument exceeded 25, setting it to 25')
        args.limit = 25

    changed_ext_attrs = []
    changed_scripts = []
    check_for_changes()
    print('Changed Extension Attributes: ', changed_ext_attrs)
    print('Changed Scripts: ', changed_scripts)

    if args.jenkins:
        write_jenkins_file()

    # Ask for password if not supplied via command line args
    if not args.password:
        args.password = getpass.getpass()

    AUTH, HEADERS, TOKEN = configure_auth(args)

    loop = asyncio.get_event_loop()

    if args.verbose:
        loop.set_debug(True)
        loop.slow_callback_duration = 0.001
        warnings.simplefilter('always', ResourceWarning)

    loop.run_until_complete(main())
