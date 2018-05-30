#!/usr/bin/env python3.6

import argparse
import asyncio
import async_timeout
import aiohttp
import uvloop

import os
from os.path import dirname, join, realpath
import xml.etree.ElementTree as ET

# The Jenkins file will contain a list of changes scripts and eas in $scripts and $eas. 
# Use this variable to add a Slack emoji in front of each item if you use a post-build action for a Slack custom message
slack_emoji = ":white_check_mark: "

supported_script_extensions = ('sh', 'py', 'pl', 'swift')
supported_ea_extensions = ('sh', 'py', 'pl', 'swift')
supported_profile_extensions = ('.mobileconfig', '.profile')


def check_for_changes():
    """Looks for files that were changed between the current commit and the last commit so we don't upload everything on every run
            --jenkins will utilize $GIT_PREVIOUS_COMMIT and $GIT_COMMIT environmental variables
            --update_all can be invoked to upload all scripts and extension attributes

    """

    # This line will work with the enviromental variables in Jenkins
    if args.jenkins:
        git_changes = os.popen("git diff --name-only $GIT_PREVIOUS_COMMIT $GIT_COMMIT").read().split('\n')

    # Compare the last two commits to determine the list of files that were changed
    else:
        git_commits = os.popen('git log -2 --pretty=oneline --pretty=format:"%h"').read().split('\n')
        command = "git diff --name-only" + " " + git_commits[1] + " " + git_commits[0]
        git_changes = os.popen(command).read().split('\n')
        
        # You could swap this line in if you wanted to look at what has changed in the last 2 days rather than the last two commits. 
        # Change the time to match your needs
        #git_changes = os.popen("git log --no-merges --since='2 days ago' --name-only --oneline").read().split('\n')

    for i in git_changes:
        if 'extension_attributes/' in i and i.split('/')[1] not in changed_ext_attrs:
            changed_ext_attrs.append(i.split('/')[1])


    for i in git_changes:
        if 'scripts/' in i and i.split('/')[1] not in changed_scripts:
            changed_scripts.append(i.split('/')[1])

    return


def write_jenkins_file():
    """Write changed_ext_attrs and changed_scripts to jenkins file. 
    
        $eas will contains the changed extension attributes, 
        $scripts will contains the changed scripts
        
        If there are no changes, the variable will be set to 'None' """

    if len(changed_ext_attrs) == 0:
        contents = "eas=" + "None"
    else:
        contents = "eas=" + slack_emoji + changed_ext_attrs[0] + '\\n' + '\\' 
        for changed_ext_attr in changed_ext_attrs[1:]:
            contents = contents + '\n' + slack_emoji + changed_ext_attr + '\\n' + '\\'
    
    if len(changed_scripts) == 0:
        contents = contents.rstrip('\\') + '\n' + "scripts=" + "None"   
    
    else:
        contents = contents.rstrip('\\') + '\n' + "scripts=" + slack_emoji + changed_scripts[0] + '\\n' + '\\'
        for changed_script in changed_scripts[1:]:
            contents = contents + '\n' + slack_emoji + changed_script + '\\n' + '\\'
        
    with open('jenkins.properties', 'w') as f:
        f.write(contents)


async def upload_profiles(session):
    pass


async def upload_extension_attributes(session, url, user, passwd, semaphore):
    mypath = dirname(realpath(__file__))

    if len(changed_ext_attrs) == 0:
        print('No Changes in Extension Attributes')
        return

    if args.update_all:
        ext_attrs = [f.name for f in os.scandir(join(mypath, 'extension_attributes'))
                if f.is_dir() and f.name is not 'templates']

    else:
        ext_attrs = [f.name for f in os.scandir(join(mypath, 'extension_attributes'))
                if f.is_dir() and f.name is not 'templates' and f.name in changed_ext_attrs]
    tasks = []
    for ea in ext_attrs:
        task = asyncio.ensure_future(upload_extension_attribute(session, url, user, passwd, ea, semaphore))
        tasks.append(task)
    responses = await asyncio.gather(*tasks)


async def upload_extension_attribute(session, url, user, passwd, ext_attr, semaphore):
    mypath = dirname(realpath(__file__))
    auth = aiohttp.BasicAuth(user, passwd)
    headers = {'content-type': 'application/xml'}
    # Get the script files within the folder, we'll only use script_file[0] in case there are multiple files
    script_file = [ f.name for f in os.scandir(join('extension_attributes', ext_attr)) if f.is_file() and f.name.split('.')[-1] in supported_ea_extensions]
    if script_file == []:
        print('Warning: No script file found in extension_attributes/%s' % ext_attr)
        return # Need to skip if no script.
    with open(join(mypath, 'extension_attributes', ext_attr, script_file[0]), 'r') as f:
        data=f.read()
    async with semaphore:
        with async_timeout.timeout(10):
            template = await get_ea_template(session, url, user, passwd, ext_attr)
            async with session.get(url + '/JSSResource/computerextensionattributes/name/' + template.find('name').text,
                    auth=auth) as resp:
                template.find('input_type/script').text = data
                if args.verbose:
                    print(ET.tostring(template))
                    print('response status initial get: ',resp.status)
                if resp.status == 200:
                    put_url = url + '/JSSResource/computerextensionattributes/name/' + template.find('name').text
                    resp = await session.put(put_url, auth=auth, data=ET.tostring(template), headers=headers)
                else:
                    post_url = url + '/JSSResource/computerextensionattributes/id/0'
                    resp = await session.post(post_url, auth=auth, data=ET.tostring(template), headers=headers)
    if args.verbose:
        print('response status: ',resp.status)
        print('EA: ',ext_attr)
        print('EA Name: ',template.find('name').text)
    if resp.status in (201, 200):
        print('Uploaded Extension Attribute: %s' % template.find('name').text)
    return resp.status

