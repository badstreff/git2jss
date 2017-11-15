#!/usr/bin/env python

import argparse
import asyncio
import async_timeout
import aiohttp
import uvloop

import os
from os.path import dirname, join, realpath
import xml.etree.ElementTree as ET


supported_script_extensions = ('sh', 'py', 'pl', 'swift')
supported_ea_extensions = ('sh', 'py', 'pl', 'swift')
supported_profile_extensions = ('.mobileconfig', '.profile')


async def upload_profiles(session):
    pass


async def upload_extension_attributes(session, url, user, passwd):
    mypath = dirname(realpath(__file__))
    ext_attrs = [f.name for f in os.scandir(join(mypath, 'extension_attributes'))
                 if f.is_file() and f.name.split('.')[-1] in supported_ea_extensions]
    tasks = []
    for ea in ext_attrs:
        task = asyncio.ensure_future(upload_extension_attribute(session, url, user, passwd, ea))
        tasks.append(task)
    responses = await asyncio.gather(*tasks)


async def upload_extension_attribute(session, url, user, passwd, ext_attr):
    mypath = dirname(realpath(__file__))
    auth = aiohttp.BasicAuth(user, passwd)
    headers = {'content-type': 'application/xml'}
    with open(join(mypath, 'extension_attributes/' + ext_attr), 'r') as f:
        data=f.read()
    with async_timeout.timeout(10):
        template = await get_ea_template(session, url, user, passwd, ext_attr)
        async with session.get(url + '/JSSResource/computerextensionattributes/name/' + template.find('name').text,
                auth=auth) as resp:
            template.find('input_type/script').text = data
            if args.verbose:
                print(ET.tostring(template))
            if resp.status == 200:
                put_url = url + '/JSSResource/computerextensionattributes/name/' + template.find('name').text
                resp = await session.put(put_url, auth=auth, data=ET.tostring(template), headers=headers)
            else:
                post_url = url + '/JSSResource/computerextensionattributes/id/0'
                resp = await session.post(post_url, auth=auth, data=ET.tostring(template), headers=headers)
    if resp.status in (201, 200):
        print(f'Uploaded Extension Attribute {ext_attr}')
    return resp.status


async def get_ea_template(session, url, user, passwd, ext_attr):
    auth = aiohttp.BasicAuth(user, passwd)
    mypath = dirname(realpath(__file__))
    try:
        with open(join(mypath, 'extension_attributes/templates/' + ext_attr.split('.')[0] + '.xml'), 'r') as file:
            template = ET.fromstring(file.read())
    except FileNotFoundError:
        with async_timeout.timeout(10):
            async with session.get(url + '/JSSResource/computerextensionattributes/name/' + ext_attr,
                    auth=auth) as resp:
                if resp.status == 200:
                    async with session.get(url + '/JSSResource/computerextensionattributes/name/' + ext_attr, auth=auth) as response:
                        template = ET.fromstring(await response.text())
                else:
                    template = ET.parse(join(mypath, 'templates/ea.xml')).getroot()
    # name is mandatory, so we use the filename if nothing is set in a template
    if args.verbose:
        print(ET.tostring(template))
    if template.find('name') is None:
        ET.SubElement(template, 'name').text = ext_attr
    elif template.find('name').text is '' or template.find('name').text is None:
        template.find('name').text = ext_attr
    return template


async def upload_scripts(session, url, user, passwd):
    mypath = dirname(realpath(__file__))
    scripts = [f.name for f in os.scandir(join(mypath, 'scripts'))
               if f.is_file() and f.name.split('.')[-1] in supported_script_extensions]
    tasks = []
    for script in scripts:
        task = asyncio.ensure_future(upload_script(session, url, user, passwd, script))
        tasks.append(task)
    responses = await asyncio.gather(*tasks)


async def upload_script(session, url, user, passwd, script):
    mypath = dirname(realpath(__file__))
    auth = aiohttp.BasicAuth(user, passwd)
    headers = {'content-type': 'application/xml'}
    with open(join(mypath, 'scripts/' + script), 'r') as f:
        data=f.read()
    with async_timeout.timeout(10):
        template = await get_script_template(session, url, user, passwd, script)
        async with session.get(url + '/JSSResource/scripts/name/' + template.find('name').text,
                auth=auth) as resp:
            template.find('script_contents').text = data
            # print(ET.tostring(template))
            if resp.status == 200:
                put_url = url + '/JSSResource/scripts/name/' + template.find('name').text
                resp = await session.put(put_url, auth=auth, data=ET.tostring(template), headers=headers)
            else:
                post_url = url + '/JSSResource/scripts/id/0'
                resp = await session.post(post_url, auth=auth, data=ET.tostring(template), headers=headers)
    if resp.status in (201, 200):
        print(f'Uploaded script {script}')
    return resp.status


async def get_script_template(session, url, user, passwd, script):
    auth = aiohttp.BasicAuth(user, passwd)
    mypath = dirname(realpath(__file__))
    try:
        with open(join(mypath, 'scripts/templates/' + script.split('.')[0] + '.xml'), 'r') as file:
            template = ET.fromstring(file.read())
    except FileNotFoundError:
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
    async with aiohttp.ClientSession() as session:
        await upload_scripts(session, args.url, args.username, args.password)
        await upload_extension_attributes(session, args.url, args.username, args.password)


if __name__ == '__main__':
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

    parser = argparse.ArgumentParser(description='Sync repo with JSS')
    parser.add_argument('--url')
    parser.add_argument('--username')
    parser.add_argument('--password')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(args))

