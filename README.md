# git2jss


A fast asynchronous python library for syncing your scripts in git with your JSS easily. This allows admins to keep their script in a version control system for easy updating rather than googling and copy-pasting from resources that they find online.


## Getting Started

1. Fork the Project
2. Install python version 3.6 or higher. (this is because of the async requirements)
3. Run `python -m pip install -r requirements.txt`
4. Run `./sync.py --url https://your.jss.com:8443 --username git2jss_admin --password your_password_here`

*Additional information can be found in the [Wiki](https://github.com/BadStreff/git2jss/wiki)*


### Prerequisites

git2jss requires `python 3.6` or higher and the python modules listed in `requirements.txt`


## Deployment

The project can be ran ad-hoc with the example listed above, but ideally you setup webhooks and integrate into a build server so each time a push is made to the repo your scripts are re-uploaded to the JSS.


## Contributing

PR's are always welcome
