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
SUPPORTED_SCRIPT_EXTENSIONS = ('sh', 'py', 'pl', 'swift', 'rb')
SUPPORTED_EA_EXTENSIONS = ('sh', 'py', 'pl', 'swift', 'rb')
CATEGORIES = []


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


async def upload_extension_attributes(session, url, user, passwd, semaphore):
    mypath = dirname(realpath(__file__))
    if not changed_ext_attrs and not args.update_all:
        print('No Changes in Extension Attributes')
        return
    ext_attrs = [
        f.name for f in os.scandir(join(mypath, 'extension_attributes'))
        if f.is_dir() and f.name in changed_ext_attrs
    ]
    if args.update_all:
        print("Copying all extension attributes...")
        ext_attrs = [
            f.name for f in os.scandir(join(mypath, 'extension_attributes'))
            if f.is_dir()
        ]
    tasks = []
    for ea in ext_attrs:
        task = asyncio.ensure_future(
            upload_extension_attribute(session, url, user, passwd, ea,
                                       semaphore))
        tasks.append(task)
    await asyncio.gather(*tasks)


async def upload_extension_attribute(session, url, user, passwd, ext_attr,
                                     semaphore):
    mypath = dirname(realpath(__file__))
    auth = aiohttp.BasicAuth(user, passwd)
    headers = {'Accept': 'application/xml', 'Content-Type': 'application/xml'}
    # Get the script files within the folder, we'll only use
    # script_file[0] in case there are multiple files
    script_file = [
        f.name for f in os.scandir(join('extension_attributes', ext_attr))
        if f.is_file() and f.name.split('.')[-1] in SUPPORTED_EA_EXTENSIONS
    ]
    if script_file == []:
        print('Warning: No script file found in extension_attributes/%s' %
              ext_attr)
        return  # Need to skip if no script.
    with open(
            join(mypath, 'extension_attributes', ext_attr, script_file[0]),
            'r') as f:
        data = f.read()
    async with semaphore:
        with async_timeout.timeout(args.timeout):
            template = await get_ea_template(session, url, user, passwd,
                                             ext_attr)
            async with session.get(
                    url + '/JSSResource/computerextensionattributes/name/' +
                    template.find('name').text,
                    auth=auth,
                    headers=headers) as resp:
                template.find('input_type/script').text = data
                if args.verbose:
                    print(ET.tostring(template))
                    print('response status initial get: ', resp.status)
                if resp.status == 200:
                    put_url = url + '/JSSResource/computerextensionattributes/name/' + \
                        template.find('name').text
                    resp = await session.put(
                        put_url,
                        auth=auth,
                        data=ET.tostring(template),
                        headers=headers)
                else:
                    post_url = url + '/JSSResource/computerextensionattributes/id/0'
                    resp = await session.post(
                        post_url,
                        auth=auth,
                        data=ET.tostring(template),
                        headers=headers)
    if args.verbose:
        print('response status: ', resp.status)
        print('EA: ', ext_attr)
        print('EA Name: ', template.find('name').text)
    if resp.status in (201, 200):
        print('Uploaded Extension Attribute: %s' % template.find('name').text)
    else:
        print('Error uploading script: %s' % template.find('name').text)
        print('Error: %s' % resp.status)
    return resp.status


async def get_ea_template(session, url, user, passwd, ext_attr):
    auth = aiohttp.BasicAuth(user, passwd)
    mypath = dirname(realpath(__file__))
    xml_file = [
        f.name for f in os.scandir(join('extension_attributes', ext_attr))
        if f.is_file() and f.name.split('.')[-1] in 'xml'
    ]
    try:
        with open(
                join(mypath, 'extension_attributes', ext_attr, xml_file[0]),
                'r') as file:
            template = ET.fromstring(file.read())
    except IndexError:
        with async_timeout.timeout(args.timeout):
            headers = {
                'Accept': 'application/xml',
                'Content-Type': 'application/xml'
            }
            async with session.get(
                    url + '/JSSResource/computerextensionattributes/name/' +
                    ext_attr,
                    auth=auth,
                    headers=headers) as resp:
                if resp.status == 200:
                    async with session.get(
                            url +
                            '/JSSResource/computerextensionattributes/name/' +
                            ext_attr,
                            auth=auth,
                            headers=headers) as response:
                        template = ET.fromstring(await response.text())
                else:
                    template = ET.parse(join(mypath,
                                             'templates/ea.xml')).getroot()
    # name is mandatory, so we use the foldername if nothing is set in
    # a template
    if args.verbose:
        print(ET.tostring(template))
    if template.find('category') and template.find(
            'category').text not in CATEGORIES:
        ET.SubElement(template, 'category').text = 'None'
        if args.verbose:
            c = template.find('category').text
            print(
                f'''WARNING: Unable to find category {c} in the JSS,
                  setting to None'''
            )
    if template.find('name') is None:
        ET.SubElement(template, 'name').text = ext_attr
    elif not template.find('name').text or template.find(
            'name').text is None:
        template.find('name').text = ext_attr
    return template


async def upload_scripts(session, url, user, passwd, semaphore):
    mypath = dirname(realpath(__file__))

    if not changed_scripts and not args.update_all:
        print('No Changes in Scripts')
    scripts = [
        f.name for f in os.scandir(join(mypath, 'scripts')) if f.is_dir()
        and f.name in changed_scripts
    ]
    if args.update_all:
        print('Copying all scripts...')
        scripts = [
            f.name for f in os.scandir(join(mypath, 'scripts'))
            if f.is_dir()
        ]

    tasks = []
    for script in scripts:
        task = asyncio.ensure_future(
            upload_script(session, url, user, passwd, script, semaphore))
        tasks.append(task)
    await asyncio.gather(*tasks)


