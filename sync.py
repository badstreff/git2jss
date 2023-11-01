#!/usr/bin/env python3
# pylint: disable=missing-docstring,invalid-name
import warnings
import os
from os.path import dirname, join, realpath
import sys
import xml.etree.ElementTree as eTree
import getpass
import argparse
import logging
import asyncio
import async_timeout
import aiohttp
import uvloop
import configparser
import requests

logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)7s: %(message)s",
    stream=sys.stderr,
)
LOG = logging.getLogger("")

# The Jenkins file will contain a list of changes scripts and eas
# in $scripts and $eas.
# Use this variable to add a Slack emoji in front of each item if
# you use a post-build action for a Slack custom message
SLACK_EMOJI = ":white_check_mark: "
SUPPORTED_SCRIPT_EXTENSIONS = ("sh", "py", "pl", "swift", "rb")
SUPPORTED_EA_EXTENSIONS = ("sh", "py", "pl", "swift", "rb")
CATEGORIES = []


# https://github.com/lazymutt/Jamf-Pro-API-Sampler/blob/5f8efa92911271248f527e70bd682db79bc600f2/jamf_duplicate_detection.py#L99
def get_uapi_token():
    """
    fetches api token
    """
    jamf_test_url = url + "/api/v1/auth/token"
    response = requests.post(url=jamf_test_url, auth=(username, password), timeout=5)
    response_json = response.json()
    return response_json["token"]


def invalidate_uapi_token(uapi_token):
    """
    invalidates api token
    """
    jamf_test_url = url + "/api/v1/auth/invalidate-token"
    headers = {"Accept": "*/*", "Authorization": "Bearer " + uapi_token}
    _ = requests.post(url=jamf_test_url, headers=headers, timeout=5)


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
        git_changes = (
            os.popen("git diff --name-only $GIT_PREVIOUS_COMMIT $GIT_COMMIT")
            .read()
            .split("\n")
        )

    # Compare the last two commits to determine the list of files that
    # were changed
    else:
        git_commits = (
            os.popen('git log -2 --pretty=oneline --pretty=format:"%h"')
            .read()
            .split("\n")
        )
        command = "git diff --name-only" + " " + git_commits[1] + " " + git_commits[0]
        git_changes = os.popen(command).read().split("\n")

    for i in git_changes:
        if "extension_attributes/" in i and i.split("/")[1] not in changed_ext_attrs:
            changed_ext_attrs.append(i.split("/")[1])

    for i in git_changes:
        if "scripts/" in i and i.split("/")[1] not in changed_scripts:
            changed_scripts.append(i.split("/")[1])


def write_jenkins_file():
    """Write changed_ext_attrs and changed_scripts to jenkins file.
    $eas will contains the changed extension attributes,
    $scripts will contains the changed scripts
    If there are no changes, the variable will be set to 'None'
    """

    if not changed_ext_attrs:
        contents = "eas=" + "None"
    else:
        contents = "eas=" + SLACK_EMOJI + changed_ext_attrs[0] + "\\n" + "\\"
        for changed_ext_attr in changed_ext_attrs[1:]:
            contents = contents + "\n" + SLACK_EMOJI + changed_ext_attr + "\\n" + "\\"

    if not changed_scripts:
        contents = contents.rstrip("\\") + "\n" + "scripts=" + "None"

    else:
        contents = (
            contents.rstrip("\\")
            + "\n"
            + "scripts="
            + SLACK_EMOJI
            + changed_scripts[0]
            + "\\n"
            + "\\"
        )
        for changed_script in changed_scripts[1:]:
            contents = contents + "\n" + SLACK_EMOJI + changed_script + "\\n" + "\\"

    with open("jenkins.properties", "w") as f:
        f.write(contents)


