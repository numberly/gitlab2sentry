# Configuration Guide

This application uses `pydantic`'s `BaseSettings` for configuration, which allows you to set and override parameters using environment variables. Below, you'll find a list of all the configuration options and the expected environment variables. Each configuration setting has a default value, but you can easily override them to suit your deployment needs.

To configure the application, set the following environment variables:

| Environment Variable            | Description                                        | Default Value                 |
| ------------------------------- | -------------------------------------------------- | ----------------------------- |
| `DSN_BRANCH_NAME`               | Branch name for DSN changes                        | `auto_add_sentry_dsn`         |
| `DSN_MR_CONTENT`                | Merge request content for DSN                      | Custom template (see code)    |
| `DSN_MR_DESCRIPTION`            | Description for DSN-related merge request          | Custom template (see code)    |
| `DSN_MR_TITLE`                  | Title for DSN-related merge request                | `[gitlab2sentry] Merge me...` |
| `ENV`                           | The environment the application is running in      | `production`                  |
| `GITLAB_AUTHOR_EMAIL`           | GitLab author email for merge requests             | `default-email@example.com`   |
| `GITLAB_AUTHOR_NAME`            | GitLab author name for merge requests              | `Default Author`              |
| `GITLAB_GRAPHQL_PAGE_LENGTH`    | Page length for GitLab GraphQL queries             | `0`                           |
| `GITLAB_GRAPHQL_SUFFIX`         | Suffix for GitLab GraphQL queries                  | `default-content`             |
| `GITLAB_GRAPHQL_TIMEOUT`        | Timeout for GitLab GraphQL queries (in seconds)    | `10`                          |
| `GITLAB_GROUP_IDENTIFIER`       | Group identifier for GitLab projects               | Empty string                  |
| `GITLAB_MENTIONS_ACCESS_LEVEL`  | Access level to mention users in GitLab MRs        | `40`                          |
| `GITLAB_MENTIONS`               | GitLab usernames to mention                        | Empty string                  |
| `GITLAB_MR_KEYWORD`             | Keyword to include in GitLab merge requests        | `sentry`                      |
| `GITLAB_MR_LABEL_LIST`          | Labels to assign to GitLab merge requests          | `['sentry']`                  |
| `GITLAB_PROJECT_CREATION_LIMIT` | Limit for creating GitLab projects                 | `30`                          |
| `GITLAB_RMV_SRC_BRANCH`         | Remove source branch after merge request           | `True`                        |
| `GITLAB_SIGNED_COMMIT`          | Whether to use signed commits in GitLab            | `False`                       |
| `GITLAB_TOKEN`                  | GitLab access token                                | `default-token`               |
| `GITLAB_URL`                    | Base URL for GitLab service                        | `http://default-gitlab-url`   |
| `SENTRYCLIRC_BRANCH_NAME`       | Branch name for Sentry CLI configuration changes   | `auto_add_sentry`             |
| `SENTRYCLIRC_COM_MSG`           | Commit message for `.sentryclirc` update           | `Update .sentryclirc`         |
| `SENTRYCLIRC_FILEPATH`          | Filepath for `.sentryclirc` configuration          | `.sentryclirc`                |
| `SENTRYCLIRC_MR_CONTENT`        | Merge request content for Sentry CLI configuration | Custom template (see code)    |
| `SENTRYCLIRC_MR_DESCRIPTION`    | Description for Sentry CLI configuration MR        | Custom template (see code)    |
| `SENTRYCLIRC_MR_TITLE`          | Title for Sentry CLI configuration MR              | `[gitlab2sentry] Merge me...` |
| `SENTRY_DSN`                    | Sentry DSN for monitoring                          | `http://default.sentry.com`   |
| `SENTRY_ENV`                    | Sentry environment name                            | `production`                  |
| `SENTRY_ORG_SLUG`               | Organization slug for Sentry                       | `default_org`                 |
| `SENTRY_TOKEN`                  | Authentication token for Sentry                    | `default-token`               |
| `SENTRY_URL`                    | Base URL for Sentry service                        | `http://default-sentry-url`   |

To override any configuration, simply set the respective environment variable before running the application. For instance:

```sh
export SENTRY_DSN="http://your.custom.sentry.dsn"
export GITLAB_URL="http://your.gitlab.url"
```