async def upload_script(session, url, user, passwd, script, semaphore):
    mypath = dirname(realpath(__file__))
    auth = aiohttp.BasicAuth(user, passwd)
    headers = {'Accept': 'application/xml', 'Content-Type': 'application/xml'}
    script_file = [
        f.name for f in os.scandir(join('scripts', script))
        if f.is_file() and f.name.split('.')[-1] in SUPPORTED_SCRIPT_EXTENSIONS
    ]
    if script_file == []:
        print('Warning: No script file found in scripts/%s' % script)
        return  # Need to skip if no script.
    with open(join(mypath, 'scripts', script, script_file[0]), 'r') as f:
        data = f.read()
    async with semaphore:
        with async_timeout.timeout(args.timeout):
            template = await get_script_template(session, url, user, passwd,
                                                 script)
            async with session.get(
                    url + '/JSSResource/scripts/name/' +
                    template.find('name').text,
                    auth=auth,
                    headers=headers) as resp:
                template.find('script_contents').text = data
                if resp.status == 200:
                    put_url = url + '/JSSResource/scripts/name/' + \
                        template.find('name').text
                    resp = await session.put(
                        put_url,
                        auth=auth,
                        data=ET.tostring(template),
                        headers=headers)
                else:
                    post_url = url + '/JSSResource/scripts/id/0'
                    resp = await session.post(
                        post_url,
                        auth=auth,
                        data=ET.tostring(template),
                        headers=headers)
    if resp.status in (201, 200):
        print('Uploaded script: %s' % template.find('name').text)
    else:
        print('Error uploading script: %s' % template.find('name').text)
        print('Error: %s' % resp.status)
    return resp.status


async def get_script_template(session, url, user, passwd, script):
    auth = aiohttp.BasicAuth(user, passwd)
    mypath = dirname(realpath(__file__))
    xml_file = [
        f.name for f in os.scandir(join('scripts', script))
        if f.is_file() and f.name.split('.')[-1] in 'xml'
    ]
    try:
        with open(join(mypath, 'scripts', script, xml_file[0]), 'r') as file:
            template = ET.fromstring(file.read())
    except IndexError:
        with async_timeout.timeout(args.timeout):
            headers = {
                'Accept': 'application/xml',
                'Content-Type': 'application/xml'
            }
            async with session.get(
                    url + '/JSSResource/scripts/name/' + script,
                    auth=auth,
                    headers=headers) as resp:
                if resp.status == 200:
                    async with session.get(
                            url + '/JSSResource/scripts/name/' + script,
                            auth=auth,
                            headers=headers) as response:
                        template = ET.fromstring(await response.text())
                else:
                    template = ET.parse(join(
                        mypath, 'templates/script.xml')).getroot()
    # name is mandatory, so we use the filename if nothing is set in a template
    if args.verbose:
        print(ET.tostring(template))
    if template.find('category') is not None and template.find(
            'category').text not in CATEGORIES:
        c = template.find('category').text
        template.remove(template.find('category'))
        if args.verbose:
            print(
                f'''WARNING: Unable to find category "{c}" in the JSS,
                    setting to None'''
            )
    if template.find('name') is None:
        ET.SubElement(template, 'name').text = script
    elif not template.find('name').text or template.find(
            'name').text is None:
        template.find('name').text = script
    return template


async def get_existing_categories(session, url, user, passwd, semaphore):
    auth = aiohttp.BasicAuth(user, passwd)
    headers = {
        'Accept': 'application/xml',
        'Content-Type': 'application/xml'
    }
    async with semaphore:
        with async_timeout.timeout(args.timeout):
            async with session.get(
                    url + '/JSSResource/categories',
                    auth=auth,
                    headers=headers) as resp:
                if resp.status in (201, 200):
                    return [
                        c.find('name').text for c in [
                            e for e in ET.fromstring(await resp.text()).
                            findall('category')
                        ]
                    ]
    return []


async def main():
    # pylint: disable=global-statement
    global CATEGORIES
    semaphore = asyncio.BoundedSemaphore(args.limit)
    async with aiohttp.ClientSession() as session:
        async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(
                    ssl=args.do_not_verify_ssl)) as session:
            CATEGORIES = await get_existing_categories(
                session, args.url, args.username, args.password, semaphore)
            await upload_scripts(session, args.url, args.username,
                                 args.password, semaphore)
            await upload_extension_attributes(session, args.url, args.username,
                                              args.password, semaphore)


if __name__ == '__main__':
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

    parser = argparse.ArgumentParser(description='Sync repo with JamfPro')
    parser.add_argument('--url')
    parser.add_argument('--username')
    parser.add_argument('--password')
    parser.add_argument('--limit', type=int, default=25)
    parser.add_argument('--timeout', type=int, default=60)
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument('--do_not_verify_ssl', action='store_false')
    parser.add_argument('--update_all', action='store_true')
    parser.add_argument('--jenkins', action='store_true')
    args = parser.parse_args()

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

    loop = asyncio.get_event_loop()

    if args.verbose:
        loop.set_debug(True)
        loop.slow_callback_duration = 0.001
        warnings.simplefilter('always', ResourceWarning)

    loop.run_until_complete(main())