async def upload_extension_attributes(session, url, user, passwd, semaphore):
    # sync_path = dirname(realpath(__file__))
    if not changed_ext_attrs and not args.update_all:
        print("No Changes in Extension Attributes")
        return
    ext_attrs = [
        f.name
        for f in os.scandir(join(sync_path, "extension_attributes"))
        if f.is_dir() and f.name in changed_ext_attrs
    ]
    if args.update_all:
        print("Copying all extension attributes...")
        ext_attrs = [
            f.name
            for f in os.scandir(join(sync_path, "extension_attributes"))
            if f.is_dir()
        ]
    tasks = []
    for ea in ext_attrs:
        task = asyncio.ensure_future(
            upload_extension_attribute(session, url, user, passwd, ea, semaphore)
        )
        tasks.append(task)
    await asyncio.gather(*tasks)


async def upload_extension_attribute(session, url, user, passwd, ext_attr, semaphore):
    has_script = True

    # sync_path = dirname(realpath(__file__))
    # auth = aiohttp.BasicAuth(user, passwd)
    headers = {
        "Accept": "application/xml",
        "Content-Type": "application/xml",
        "Authorization": "Bearer " + token,
    }
    # Get the script files within the folder, we'll only use
    # script_file[0] in case there are multiple files
    script_file = [
        f.name
        for f in os.scandir(join(sync_path, "extension_attributes", ext_attr))
        if f.is_file() and f.name.split(".")[-1] in SUPPORTED_EA_EXTENSIONS
    ]
    if script_file == []:
        print("Warning: No script file found in extension_attributes/%s" % ext_attr)
        has_script = False
        # return  # Need to skip if no script.
    if has_script:
        with open(
            join(sync_path, "extension_attributes", ext_attr, script_file[0]), "r"
        ) as f:
            data = f.read()
    async with semaphore:
        with async_timeout.timeout(args.timeout):
            template = await get_ea_template(session, url, user, passwd, ext_attr)
            async with session.get(
                url
                + "/JSSResource/computerextensionattributes/name/"
                + template.find("name").text,
                headers=headers,
            ) as resp:
                if has_script and data:
                    template.find("input_type/script").text = data
                if args.verbose:
                    print(eTree.tostring(template))
                    print("response status initial get: ", resp.status)
                if resp.status == 200:
                    put_url = (
                        url
                        + "/JSSResource/computerextensionattributes/name/"
                        + template.find("name").text
                    )
                    resp = await session.put(
                        put_url, data=eTree.tostring(template), headers=headers
                    )
                else:
                    post_url = url + "/JSSResource/computerextensionattributes/id/0"
                    resp = await session.post(
                        post_url, data=eTree.tostring(template), headers=headers
                    )
    if args.verbose:
        print("response status: ", resp.status)
        print("EA: ", ext_attr)
        print("EA Name: ", template.find("name").text)
    if resp.status in (201, 200):
        print("Uploaded Extension Attribute: %s" % template.find("name").text)
    else:
        print("Error uploading script: %s" % template.find("name").text)
        print("Error: %s" % resp.status)
    return resp.status


async def get_ea_template(session, url, user, passwd, ext_attr):
    # auth = aiohttp.BasicAuth(user, passwd)
    # sync_path = dirname(realpath(__file__))
    xml_file = [
        f.name
        for f in os.scandir(join(sync_path, "extension_attributes", ext_attr))
        if f.is_file() and f.name.split(".")[-1] in "xml"
    ]
    try:
        with open(
            join(sync_path, "extension_attributes", ext_attr, xml_file[0]), "r"
        ) as file:
            template = eTree.fromstring(file.read())
    except IndexError:
        with async_timeout.timeout(args.timeout):
            headers = {
                "Accept": "application/xml",
                "Content-Type": "application/xml",
                "Authorization": "Bearer " + token,
            }

            async with session.get(
                url + "/JSSResource/computerextensionattributes/name/" + ext_attr,
                headers=headers,
            ) as resp:
                if resp.status == 200:
                    async with session.get(
                        url
                        + "/JSSResource/computerextensionattributes/name/"
                        + ext_attr,
                        headers=headers,
                    ) as response:
                        template = eTree.fromstring(await response.text())
                else:
                    template = eTree.parse(
                        join(sync_path, "templates/ea.xml")
                    ).getroot()
    # name is mandatory, so we use the foldername if nothing is set in
    # a template
    if args.verbose:
        print(eTree.tostring(template))
    if template.find("category") and template.find("category").text not in CATEGORIES:
        eTree.SubElement(template, "category").text = "None"
        if args.verbose:
            c = template.find("category").text
            print(
                f"""WARNING: Unable to find category {c} in the JSS,
                  setting to None"""
            )
    if template.find("name") is None:
        eTree.SubElement(template, "name").text = ext_attr
    elif not template.find("name").text or template.find("name").text is None:
        template.find("name").text = ext_attr
    return template


