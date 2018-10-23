#!/bin/bash
###################################################################################
## Validates XML for proper formatting
###################################################################################

xmllint --noout scripts/templates/*.xml
xmllint --noout extension_attributes/templates/*.xml
