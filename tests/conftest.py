from datetime import datetime, timedelta

import pytest
import pytz

from gitlab2sentry import Gitlab2Sentry
from gitlab2sentry.resources import (
    DSN_MR_CONTENT,
    DSN_MR_TITLE,
    GITLAB_GROUP_IDENTIFIER,
    GITLAB_PROJECT_CREATION_LIMIT,
    SENTRYCLIRC_FILEPATH,
    SENTRYCLIRC_MR_CONTENT,
    SENTRYCLIRC_MR_TITLE,
    TEST_SENTRY_DSN,
    TEST_SENTRY_URL,
    G2SProject,
)
from gitlab2sentry.utils.gitlab_provider import GitlabProvider, GraphQLClient
from gitlab2sentry.utils.sentry_provider import SentryProvider

TEST_PROJECT_NAME = "test"
TEST_GROUP_NAME = f"{GITLAB_GROUP_IDENTIFIER}test"
CURRENT_TIME = datetime.strftime(datetime.now(pytz.UTC), "%Y-%m-%dT%H:%M:%SZ")
OLD_TIME = datetime.strftime(
    (datetime.now(pytz.UTC) - timedelta(days=(GITLAB_PROJECT_CREATION_LIMIT + 1))),
    "%Y-%m-%dT%H:%M:%SZ",
)


@pytest.fixture
def g2s_fixture():
    yield Gitlab2Sentry()


@pytest.fixture
def gql_client_fixture():
    yield GraphQLClient()


@pytest.fixture
def gitlab_provider_fixture():
    yield GitlabProvider()


@pytest.fixture
def sentry_provider_fixture():
    yield SentryProvider()


class TestGitlabMember:
    def __init__(self, username, access_level, state):
        self.username = username
        self.access_level = access_level
        self.state = state


TEST_GITLAB_PROJECT_MEMBERS = [
    TestGitlabMember("active_user", 40, "active"),
    TestGitlabMember("blocked_user", 40, "blocked")
]


class TestGitlabProject:
    def __init__(self):
        self.members = TestGitlabMemberManager()


class TestGitlabMemberManager:
    def list(self, all=True, iterator=True):
        return TEST_GITLAB_PROJECT_MEMBERS


@pytest.fixture
def gitlab_project_fixture():
    yield TestGitlabProject()


def create_test_g2s_project(**kwargs):
    return G2SProject(
        1,
        f"{TEST_GROUP_NAME}/{TEST_PROJECT_NAME}",
        TEST_PROJECT_NAME,
        TEST_GROUP_NAME,
        kwargs["mrs_enabled"],
        CURRENT_TIME,
        f"{TEST_GROUP_NAME} / {TEST_PROJECT_NAME}",
        kwargs["has_sentryclirc_file"],
        kwargs["has_dsn"],
        kwargs["sentryclirc_mr_state"],
        kwargs["dsn_mr_state"],
    )


def create_graphql_json_object(**kwargs):
    response_dict = {
        "node": {
            "id": "gid://gitlab/Project/0001",
            "fullPath": f"{TEST_GROUP_NAME}/{TEST_PROJECT_NAME}",
            "name": TEST_PROJECT_NAME,
            "mergeRequestsEnabled": kwargs["mrs_enabled"],
            "group": {"name": kwargs.get("group", TEST_GROUP_NAME)},
            "mergeRequests": {"nodes": []},
        }
    }
    response_dict["node"]["createdAt"] = kwargs.get("created_at", CURRENT_TIME)
    if not kwargs.get("no_repository", False):
        response_dict["node"]["repository"] = {"blobs": {"nodes": []}}

    if kwargs["has_sentryclirc_file"]:
        if kwargs["has_dsn"]:
            blob_item = {
                "name": SENTRYCLIRC_FILEPATH,
                "rawTextBlob": DSN_MR_CONTENT.format(
                    sentry_url=TEST_SENTRY_URL,
                    dsn=TEST_SENTRY_DSN,
                    project_slug=TEST_PROJECT_NAME
                ),
            }
        else:
            blob_item = {
                "name": SENTRYCLIRC_FILEPATH,
                "rawTextBlob": SENTRYCLIRC_MR_CONTENT.format(
                    sentry_url=TEST_SENTRY_URL
                ),
            }
        response_dict["node"]["repository"]["blobs"]["nodes"].append(blob_item)

    if kwargs["sentryclirc_mr_state"]:
        sentryclirc_mr = {
            "id": "gid://gitlab/MergeRequest/0001",
            "title": SENTRYCLIRC_MR_TITLE.format(
                project_name=response_dict["node"]["name"]
            ),
            "state": kwargs["sentryclirc_mr_state"],
        }
        response_dict["node"]["mergeRequests"]["nodes"].append(sentryclirc_mr)

    if kwargs["dsn_mr_state"]:
        dsn_mr = {
            "id": "gid://gitlab/MergeRequest/0001",
            "title": DSN_MR_TITLE.format(project_name=response_dict["node"]["name"]),
            "state": kwargs["dsn_mr_state"],
        }
        response_dict["node"]["mergeRequests"]["nodes"].append(dsn_mr)
    return response_dict


