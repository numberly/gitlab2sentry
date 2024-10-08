from collections import namedtuple
from typing import List, Tuple

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    dsn_branch_name: str = Field("auto_add_sentry_dsn")
    dsn_mr_content: str = Field(
        """
    ## File generated by gitlab2sentry
    [defaults]
    url = {sentry_url}
    dsn = {dsn}
    project = {project_slug}
    """
    )
    dsn_mr_description: str = Field(
        """{mentions} Congrats, your Sentry project has been created, merge this to finalize your Sentry integration of {name_with_namespace} :clap: :cookie:"""  # noqa
    )
    dsn_mr_title: str = Field(
        "[gitlab2sentry] Merge me to add your Sentry DSN to {project_name}"
    )
    env: str = Field("production")
    gitlab_author_email: str = Field("default-email@example.com")
    gitlab_author_name: str = Field("Default Author")
    gitlab_graphql_page_length: int = Field(0)
    gitlab_graphql_suffix: str = Field("default-content")
    gitlab_graphql_timeout: int = Field(10)
    gitlab_group_identifier: str = Field("")
    gitlab_mentions: str = Field("", examples=["@foo,@bar"])
    gitlab_mentions_access_level: int = Field(40)
    gitlab_mr_keyword: str = Field("sentry")
    gitlab_mr_label_list: List[str] = Field(["sentry"])
    gitlab_project_creation_limit: int = Field(30)
    gitlab_rmv_src_branch: bool = Field(True)
    gitlab_signed_commit: bool = Field(False)
    gitlab_token: str = Field("default-token")
    gitlab_url: str = Field("http://default-gitlab-url")
    sentry_dsn: str = Field("http://default.sentry.com")
    sentry_env: str = Field("production")
    sentry_org_slug: str = Field("default_org")
    sentry_token: str = Field("default-token")
    sentry_url: str = Field("http://default-sentry-url")
    sentryclirc_branch_name: str = Field("auto_add_sentry")
    sentryclirc_com_msg: str = Field("Update .sentryclirc")
    sentryclirc_filepath: str = Field(".sentryclirc")
    sentryclirc_mr_content: str = Field(
        """
    ## File generated by gitlab2sentry
    [defaults]
    url = {sentry_url}
    """
    )
    sentryclirc_mr_description: str = Field(
        """{mentions} Merge this and it will automatically create a Sentry project for {name_with_namespace} :cookie:"""  # noqa
    )
    sentryclirc_mr_title: str = Field(
        """"[gitlab2sentry] Merge me to add Sentry to {project_name} or close me"""
    )


settings = Settings()  # type: ignore

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
