#!/usr/bin/env python

import argparse
import asyncio
from os.path import basename, join, dirname, realpath
from os import walk

import uvloop
import aiojss

supported_script_extensions = ('sh', 'py', 'pl', 'swift')
supported_ea_extensions = ('sh', 'py', 'pl', 'swift')


async def sync_jssobject(jss, path):
    # pylint: disable=invalid-name,broad-except
    mypath = dirname(realpath(__file__))
    template = None
    try:
        with open(path + '.xml', 'r') as f:
            template = f.read()
    except Exception:
        pass
    if 'scripts' in path:
        if not template:
            with open(join(mypath, 'templates/script.xml'), 'r') as f:
                template = f.read()
        jssobject = aiojss.Script(template, jss)
    else:
        if not template:
            with open(join(mypath, 'templates/ea.xml'), 'r') as f:
                template = f.read()
        jssobject = aiojss.ExtensionAttribute(template, jss)
    if jssobject.name == '':
        jssobject.name = basename(path)
    print('---name---')
    jssobject.name = 'asdf'
    print(jssobject.name)
    print(jssobject.raw_xml())
    await jssobject.save()


async def main(args):
    # pylint: disable=redefined-outer-name,invalid-name
    mypath = dirname(realpath(__file__))
    semaphore = asyncio.BoundedSemaphore(args.limit)
    tasks = []
    async with semaphore:
        jss = aiojss.JSS(args.url, args.username, args.password)
        for path in walk(join(mypath, 'scripts')):
            for f in path[2]:
                if f.split('.')[-1] in supported_script_extensions:
                    print(f'syncing {f}')
                    coroutine = sync_jssobject(jss, join(path[0], f))
                    task = asyncio.ensure_future(coroutine)
                    tasks.append(task)
        for path in walk(join(mypath, 'extension_attributes')):
            for f in path[2]:
                if f.split('.')[-1] in supported_ea_extensions:
                    print(f'syncing {f}')
                    coroutine = sync_jssobject(jss, join(path[0], f))
                    task = asyncio.ensure_future(coroutine)
                    tasks.append(task)
        await asyncio.gather(*tasks)


if __name__ == '__main__':
    # pylint: disable=invalid-name
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

    parser = argparse.ArgumentParser(description='Sync repo with JSS')
    parser.add_argument('--url')
    parser.add_argument('--username')
    parser.add_argument('--password')
    parser.add_argument('--limit', type=int, default=25)
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(args))
