import logging
import os
from collections import namedtuple
from typing import List, Tuple

import yaml

from gitlab2sentry.exceptions import InvalidYamlConfigError

with open("g2s.yaml", "r") as config_file:
    try:
        config = yaml.safe_load(config_file)
    except yaml.YAMLError as exc:
        raise InvalidYamlConfigError(f"Invalid Config File: {str(exc)}")

try:
    ENV = os.getenv("ENV", "production")
    TEST_SENTRY_URL = "http://sentry.test.com"
    TEST_SENTRY_DSN = "http://test.sentry.test.com"
    TEST_SENTRY_TOKEN = "test-token"
    TEST_GITLAB_URL = "http://test-gitlab-url"
    TEST_GITLAB_TOKEN = "test-token"

    # Sentry configuration
    SENTRY_URL = os.getenv("SENTRY_URL") if ENV != "test" else TEST_SENTRY_URL
    SENTRY_TOKEN = os.getenv("SENTRY_TOKEN") if ENV != "test" else TEST_SENTRY_TOKEN
    SENTRY_DSN = os.getenv("SENTRY_DSN") if ENV != "test" else TEST_SENTRY_DSN
    SENTRY_ENV = os.getenv("SENTRY_ENV", "production")
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
    GITLAB_URL = os.getenv("GITLAB_URL") if ENV != "test" else TEST_GITLAB_URL
    GITLAB_TOKEN = os.getenv("GITLAB_TOKEN") if ENV != "test" else TEST_GITLAB_TOKEN
    GITLAB_GRAPHQL_SUFFIX = config["gitlab"]["config"]["graphql_suffix"]
    GITLAB_GRAPHQL_TIMEOUT = int(config["gitlab"]["config"]["graphql_aiohttp_timeout"])
    GITLAB_GRAPHQL_PAGE_LENGTH = int(config["gitlab"]["config"]["graphql_page_length"])
    GITLAB_GROUP_IDENTIFIER = config["gitlab"]["config"].get("group_identifier", "")
    GITLAB_AUTHOR_EMAIL = config["gitlab"]["config"]["author"]["email"]
    GITLAB_AUTHOR_NAME = config["gitlab"]["config"]["author"]["name"]
    GITLAB_PROJECT_CREATION_LIMIT = int(
        config["gitlab"]["config"].get("creation_days_limit", 0)
    )
    GITLAB_RMV_SRC_BRANCH = config["gitlab"]["config"]["remove_source"]
    GITLAB_MENTIONS_LIST = config["gitlab"]["config"].get("mentions")
    GITLAB_MENTIONS_ACCESS_LEVEL = int(
        config["gitlab"]["config"].get("mentions_access_level")
    )
    GITLAB_MR_KEYWORD = config["gitlab"]["config"]["keyword"]
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

# G2SProject namedtuple configuration
G2SProject = namedtuple(
    "G2SProject",
    [
        "pid",
        "full_path",
        "name",
        "group",
        "mrs_enabled",
        "created_at",
        "name_with_namespace",
        "has_sentryclirc_file",
        "has_dsn",
        "sentryclirc_mr_state",
        "dsn_mr_state",
    ],
)

# Statistics configuration
G2S_STATS: List[Tuple[str, int]] = [
    ("not_in_g2s_cases", 0),
    ("mr_sentryclirc_waiting", 0),
    ("mr_dsn_waiting", 0),
    ("mr_disabled", 0),
    ("mr_sentryclirc_created", 0),
    ("mr_dsn_created", 0),
    ("mr_sentryclirc_closed", 0),
    ("mr_dsn_closed", 0),
]

# GraphQL Queries.
GRAPHQL_LIST_PROJECTS_QUERY = {
    "name": "PROJECTS_QUERY",
    "instance": "projects",
    "body": """
{
    projects%s {
        edges {
            node {
                id
                fullPath
                name
                createdAt
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

GRAPHQL_FETCH_PROJECT_QUERY = {
    "name": "PROJECTS_QUERY",
    "instance": "projects",
    "body": """
{
    project(fullPath: "%s") {
        id
        fullPath
        name
        createdAt
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
""",
}
GRAPHQL_TEST_QUERY = {
    "name": "TEST_QUERY",
    "instance": "projects",
    "body": """
{
    project(fullPath: "none") {
        id
        fullPath
        name
        createdAt
        mergeRequestsEnabled
        group {
            name
        }
        repository {
            blobs {
                nodes {
                    name
                    rawTextBlob
                }
            }
        }
        mergeRequests {
            nodes {
                id
                title
                state
            }
        }
    }
}
""",
}