async def get_ea_template(session, url, user, passwd, ext_attr):
    auth = aiohttp.BasicAuth(user, passwd)
    mypath = dirname(realpath(__file__))
    xml_file = [ f.name for f in os.scandir(join('extension_attributes', ext_attr)) if f.is_file() and f.name.split('.')[-1] in 'xml' ]
    try:
        with open(join(mypath, 'extension_attributes', ext_attr, xml_file[0]), 'r') as file:
            template = ET.fromstring(file.read())
    except IndexError:
        with async_timeout.timeout(10):
            async with session.get(url + '/JSSResource/computerextensionattributes/name/' + ext_attr,
                    auth=auth) as resp:
                if resp.status == 200:
                    async with session.get(url + '/JSSResource/computerextensionattributes/name/' + ext_attr, auth=auth) as response:
                        template = ET.fromstring(await response.text())
                else:
                    template = ET.parse(join(mypath, 'templates/ea.xml')).getroot()
    # name is mandatory, so we use the foldername if nothing is set in a template
    if args.verbose:
        print(ET.tostring(template))
    if template.find('name') is None:
        ET.SubElement(template, 'name').text = ext_attr
    elif template.find('name').text is '' or template.find('name').text is None:
        template.find('name').text = ext_attr
    return template


async def upload_scripts(session, url, user, passwd, semaphore):
    mypath = dirname(realpath(__file__))

    if len(changed_scripts) == 0:
        print('No Changes in Scripts')
        return

    if args.update_all:
        scripts = [f.name for f in os.scandir(join(mypath, 'scripts'))
                if f.is_dir() and f.name is not 'templates']
    else:
        scripts = [f.name for f in os.scandir(join(mypath, 'scripts'))
                if f.is_dir() and f.name is not 'templates'  and f.name in changed_scripts]
    tasks = []
    for script in scripts:
        task = asyncio.ensure_future(upload_script(session, url, user, passwd, script, semaphore))
        tasks.append(task)
    responses = await asyncio.gather(*tasks)


async def upload_script(session, url, user, passwd, script, semaphore):
    mypath = dirname(realpath(__file__))
    auth = aiohttp.BasicAuth(user, passwd)
    headers = {'content-type': 'application/xml'}
    script_file = [ f.name for f in os.scandir(join('scripts', script)) if f.is_file() and f.name.split('.')[-1] in supported_script_extensions]
    if script_file == []:
        print('Warning: No script file found in scripts/%s' % script)
        return # Need to skip if no script.
    with open(join(mypath, 'scripts', script, script_file[0]), 'r') as f:
        data=f.read()
    async with semaphore:
        with async_timeout.timeout(10):
            template = await get_script_template(session, url, user, passwd, script)
            async with session.get(url + '/JSSResource/scripts/name/' + template.find('name').text,
                    auth=auth) as resp:
                template.find('script_contents').text = data
                if resp.status == 200:
                    put_url = url + '/JSSResource/scripts/name/' + template.find('name').text
                    resp = await session.put(put_url, auth=auth, data=ET.tostring(template), headers=headers)
                else:
                    post_url = url + '/JSSResource/scripts/id/0'
                    resp = await session.post(post_url, auth=auth, data=ET.tostring(template), headers=headers)
    if resp.status in (201, 200):
        print('Uploaded script: %s' % template.find('name').text)
    return resp.status


async def get_script_template(session, url, user, passwd, script):
    auth = aiohttp.BasicAuth(user, passwd)
    mypath = dirname(realpath(__file__))
    xml_file = [ f.name for f in os.scandir(join('scripts', script)) if f.is_file() and f.name.split('.')[-1] in 'xml' ]
    try:
        with open(join(mypath, 'scripts', script, xml_file[0]), 'r') as file:
            template = ET.fromstring(file.read())
    except IndexError:
        with async_timeout.timeout(10):
            async with session.get(url + '/JSSResource/scripts/name/' + script,
                    auth=auth) as resp:
                if resp.status == 200:
                    async with session.get(url + '/JSSResource/scripts/name/' + script, auth=auth) as response:
                        template = ET.fromstring(await response.text())
                else:
                    template = ET.parse(join(mypath, 'templates/script.xml')).getroot()
    # name is mandatory, so we use the filename if nothing is set in a template
    if args.verbose:
        print(ET.tostring(template))
    if template.find('name') is None:
        ET.SubElement(template, 'name').text = script
    elif template.find('name').text is '' or template.find('name').text is None:
        template.find('name').text = script
    return template


async def main(args):
    semaphore = asyncio.BoundedSemaphore(args.limit)
    async with aiohttp.ClientSession() as session:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=args.do_not_verify_ssl)) as session:
            await upload_scripts(session, args.url, args.username, args.password, semaphore)
            await upload_extension_attributes(session, args.url, args.username, args.password, semaphore)

if __name__ == '__main__':
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

    parser = argparse.ArgumentParser(description='Sync repo with JamfPro')
    parser.add_argument('--url')
    parser.add_argument('--username')
    parser.add_argument('--password')
    parser.add_argument('--limit', type=int, default=25)
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument('--do_not_verify_ssl', action='store_false')
    parser.add_argument('--update_all', action='store_true')
    parser.add_argument('--jenkins', action='store_true')
    args = parser.parse_args()

    changed_ext_attrs = []
    changed_scripts = []
    check_for_changes()
    print('Changed Extention Attributes: ', changed_ext_attrs)
    print('Changed Scripts: ', changed_scripts)

    if args.jenkins:
        write_jenkins_file()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(args))
