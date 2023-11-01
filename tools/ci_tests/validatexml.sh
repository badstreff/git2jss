#!/bin/zsh
###################################################################################
## Validates XML for proper formatting
###################################################################################

function scripts() {
	
	printf "\033[31m---------------------------------------------------------------------------------\n"
	printf "\033[31m                           Working on Scripts\n"
	printf "\033[31m---------------------------------------------------------------------------------\n"
	printf "\033[0m"
scriptfolders=$(ls -1 ./scripts | awk 'NR>1')
	while read folder ; do 
		echo "$folder"
		xmllint --noout ./scripts/"$folder"/*.xml
	done <<< "$scriptfolders"

}



function ea(){
	eafolders=$(ls -1 ./extension_attributes | awk 'NR>1')

	printf "\033[31m---------------------------------------------------------------------------------\n"
	printf "\033[31m                        Working on Extension Attributes\n"
	printf "\033[31m---------------------------------------------------------------------------------\n"
	printf "\033[0m"
	while read folder ; do 

		echo "$folder"
		
		xmllint --noout ./extension_attributes/"$folder"/*.xml
	done <<< "$eafolders"

}

scripts
ea
exit 0
