#!/usr/bin/env python3

import requests
from defusedxml import ElementTree as eTree
import os
import getpass
import json
import configparser

# Use this script to validate that EA values aren't changing as a result of syncing

# Overwrite computers.json
overwrite = False
smart_group = "1018"

# Constants
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
        smart_group = CONFPARSER.get("verifyEA", "smart_group")
    except configparser.NoOptionError:
        print("Can't find smart_group in configfile")

else:
    url = "https://your.jss.com"
    username = getpass.getuser()
    password = getpass.getpass()
    smart_group = input("Enter smart_group")


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


def overwrite_file():
    print("Overwriting File: computers.json...")
    with open("computers.json", "w") as f:
        f.write(json.dumps(computers))


def read_file():
    print("Reading cached data from disk...")
    with open("computers.json", "r") as f:
        computers_from_disk = json.load(f)
        return computers_from_disk


def build_computers_data_object(token, group_id):
    """Builds computer data into local file
    params: token, group_id
    returns: computers objects json
    """
    print("Communicating with the Jamf Pro Server...")
    computers = {}
    r = requests.get(
        url + "/JSSResource/computergroups/id/{0}".format(group_id),
        headers={"Content-Type": "application/xml", "Authorization": "Bearer " + token},
    )

    tree = eTree.fromstring(r.content)
    resource_ids = [e.text for e in tree.findall("computers/computer/id")]

    # Download each resource and save to disk
    for resource_id in resource_ids:
        # Get detailed information about the record
        r = requests.get(
            url + "/JSSResource/computers/id/{0}".format(resource_id),
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + token},
        )

        # Parse xml
        tree = eTree.fromstring(r.content)
        ea_values = [
            e.text
            for e in tree.findall("extension_attributes/extension_attribute/value")
        ]
        ea_names = [
            e.text
            for e in tree.findall("extension_attributes/extension_attribute/name")
        ]

        # Build the json for the comparison
        computers[resource_id] = {}
        for k, v in zip(ea_names, ea_values):
            computers[resource_id][k] = v
    return computers


def compare_computer(computer_id):
    """Compares a computer id record from live to cached copy on disk
    params: computer_id
    returns: None
    """
    print("Processing Computer ID: %s" % computer_id)
    for key in computers[computer_id].keys():
        if computers[computer_id][key] != computers_from_disk[computer_id][key]:
            print(
                "Value Change Found\n\tEA Name:\t{}\n\tOriginal Value:\t{}\n\tNew Value:\t{}".format(
                    key,
                    computers[computer_id][key],
                    computers_from_disk[computer_id][key],
                )
            )


# Is this the first time it was run?
mypath = os.path.dirname(os.path.realpath(__file__))
if os.path.exists(os.path.join(mypath, "computers.json")):
    computers_from_disk = read_file()
else:
    print("No cached data found, writing new data to computers.json")
    overwrite = True

token = get_uapi_token()

# Get computers information from JSS smart group
computers = build_computers_data_object(token, smart_group)

# Overwrite local file?
if overwrite == True:
    overwrite_file()
    print("Computer data staged for comparison with future runs.")
else:
    # Compare each computer
    print("Analyzing the results...")
    for computer_id in list(computers.keys()):
        compare_computer(computer_id)
