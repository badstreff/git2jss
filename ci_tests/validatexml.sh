#!/bin/bash
###################################################################################
## Validates XML for proper formatting
###################################################################################

echo "This tool has been moved under the tools/ci_tests/ directory, please use the updated path as this file will be removed in future versions"
xmllint --noout scripts/templates/*.xml
xmllint --noout extension_attributes/templates/*.xml