async def upload_scripts(session, url, user, passwd, semaphore):
    # sync_path = dirname(realpath(__file__))

    if not changed_scripts and not args.update_all:
        print("No Changes in Scripts")
    scripts = [
        f.name
        for f in os.scandir(join(sync_path, "scripts"))
        if f.is_dir() and f.name in changed_scripts
    ]
    if args.update_all:
        print("Copying all scripts...")
        scripts = [f.name for f in os.scandir(join(sync_path, "scripts")) if f.is_dir()]

    tasks = []
    for script in scripts:
        task = asyncio.ensure_future(
            upload_script(session, url, user, passwd, script, semaphore)
        )
        tasks.append(task)
    await asyncio.gather(*tasks)


async def upload_script(session, url, user, passwd, script, semaphore):
    # sync_path = dirname(realpath(__file__))
    # auth = aiohttp.BasicAuth(user, passwd)
    headers = {
        "Accept": "application/xml",
        "Content-Type": "application/xml",
        "Authorization": "Bearer " + token,
    }
    script_file = [
        f.name
        for f in os.scandir(join(sync_path, "scripts", script))
        if f.is_file() and f.name.split(".")[-1] in SUPPORTED_SCRIPT_EXTENSIONS
    ]
    if script_file == []:
        print("Warning: No script file found in scripts/%s" % script)
        return  # Need to skip if no script.
    with open(join(sync_path, "scripts", script, script_file[0]), "r") as f:
        data = f.read()
    async with semaphore:
        with async_timeout.timeout(args.timeout):
            template = await get_script_template(session, url, user, passwd, script)
            async with session.get(
                url + "/JSSResource/scripts/name/" + template.find("name").text,
                headers=headers,
            ) as resp:
                template.find("script_contents").text = data
                if resp.status == 200:
                    put_url = (
                        url + "/JSSResource/scripts/name/" + template.find("name").text
                    )
                    resp = await session.put(
                        put_url, data=eTree.tostring(template), headers=headers
                    )
                else:
                    post_url = url + "/JSSResource/scripts/id/0"
                    resp = await session.post(
                        post_url, data=eTree.tostring(template), headers=headers
                    )
    if resp.status in (201, 200):
        print("Uploaded script: %s" % template.find("name").text)
    else:
        print("Error uploading script: %s" % template.find("name").text)
        print("Error: %s" % resp.status)
    return resp.status


async def get_script_template(session, url, user, passwd, script):
    # auth = aiohttp.BasicAuth(user, passwd)
    # sync_path = dirname(realpath(__file__))
    xml_file = [
        f.name
        for f in os.scandir(join(sync_path, "scripts", script))
        if f.is_file() and f.name.split(".")[-1] in "xml"
    ]
    try:
        with open(join(sync_path, "scripts", script, xml_file[0]), "r") as file:
            template = eTree.fromstring(file.read())
    except IndexError:
        with async_timeout.timeout(args.timeout):
            headers = {
                "Accept": "application/xml",
                "Content-Type": "application/xml",
                "Authorization": "Bearer " + token,
            }
            async with session.get(
                url + "/JSSResource/scripts/name/" + script, headers=headers
            ) as resp:
                if resp.status == 200:
                    async with session.get(
                        url + "/JSSResource/scripts/name/" + script, headers=headers
                    ) as response:
                        template = eTree.fromstring(await response.text())
                else:
                    template = eTree.parse(
                        join(sync_path, "templates/script.xml")
                    ).getroot()
    # name is mandatory, so we use the filename if nothing is set in a template
    if args.verbose:
        print(eTree.tostring(template))
    if (
        template.find("category") is not None
        and template.find("category").text not in CATEGORIES
    ):
        c = template.find("category").text
        template.remove(template.find("category"))
        if args.verbose:
            print(
                f"""WARNING: Unable to find category "{c}" in the JSS,
                    setting to None"""
            )
    if template.find("name") is None:
        eTree.SubElement(template, "name").text = script
    elif not template.find("name").text or template.find("name").text is None:
        template.find("name").text = script
    return template


