import logging
import os

import yaml

from gitlab2sentry.exceptions import InvalidYamlConfigError

with open("g2s.yaml", "r") as config_file:
    try:
        config = yaml.safe_load(config_file)
    except yaml.YAMLError as exc:
        raise InvalidYamlConfigError(f"Invalid Config File: {str(exc)}")

try:
    # Sentry configuration
    SENTRY_URL = os.getenv("SENTRY_URL")
    SENTRY_TOKEN = os.getenv("SENTRY_TOKEN")
    SENTRY_DSN = os.getenv("SENTRY_DSN")
    SENTRY_ENV = os.getenv("SENTRY_ENV")
    SENTRY_ORG_SLUG = config["sentry"]["slug"]

    # DSN MR configuration.
    DSN_MR_CONTENT = config["gitlab"]["dsn_mr"]["content"]
    DSN_BRANCH_NAME = config["gitlab"]["dsn_mr"]["branch_name"]
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
    GITLAB_GRAPHQL_SUFFIX = config["gitlab"]["config"]["graphql_suffix"]
    GITLAB_GRAPHQL_TIMEOUT = int(config["gitlab"]["config"]["graphql_aiohttp_timeout"])
    GITLAB_GRAPHQL_PAGE_LENGTH = int(config["gitlab"]["config"]["graphql_page_length"])
    GITLAB_AUTHOR_EMAIL = config["gitlab"]["config"]["author"]["email"]
    GITLAB_AUTHOR_NAME = config["gitlab"]["config"]["author"]["name"]
    GITLAB_RMV_SRC_BRANCH = config["gitlab"]["config"]["remove_source"]
    GITLAB_MENTIONS_LIST = config["gitlab"]["config"]["mentions"]
    GITLAB_MR_KEYWORD = config["gitlab"]["config"]["keyword"]
    GITLAB_GROUP_IDENTIFIER = config["gitlab"]["config"]["group_identifier"]
except TypeError as type_error:
    logging.error(
        "<Gitlab2Sentry>: g2s.yaml not configured properly - {}".format(str(type_error))
    )
    exit(1)
except ValueError as value_error:
    logging.error(
        "<Gitlab2Sentry>: g2s.yaml not wrong value type - {}".format(str(value_error))
    )
    exit(1)

# GraphQL Queries.
GRAPHQL_PROJECTS_QUERY = {
    "name": "OPENED_MRS_QUERY",
    "body": """
{
    projects%s {
        edges {
            node {
                id
                name
                mergeRequestsEnabled
                group {
                    name
                }
                repository {
                    blobs%s {
                        nodes {
                            name
                            rawTextBlob
                        }
                    }
                }
                mergeRequests%s {
                    nodes {
                        id
                        title
                        state
                    }
                }
            }
        }
        pageInfo {
            endCursor
            hasNextPage
        }
    }
}
""",
}
