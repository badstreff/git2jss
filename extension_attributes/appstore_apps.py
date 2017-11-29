#!/usr/bin/python

import xml.etree.ElementTree as ET
import plistlib

receipt_path = '/Library/Receipts/InstallHistory.plist'
receipts = plistlib.readPlist(receipt_path)

# for item in receipts:
#     if item['processName'] == 'storedownloadd':
#         print item['displayName']

apps = set(item['displayName'] for item in receipts if item['processName'] == 'storedownloadd')
print '<result>'
for app in apps:
    print(app)
print '</result>'
