# gitlab2sentry

This project aims to automate Sentry project creation.

It's designed to be idempotent.

It the following workflow:
- It creates Sentry `Teams` for every Gitlab `first-level Groups`
- It scans project and creates a MR to ask the developer for a Sentry DSN creation
- If the MR is merged, it means the script will create the DSN on the next run
- It creates a second MR with a `.sentryclirc` file containing the DSN

In order to make the script faster, it only scans for MR created by the Gitlab token associated user.

Warning:
 * Meaning that if you use another user for the script to run, it will create new MR over again.
 * We also had the case of users importing projects instead of using the Gitlab transfer feature. It recreated all the project's MR by changing the author with the user importing projects.

## Requirements

1. A Gitlab Access Token with permissions to use the following scopes

    1. api
    2. read_api
    3. write_repository

2. A Sentry Token from an [Internal Integrations](https://docs.sentry.io/product/integrations/integration-platform/) with the following permissions

    1. Project: Admin
    2. Team: Admin
    3. Organization: Read

## Usage

```
GITLAB_URL=https://gitlab.com GITLAB_TOKEN='sup3rs3cr3t' SENTRY_URL=https://sentry.company.com SENTRY_TOKEN='m0r3sup3rs3cr3t' make run
```