async def get_existing_categories(session, url, user, passwd, semaphore):
    # auth = aiohttp.BasicAuth(user, passwd)
    headers = {
        "Accept": "application/xml",
        "Content-Type": "application/xml",
        "Authorization": "Bearer " + token,
    }
    async with semaphore:
        with async_timeout.timeout(args.timeout):
            async with session.get(
                url + "/JSSResource/categories", headers=headers
            ) as resp:
                if resp.status in (201, 200):
                    return [
                        c.find("name").text
                        for c in [
                            e
                            for e in eTree.fromstring(await resp.text()).findall(
                                "category"
                            )
                        ]
                    ]
    return []


async def main():
    # pylint: disable=global-statement
    global CATEGORIES
    semaphore = asyncio.BoundedSemaphore(args.limit)
    async with aiohttp.ClientSession() as session:
        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=args.do_not_verify_ssl)
        ) as session:
            CATEGORIES = await get_existing_categories(
                session, url, username, password, semaphore
            )
            await upload_scripts(session, url, username, password, semaphore)
            await upload_extension_attributes(
                session, url, username, password, semaphore
            )


if __name__ == "__main__":
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

    # Export to current directory by default
    sync_path = dirname(realpath(__file__))

    parser = argparse.ArgumentParser(description="Sync repo with JamfPro")
    parser.add_argument("--url")
    parser.add_argument("--username")
    parser.add_argument("--password")
    parser.add_argument("--sync_path")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--do_not_verify_ssl", action="store_false")
    parser.add_argument("--update_all", action="store_true")
    parser.add_argument("--jenkins", action="store_true")
    args = parser.parse_args()

    changed_ext_attrs = []
    changed_scripts = []
    check_for_changes()
    print("Changed Extension Attributes: ", changed_ext_attrs)
    print("Changed Scripts: ", changed_scripts)

    if args.jenkins:
        write_jenkins_file()
    # Set configs file locations
    CONFIG_FILE_LOCATIONS = ["jamfapi.cfg", os.path.expanduser("~/jamfapi.cfg")]
    CONFIG_FILE = ""
    # Parse Config File
    CONFPARSER = configparser.ConfigParser()
    for config_path in CONFIG_FILE_LOCATIONS:
        if os.path.exists(config_path):
            print("Found Config: {0}".format(config_path))
            CONFIG_FILE = config_path

    if CONFIG_FILE != "":
        # Get config
        CONFPARSER.read(CONFIG_FILE)
        try:
            username = CONFPARSER.get("jss", "username")
        except configparser.NoOptionError:
            print("Can't find username in configfile")
        try:
            password = CONFPARSER.get("jss", "password")
        except configparser.NoOptionError:
            print("Can't find password in configfile")
        try:
            url = CONFPARSER.get("jss", "server")
        except configparser.NoOptionError:
            print("Can't find url in configfile")
        try:
            sync_path = CONFPARSER.get("jss", "sync_path")
        except configparser.NoOptionError:
            print("Can't find sync_path in config")

    # Ask for password if not supplied via command line args
    if args.password:
        password = args.password
    elif password is None:
        password = getpass.getpass()

    if args.sync_path:
        sync_path = args.sync_path

    if args.url:
        url = args.url

    if args.username:
        username = args.username

    token = get_uapi_token()

    loop = asyncio.get_event_loop()

    if args.verbose:
        loop.set_debug(True)
        loop.slow_callback_duration = 0.001
        warnings.simplefilter("always", ResourceWarning)

    loop.run_until_complete(main())

    # Remove token
    invalidate_uapi_token(token)
