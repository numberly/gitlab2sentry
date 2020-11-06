# gitlab2sentry

This project aims to automate Sentry project creation

The workflow is the following:

* An user create a `Gitlab Project`
* `gitlab2sentry` makes sure the `Sentry Team` with the same `Gitlab Group` exists
* It then creates a `Merge Request` with a `.sentryclirc` file within the `Gitlab Project`
* If the `Merge Request` is accepted it creates a Sentry project in the same `Sentry Team` as the `Gitlab Group`
* It then posts the `DSNs` within the `Merge Request`


## Requirements

* python-gitlab 
* slugify 
* requests 

## Usage

```
GITLAB_TOKEN='sup3rs3cr3t' SENTRY_TOKEN='m0r3sup3rs3cr3t' python3 main.py
```
