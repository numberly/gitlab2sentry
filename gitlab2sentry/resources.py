import os

import yaml

from gitlab2sentry.exceptions import InvalidYamlConfigError

with open("config.yaml", "r") as config_file:
    try:
        config = yaml.safe_load(config_file)
    except yaml.YAMLError as exc:
        raise InvalidYamlConfigError(f"Invalid Config File: {str(exc)}")


# Sentry configuration
SENTRY_URL = os.getenv("SENTRY_URL")
SENTRY_TOKEN = os.getenv("SENTRY_TOKEN")
SENTRY_DSN = os.getenv("SENTRY_DSN")
SENTRY_ENV = os.getenv("SENTRY_ENV")
SENTRY_ORG_SLUG = config["sentry"]["slug"]

# DSN MR configuration.
DSN_MR_CONTENT = config["gitlab"]["dsn_mr"]["content"]
DSN_MR_BRANCH_NAME = config["gitlab"]["dsn_mr"]["branch_name"]
DSN_MR_TITLE = config["gitlab"]["dsn_mr"]["title"]
DSN_MR_DESCRIPTION = config["gitlab"]["dsn_mr"]["description"]

# Sentryclirc MR configuration.
SENTRYCLIRC_MR_CONTENT = config["gitlab"]["sentryclirc_mr"]["content"]
SENTRYCLIRC_BRANCH_NAME = config["gitlab"]["sentryclirc_mr"]["branch_name"]
SENTRYCLIRC_MR_TITLE = config["gitlab"]["sentryclirc_mr"]["title"]
SENTRYCLIRC_FILEPATH = config["gitlab"]["sentryclirc_mr"]["filepath"]
SENTRYCLIRC_COM_MSG = config["gitlab"]["sentryclirc_mr"]["commit_message"]
SENTRYCLIRC_MR_DESCRIPTION = config["gitlab"]["sentryclirc_mr"]["description"]

# Gitlab Configuration.
GITLAB_URL = os.getenv("GITLAB_URL")
GITLAB_TOKEN = os.getenv("GITLAB_TOKEN")
GITLAB_AUTHOR_EMAIL = config["gitlab"]["config"]["author"]["email"]
GITLAB_AUTHOR_NAME = config["gitlab"]["config"]["author"]["name"]
GITLAB_RMV_SRC_BRANCH = config["gitlab"]["config"]["remove_source"]
GITLAB_MENTIONS_LIST = config["gitlab"]["config"]["mentions"]
GITLAB_MR_KEYWORD = config["gitlab"]["config"]["keyword"]
