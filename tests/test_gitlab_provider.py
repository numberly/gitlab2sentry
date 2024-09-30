from datetime import datetime

import aiohttp
from gitlab import Gitlab
from gql.transport.aiohttp import AIOHTTPTransport

from gitlab2sentry.resources import (
    GRAPHQL_FETCH_PROJECT_QUERY,
    GRAPHQL_LIST_PROJECTS_QUERY,
    settings,
)
from tests.conftest import CURRENT_TIME, GRAPHQL_TEST_QUERY


def test_get_transport(gql_client_fixture):
    assert isinstance(
        gql_client_fixture._get_transport(settings.gitlab_url, settings.gitlab_token),
        AIOHTTPTransport,
    )


def test_query(gql_client_fixture, payload_new_project, mocker):
    mocker.patch.object(
        gql_client_fixture._client,
        attribute="execute",
        return_value=[payload_new_project],
    )
    assert gql_client_fixture._query(
        payload_new_project["node"]["name"], GRAPHQL_TEST_QUERY["body"]
    )
    mocker.patch.object(
        gql_client_fixture._client,
        attribute="execute",
        side_effect=aiohttp.client_exceptions.ClientResponseError(None, None),
    )
    assert not gql_client_fixture._query(
        payload_new_project["node"]["name"], GRAPHQL_TEST_QUERY["body"]
    )


def test_project_fetch_query(gql_client_fixture, payload_new_project, mocker):
    mocker.patch.object(
        gql_client_fixture._client,
        attribute="execute",
        return_value=[payload_new_project],
    )
    assert (
        gql_client_fixture.project_fetch_query(GRAPHQL_FETCH_PROJECT_QUERY)[0]
        == payload_new_project
    )


def test_project_list_query(gql_client_fixture, payload_new_project, mocker):
    mocker.patch.object(
        gql_client_fixture._client,
        attribute="execute",
        return_value=[payload_new_project],
    )
    assert (
        gql_client_fixture.project_list_query(GRAPHQL_LIST_PROJECTS_QUERY, None)[0]
        == payload_new_project
    )


def test_get_gitlab(gitlab_provider_fixture):
    assert isinstance(
        gitlab_provider_fixture._get_gitlab(settings.gitlab_url, settings.gitlab_token), Gitlab
    )


def test_get_update_limit(gitlab_provider_fixture):
    if settings.gitlab_project_creation_limit:
        assert (
            datetime.now() - gitlab_provider_fixture._get_update_limit()
        ).days - settings.gitlab_project_creation_limit <= 1
    else:
        assert not gitlab_provider_fixture._get_update_limit()


def test_from_iso_to_datetime(gitlab_provider_fixture):
    assert isinstance(
        gitlab_provider_fixture._from_iso_to_datetime(CURRENT_TIME), datetime
    )


def test_get_default_mentions(gitlab_provider_fixture, gitlab_project_fixture):
    _mentioned_members = gitlab_provider_fixture._get_default_mentions(
        gitlab_project_fixture
    ).split(", ")
    _project_non_blocked_members = [
        member
        for member in gitlab_project_fixture.members_all.list()
        if member.state != "blocked"
    ]
    assert len(_mentioned_members) == len(_project_non_blocked_members)


def test_get_project(gitlab_provider_fixture, mocker):
    mocker.patch.object(
        gitlab_provider_fixture._gql_client,
        attribute="project_fetch_query",
        return_value=True,
    )
    assert gitlab_provider_fixture.get_project(GRAPHQL_FETCH_PROJECT_QUERY) is True


def test_get_all_projects(
    gitlab_provider_fixture, payload_new_project, payload_old_project, mocker
):
    mocker.patch.object(
        gitlab_provider_fixture._gql_client,
        attribute="project_list_query",
        side_effect=[
            {
                GRAPHQL_LIST_PROJECTS_QUERY["instance"]: {
                    "edges": [payload_new_project],
                    "pageInfo": {"endCursor": "first-cursor", "hasNextPage": True},
                }
            },
            {
                GRAPHQL_LIST_PROJECTS_QUERY["instance"]: {
                    "edges": [payload_new_project],
                    "pageInfo": {"endCursor": None, "hasNextPage": False},
                }
            },
        ],
    )
    assert (
        len(
            [
                result_page
                for result_page in gitlab_provider_fixture.get_all_projects(
                    GRAPHQL_LIST_PROJECTS_QUERY
                )
            ]
        )
        == 2
    )

    mocker.patch.object(
        gitlab_provider_fixture._gql_client,
        attribute="project_list_query",
        side_effect=[
            {
                GRAPHQL_LIST_PROJECTS_QUERY["instance"]: {
                    "edges": [payload_old_project],
                    "pageInfo": {"endCursor": "first-cursor", "hasNextPage": True},
                }
            },
            {
                GRAPHQL_LIST_PROJECTS_QUERY["instance"]: {
                    "edges": [payload_old_project],
                    "pageInfo": {"endCursor": None, "hasNextPage": False},
                }
            },
        ],
    )
    assert (
        len(
            [
                result_page
                for result_page in gitlab_provider_fixture.get_all_projects(
                    GRAPHQL_LIST_PROJECTS_QUERY
                )
            ]
        )
        == 1
    )
