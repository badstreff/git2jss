#!/bin/bash
###################################################################################
## Validates XML for proper formatting
###################################################################################

function scripts() {
	
	printf "\033[31m---------------------------------------------------------------------------------\n"
	printf "\033[31m                           Working on Scripts\n"
	printf "\033[31m---------------------------------------------------------------------------------\n"
	printf "\033[0m"
scriptfolders=$(ls -ltr ./scripts | cut -c52- | awk 'NR>1')
	while read folder ; do 
		echo "$folder"
		xmllint  --noout  ./scripts/"$folder"/*.xml
	done <<< "$scriptfolders"

}



function ea(){
	eafolders=$(ls -ltr ./extension_attributes | cut -c52- | awk 'NR>1')

	printf "\033[31m---------------------------------------------------------------------------------\n"
	printf "\033[31m                        Working on Extension Attributes\n"
	printf "\033[31m---------------------------------------------------------------------------------\n"
	printf "\033[0m"
	while read folder ; do 

		echo "$folder"
		
		xmllint  --noout  ./extension_attributes/"$folder"/*.xml
	done <<< "$eafolders"

}

scripts
ea
exit 0