@pytest.fixture
def g2s_new_project():
    yield create_test_g2s_project(
        mrs_enabled=True,
        has_sentryclirc_file=False,
        has_dsn=False,
        sentryclirc_mr_state=None,
        dsn_mr_state=None,
    )


@pytest.fixture
def g2s_disabled_mr_project():
    yield create_test_g2s_project(
        mrs_enabled=False,
        has_sentryclirc_file=False,
        has_dsn=False,
        sentryclirc_mr_state=None,
        dsn_mr_state=None,
    )


@pytest.fixture
def g2s_sentryclirc_mr_closed_project():
    yield create_test_g2s_project(
        mrs_enabled=True,
        has_sentryclirc_file=False,
        has_dsn=False,
        sentryclirc_mr_state="closed",
        dsn_mr_state=None,
    )


@pytest.fixture
def g2s_sentryclirc_mr_open_project():
    yield create_test_g2s_project(
        mrs_enabled=True,
        has_sentryclirc_file=False,
        has_dsn=False,
        sentryclirc_mr_state="opened",
        dsn_mr_state=None,
    )


@pytest.fixture
def g2s_sentryclirc_mr_merged_project():
    yield create_test_g2s_project(
        mrs_enabled=True,
        has_sentryclirc_file=True,
        has_dsn=False,
        sentryclirc_mr_state="merged",
        dsn_mr_state=None,
    )


@pytest.fixture
def g2s_dsn_mr_open_project():
    yield create_test_g2s_project(
        mrs_enabled=True,
        has_sentryclirc_file=True,
        has_dsn=False,
        sentryclirc_mr_state="merged",
        dsn_mr_state="opened",
    )


@pytest.fixture
def g2s_dsn_mr_closed_project():
    yield create_test_g2s_project(
        mrs_enabled=True,
        has_sentryclirc_file=True,
        has_dsn=False,
        sentryclirc_mr_state="merged",
        dsn_mr_state="closed",
    )


@pytest.fixture
def g2s_sentry_project():
    yield create_test_g2s_project(
        mrs_enabled=True,
        has_sentryclirc_file=True,
        has_dsn=True,
        sentryclirc_mr_state="merged",
        dsn_mr_state="merged",
    )


@pytest.fixture
def payload_new_project():
    yield create_graphql_json_object(
        mrs_enabled=True,
        has_sentryclirc_file=False,
        has_dsn=False,
        sentryclirc_mr_state=None,
        dsn_mr_state=None,
    )


@pytest.fixture
def payload_old_project():
    yield create_graphql_json_object(
        mrs_enabled=True,
        has_sentryclirc_file=False,
        has_dsn=False,
        sentryclirc_mr_state=None,
        dsn_mr_state=None,
        created_at=OLD_TIME,
    )


@pytest.fixture
def payload_mrs_disabled_project():
    yield create_graphql_json_object(
        mrs_enabled=False,
        has_sentryclirc_file=False,
        has_dsn=False,
        sentryclirc_mr_state=None,
        dsn_mr_state=None,
    )


@pytest.fixture
def payload_no_group_project():
    yield create_graphql_json_object(
        mrs_enabled=True,
        group=None,
        has_sentryclirc_file=False,
        has_dsn=False,
        sentryclirc_mr_state=None,
        dsn_mr_state=None,
    )


@pytest.fixture
def payload_no_repository_project():
    yield create_graphql_json_object(
        mrs_enabled=True,
        no_repository=True,
        has_sentryclirc_file=False,
        has_dsn=False,
        sentryclirc_mr_state=None,
        dsn_mr_state=None,
    )


@pytest.fixture
def payload_sentryclirc_mr_open_project():
    yield create_graphql_json_object(
        mrs_enabled=True,
        has_sentryclirc_file=False,
        has_dsn=False,
        sentryclirc_mr_state="opened",
        dsn_mr_state=None,
    )


@pytest.fixture
def payload_sentryclirc_mr_closed_project():
    yield create_graphql_json_object(
        mrs_enabled=True,
        has_sentryclirc_file=False,
        has_dsn=False,
        sentryclirc_mr_state="closed",
        dsn_mr_state=None,
    )


@pytest.fixture
def payload_sentryclirc_mr_merged_project():
    yield create_graphql_json_object(
        mrs_enabled=True,
        has_sentryclirc_file=True,
        has_dsn=False,
        sentryclirc_mr_state="merged",
        dsn_mr_state=None,
    )


@pytest.fixture
def payload_dsn_mr_open_project():
    yield create_graphql_json_object(
        mrs_enabled=True,
        has_sentryclirc_file=True,
        has_dsn=False,
        sentryclirc_mr_state="merged",
        dsn_mr_state="opened",
    )


@pytest.fixture
def payload_dsn_mr_closed_project():
    yield create_graphql_json_object(
        mrs_enabled=True,
        has_sentryclirc_file=True,
        has_dsn=False,
        sentryclirc_mr_state="merged",
        dsn_mr_state="closed",
    )


@pytest.fixture
def payload_sentry_project():
    yield create_graphql_json_object(
        mrs_enabled=True,
        has_sentryclirc_file=True,
        has_dsn=True,
        sentryclirc_mr_state="merged",
        dsn_mr_state="merged",
    )
