import logging
import os
from collections import namedtuple
from typing import List, Tuple

try:
    ENV = os.getenv("ENV", "production")
    TEST_SENTRY_URL = "http://sentry.test.com"
    TEST_SENTRY_DSN = "http://test.sentry.test.com"
    TEST_SENTRY_TOKEN = "test-token"
    TEST_GITLAB_URL = "http://test-gitlab-url"
    TEST_GITLAB_TOKEN = "test-token"

    # Sentry configuration
    SENTRY_URL = TEST_SENTRY_URL if ENV == "test" else os.environ["SENTRY_URL"]
    SENTRY_TOKEN = TEST_SENTRY_TOKEN if ENV == "test" else os.environ["SENTRY_TOKEN"]
    SENTRY_DSN = TEST_SENTRY_DSN if ENV == "test" else os.environ["SENTRY_DSN"]
    SENTRY_ENV = os.getenv("SENTRY_ENV", "production")
    SENTRY_ORG_SLUG = os.environ["SENTRY_ORG_SLUG"]

    # DSN MR configuration.
    DSN_MR_CONTENT = os.environ["GITLAB_DSN_MR_CONTENT"]
    DSN_BRANCH_NAME = os.environ["GITLAB_DSN_MR_BRANCH_NAME"]
    DSN_MR_TITLE = os.environ["GITLAB_DSN_MR_TITLE"]
    DSN_MR_DESCRIPTION = os.environ["GITLAB_DSN_MR_DESCRIPTION"]

    # Sentryclirc MR configuration.
    SENTRYCLIRC_MR_CONTENT = os.environ["GITLAB_SENTRYCLIRC_MR_CONTENT"]
    SENTRYCLIRC_BRANCH_NAME = os.environ["GITLAB_SENTRYCLIRC_MR_BRANCH_NAME"]
    SENTRYCLIRC_MR_TITLE = os.environ["GITLAB_SENTRYCLIRC_MR_TITLE"]
    SENTRYCLIRC_FILEPATH = os.environ["GITLAB_SENTRYCLIRC_MR_FILEPATH"]
    SENTRYCLIRC_COM_MSG = os.environ["GITLAB_SENTRYCLIRC_MR_COMMIT_MSG"]
    SENTRYCLIRC_MR_DESCRIPTION = os.environ["GITLAB_SENTRYCLIRC_MR_DESCRIPTION"]

    # Gitlab Configuration.
    GITLAB_URL = TEST_GITLAB_URL if ENV == "test" else os.environ["GITLAB_URL"] 
    GITLAB_TOKEN = TEST_GITLAB_TOKEN if ENV == "test" else os.environ["GITLAB_TOKEN"] 
    GITLAB_GRAPHQL_SUFFIX = os.environ["GITLAB_GRAPHQL_SUFFIX"]
    GITLAB_GRAPHQL_TIMEOUT = int(os.environ["GITLAB_AIOHTTP_TIMEOUT"])
    GITLAB_GRAPHQL_PAGE_LENGTH = int(os.environ["GITLAB_GRAPHQL_PAGE_LENGTH"])
    GITLAB_GROUP_IDENTIFIER = os.getenv("GITLAB_GROUP_IDENTIFIER", "")
    GITLAB_AUTHOR_EMAIL = os.environ["GITLAB_AUTHOR_EMAIL"]
    GITLAB_AUTHOR_NAME = os.environ["GITLAB_AUTHOR_NAME"]
    GITLAB_PROJECT_CREATION_LIMIT = int(os.getenv("GITLAB_CREATION_DAYS_LIMIT", 0))
    GITLAB_RMV_SRC_BRANCH = os.environ["GITLAB_REMOVE_SOURCE"]
    GITLAB_MENTIONS_LIST = os.getenv("GITLAB_MENTIONS")
    GITLAB_MENTIONS_ACCESS_LEVEL = int(os.getenv("GITLAB_MENTIONS_ACCESS_LEVEL", 40))
    GITLAB_MR_KEYWORD = os.environ["GITLAB_MR_KEYWORD"]
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
