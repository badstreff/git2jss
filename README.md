# git2jss
[![Codacy Badge](https://app.codacy.com/project/badge/Grade/c49c0bd6a88d4f1e8c6808455171178e)](https://app.codacy.com/gh/rustymyers/git2jss/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade)

A fast asynchronous python library for syncing your scripts in git with your JSS easily. This allows admins to keep their script in a version control system for easy updating rather than googling and copy-pasting from resources that they find online.

## Getting Started
1.  Fork the Project
2.  Install [Python version 3.6](https://www.python.org/downloads/) or higher. (this is because of the async requirements)
3.  Run `python3.6 -m pip install -r requirements.txt` to install required modules
4.  Run `./tools/download.py --url https://your.jss.url:8443 --username api_user` to download all scripts and extension attributes to the repository
5.  Run `./sync.py --url https://your.jss.url:8443 --username api_user` to sync all scripts back to your JSS

Optional flags for `download.py`:

-   `--password` for CI/CD (Will prompt for password if not set)
-   `--do_not_verify_ssl` to skip ssl verification
-   `--overwrite` to overwrite all scripts and extension attributes

Optional flags for `sync.py`:

-   `--password` for CI/CD (Will prompt for password if not set)
-   `--do_not_verify_ssl` to skip ssl verification
-   `--overwrite` to overwrite all scripts and extension attributes
-   `--limit` to limit max connections (default=25)
-   `--timeout` to limit max connections (default=60)
-   `--verbose` to add additional logging
-   `--update_all` to upload all resources in `./extension_attributes` and `./scripts`
-   `--jenkins` to write a Jenkins file:`jenkins.properties` with `$scripts` and `$eas` and compare `$GIT_PREVIOUS_COMMIT` with `$GIT_COMMIT`

### [ConfigParser](https://docs.python.org/3/library/configparser.html) (Optional):

A config file can be created in the project root or the users home folder. When a config file exists, the script will not promt for a password.

 A jamfapi.cfg file can provide the following variables:

-   username
-   password
-   url

### Prerequisites
git2jss requires [Python 3.6](https://www.python.org/downloads/) and the python modules listed in `requirements.txt`

## Deployment
The project can be ran ad-hoc with the example listed above, but ideally you setup webhooks and integrate into a CI/CD pipeline so each time a push is made to the repo your scripts are re-uploaded to the JSS.

## Contributing
PR's are always welcome!
