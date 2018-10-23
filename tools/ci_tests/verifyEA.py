#!/usr/bin/env python

import requests
from xml.etree import ElementTree as ET
import os
import getpass
import json

# Use this script to validate that EA values aren't changing as a result of syncing

# Overwrite computers.json
overwrite = False

# Constants
url = 'https://your.jss.com'
username = getpass.getuser()
password = getpass.getpass()


def overwrite_file():
    print('Overwriting File: computers.json...')
    with open('computers.json', 'w') as f:
        f.write(json.dumps(computers))

def read_file():
    print('Reading cached data from disk...')
    with open('computers.json', 'r') as f:
        computers_from_disk = json.load(f)
        return computers_from_disk

def build_computers_data_object():
    # Get IDs for computers 
    print('Communicating with the Jamf Pro Server...')
    computers = {}
    r = requests.get(url + '/JSSResource/computergroups/id/810', 
        auth = (username, password), 
        headers= {'Content-Type': 'application/xml'})

    tree = ET.fromstring(r.content) 
    resource_ids = [ e.text for e in tree.findall('computers/computer/id') ]

    # Download each resource and save to disk
    for resource_id in resource_ids:

        # Get detailed information about the record
        r = requests.get(url + '/JSSResource/computers/id/%s' % (resource_id), 
            auth = (username, password), 
            headers={'Content-Type': 'application/json'})

        # Parse xml 
        tree = ET.fromstring(r.content)
        ea_values = [ e.text for e in tree.findall('extension_attributes/extension_attribute/value') ]
        ea_names = [ e.text for e in tree.findall('extension_attributes/extension_attribute/name') ]

        # Build the json for the comparison 
        computers[resource_id] = {}
        for k,v in zip(ea_names,ea_values):
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
            print("Value Change Found\n\tEA Name:\t{}\n\tOriginal Value:\t{}\n\tNew Value:\t{}".format(key,computers[computer_id][key],computers_from_disk[computer_id][key]))

# Is this the first time it was run?
mypath = os.path.dirname(os.path.realpath(__file__))
if os.path.exists(os.path.join(mypath,'computers.json')):
    computers_from_disk = read_file()
else:
    print('No cached data found, writing new data to computers.json')
    overwrite = True

# Get computers information from JSS
computers = build_computers_data_object()

# Overwrite local file?
if overwrite == True:  
    overwrite_file()

else:
    # Compare each computer
    print('Analyzing the results...')
    for computer_id in list(computers.keys()):
        compare_computer(computer_id)
