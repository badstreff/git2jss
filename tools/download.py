#!/usr/bin/env python3
import getpass
import requests
from defusedxml import ElementTree as eTree
from xml.dom import minidom
import os
import argparse
import urllib3
import configparser

# Suppress the warning in dev
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


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


def download_scripts(
    mode,
    overwrite=None,
):
    """Downloads Scripts to ./scripts and Extension Attributes to ./extension_attributes

    Folder Structure:
    ./scripts/script_name/script.sh
    ./scripts/script_name/script.xml
    ./extension_attributes/ea_name/ea.sh
    ./extension_attributes/ea_name/ea.xml

    Usage:

    Download all Extension Attributes from JSS:
    download_scripts('ea','overwrite=False)

    Download all Extension Attributes from JSS:
    download_scripts('script','overwrite=False)

    Params:
    mode = 'script' or 'ea'
    overwrite = True/False
    Returns: None
    """

    # Set various values based on resource type
    if mode == "ea":
        resource = "computerextensionattributes"
        download_path = "extension_attributes"
        script_xml = "input_type/script"

    if mode == "script":
        resource = "scripts"
        download_path = "scripts"
        script_xml = "script_contents"

    token = get_uapi_token()
    # Get all IDs of resource type
    r = requests.get(
        url + "/JSSResource/%s" % resource,
        headers={
            "Accept": "application/xml",
            "Content-Type": "application/xml",
            "Authorization": "Bearer " + token,
        },
        verify=args.do_not_verify_ssl,
        timeout=5,
    )

    # Basic error handling
    if r.status_code != 200:
        print(
            "Something went wrong with the request, check your password and privileges and try again. \n \
        It's also possible that the url is incorrect. \n \
        Here is the HTTP Status code: %s"
            % r.status_code
        )
        exit(1)
    tree = eTree.fromstring(r.content)
    resource_ids = [e.text for e in tree.findall(".//id")]

    # Download each resource and save to disk
    for resource_id in resource_ids:
        get_script = True

        r = requests.get(
            url + "/JSSResource/%s/id/%s" % (resource, resource_id),
            headers={
                "Accept": "application/xml",
                "Content-Type": "application/xml",
                "Authorization": "Bearer " + token,
            },
            verify=args.do_not_verify_ssl,
            timeout=5,
        )
        tree = eTree.fromstring(r.content)

        if mode == "ea":
            if tree.find("input_type/type").text != "script":
                print("No script found in: %s" % tree.find("name").text)
                get_script = False
                # continue

        # Determine resource path (folder name)
        resource_path = os.path.join(export_path, download_path, tree.find("name").text)

        # Check to see if it exists
        if os.path.exists(resource_path):
            print("Resource is already in the repo: ", tree.find("name").text)

            if not overwrite:
                print("\tSkipping: ", tree.find("name").text)
                continue

        else:  # Make the folder
            os.makedirs(resource_path)

        print("Saving: ", tree.find("name").text)

        # Create script string, and determine the file extension
        if get_script:
            xmlstr = eTree.tostring(
                tree.find(script_xml), encoding="unicode", method="text"
            ).replace("\r", "")
            if xmlstr.startswith("#!/bin/sh"):
                ext = ".sh"
            elif xmlstr.startswith("#!/usr/bin/env sh"):
                ext = ".sh"
            elif xmlstr.startswith("#!/bin/bash"):
                ext = ".sh"
            elif xmlstr.startswith("#!/usr/bin/env bash"):
                ext = ".sh"
            elif xmlstr.startswith("#!/bin/zsh"):
                ext = ".sh"
            elif xmlstr.startswith("#!/usr/bin/python"):
                ext = ".py"
            elif xmlstr.startswith("#!/usr/bin/env python"):
                ext = ".py"
            elif xmlstr.startswith("#!/usr/bin/perl"):
                ext = ".pl"
            elif xmlstr.startswith("#!/usr/bin/ruby"):
                ext = ".rb"
            else:
                print("No interpreter directive found for: ", tree.find("name").text)
                ext = ".sh"  # Call it sh for now so the uploader detects it

            with open(os.path.join(resource_path, "%s%s" % (mode, ext)), "w") as f:
                f.write(xmlstr)

            # Need to remove ID and script contents and write out xml
            try:
                tree.find(script_xml).clear()
                tree.remove(tree.find("id"))
                tree.remove(tree.find("script_contents_encoded"))
                tree.remove(tree.find("filename"))
            except:
                pass

        xmlstr = minidom.parseString(
            eTree.tostring(tree, encoding="unicode", method="xml")
        ).toprettyxml(indent="   ")
        with open(os.path.join(resource_path, "%s.xml" % mode), "w") as f:
            f.write(xmlstr)
    invalidate_uapi_token(token)


if __name__ == "__main__":
    # Export to current directory by default
    export_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..")

    parser = argparse.ArgumentParser(description="Download Scripts from Jamf")
    parser.add_argument("--url")
    parser.add_argument("--username")
    parser.add_argument("--password")
    parser.add_argument("--export_path")
    parser.add_argument("--overwrite", action="store_true")  # Overwrites existing files
    parser.add_argument(
        "--do_not_verify_ssl", action="store_false"
    )  # Skips SSL verification
    args = parser.parse_args()
    # Get configs from files
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
            export_path = CONFPARSER.get("jss", "export_path")
        except configparser.NoOptionError:
            print("Can't find export_path in config")

    # Ask for password if not supplied via command line args
    if args.password:
        password = args.password
    elif password is None:
        password = getpass.getpass()

    if args.export_path:
        export_path = args.export_path

    if args.url:
        url = args.url

    if args.username:
        username = args.username

    # Run script download for extension attributes
    download_scripts(overwrite=args.overwrite, mode="ea")
    # Run script download for scripts
    download_scripts(overwrite=args.overwrite, mode="script")
