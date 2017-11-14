#!/bin/bash
# technical resource: https://macops.ca/os-x-admins-your-clients-are-not-getting-background-security-updates/

# Apply software updates without the configuration updates
defaults write /Library/Preferences/com.apple.SoftwareUpdate AutomaticCheckEnabled -bool false
output="$(softwareupdate --install --all 2>&1)"

# Apply the updates apple has labeled as configuration and critical updates
defaults write /Library/Preferences/com.apple.SoftwareUpdate AutomaticCheckEnabled -bool true
softwareupdate --background-critical
defaults write /Library/Preferences/com.apple.SoftwareUpdate AutomaticCheckEnabled -bool false

# Give 5 minutes plus an additional 5 to restart to finish installing updates
sleep 300
grep -i -q "restart" "$output"
if [ $? -eq 0 ] ; then
  echo "Restarting in 5 minute and notifying user..."
  jamf DisplayMessage -message "Your machine has installed updates that require a restart. Please save your work and quit any applications you have open. Your machine will restart in 5 minutes."
  shutdown -r +5
else
  echo "Restart not required"
fi
