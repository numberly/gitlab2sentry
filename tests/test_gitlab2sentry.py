from gitlab2sentry.exceptions import SentryProjectCreationFailed
from gitlab2sentry.resources import settings
from gitlab2sentry.utils import GitlabProvider, SentryProvider
from tests.conftest import TEST_GROUP_NAME


def test_get_gitlab_provider(g2s_fixture):
    assert isinstance(g2s_fixture._get_gitlab_provider(), GitlabProvider)


def test_get_sentry_provider(g2s_fixture):
    assert isinstance(g2s_fixture._get_sentry_provider(), SentryProvider)


def test_ensure_sentry_group(mocker, g2s_fixture):
    mocker.patch.object(
        g2s_fixture.sentry_provider, attribute="ensure_sentry_team", return_values=None
    )
    g2s_fixture._ensure_sentry_group(TEST_GROUP_NAME)
    assert TEST_GROUP_NAME in g2s_fixture.sentry_groups


def test_has_mrs_enabled(g2s_fixture, g2s_new_project, g2s_disabled_mr_project):
    g2s_fixture.run_stats["mr_disabled"] = 0
    assert (
        g2s_fixture._has_mrs_enabled(g2s_new_project)
        and not g2s_fixture._has_mrs_enabled(g2s_disabled_mr_project)
        and g2s_fixture.run_stats["mr_disabled"] == 1
    )


def test_opened_dsn_mr_found(g2s_fixture, g2s_new_project, g2s_dsn_mr_open_project):
    g2s_fixture.run_stats["mr_dsn_waiting"] = 0
    assert (
        g2s_fixture._opened_dsn_mr_found(g2s_dsn_mr_open_project)
        and not g2s_fixture._opened_dsn_mr_found(g2s_new_project)
        and g2s_fixture.run_stats["mr_dsn_waiting"] == 1
    )


def test_opened_sentryclirc_mr_found(
    g2s_fixture, g2s_new_project, g2s_sentryclirc_mr_open_project
):
    g2s_fixture.run_stats["mr_sentryclirc_waiting"] = 0
    assert (
        g2s_fixture._opened_sentryclirc_mr_found(g2s_sentryclirc_mr_open_project)
        and not g2s_fixture._opened_sentryclirc_mr_found(g2s_new_project)
        and g2s_fixture.run_stats["mr_sentryclirc_waiting"] == 1
    )


def test_closed_dsn_mr_found(g2s_fixture, g2s_new_project, g2s_dsn_mr_closed_project):
    g2s_fixture.run_stats["mr_dsn_closed"] = 0
    assert (
        g2s_fixture._closed_dsn_mr_found(g2s_dsn_mr_closed_project)
        and not g2s_fixture._closed_dsn_mr_found(g2s_new_project)
        and g2s_fixture.run_stats["mr_dsn_closed"] == 1
    )


def test_closed_sentryclirc_mr_found(
    g2s_fixture, g2s_new_project, g2s_sentryclirc_mr_closed_project
):
    g2s_fixture.run_stats["mr_sentryclirc_closed"] = 0
    assert (
        g2s_fixture._closed_sentryclirc_mr_found(g2s_sentryclirc_mr_closed_project)
        and not g2s_fixture._closed_sentryclirc_mr_found(g2s_new_project)
        and g2s_fixture.run_stats["mr_sentryclirc_closed"] == 1
    )


def test_get_mr_states(
    g2s_fixture,
    payload_new_project,
    payload_mrs_disabled_project,
    payload_sentryclirc_mr_open_project,
    payload_sentryclirc_mr_closed_project,
    payload_sentryclirc_mr_merged_project,
    payload_dsn_mr_open_project,
    payload_dsn_mr_closed_project,
    payload_sentry_project,
):
    assert g2s_fixture._get_mr_states(
        payload_new_project["node"]["name"],
        payload_new_project["node"]["mergeRequests"]["nodes"],
    ) == (None, None)

    assert g2s_fixture._get_mr_states(
        payload_sentryclirc_mr_open_project["node"]["name"],
        payload_sentryclirc_mr_open_project["node"]["mergeRequests"]["nodes"],
    ) == ("opened", None)

    assert g2s_fixture._get_mr_states(
        payload_mrs_disabled_project["node"]["name"],
        payload_mrs_disabled_project["node"]["mergeRequests"]["nodes"],
    ) == (None, None)

    assert g2s_fixture._get_mr_states(
        payload_sentryclirc_mr_closed_project["node"]["name"],
        payload_sentryclirc_mr_closed_project["node"]["mergeRequests"]["nodes"],
    ) == ("closed", None)

    assert g2s_fixture._get_mr_states(
        payload_sentryclirc_mr_merged_project["node"]["name"],
        payload_sentryclirc_mr_merged_project["node"]["mergeRequests"]["nodes"],
    ) == ("merged", None)

    assert g2s_fixture._get_mr_states(
        payload_dsn_mr_open_project["node"]["name"],
        payload_dsn_mr_open_project["node"]["mergeRequests"]["nodes"],
    ) == ("merged", "opened")

    assert g2s_fixture._get_mr_states(
        payload_dsn_mr_closed_project["node"]["name"],
        payload_dsn_mr_closed_project["node"]["mergeRequests"]["nodes"],
    ) == ("merged", "closed")

    assert g2s_fixture._get_mr_states(
        payload_sentry_project["node"]["name"],
        payload_sentry_project["node"]["mergeRequests"]["nodes"],
    ) == ("merged", "merged")


def test_is_group_project(g2s_fixture, payload_no_group_project, payload_new_project):
    assert g2s_fixture._is_group_project(
        payload_new_project["node"]["group"]
    ) and not g2s_fixture._is_group_project(payload_no_group_project["node"]["group"])


def test_get_sentryclirc_file(
    g2s_fixture,
    payload_new_project,
    payload_sentryclirc_mr_merged_project,
    payload_sentry_project,
):
    assert g2s_fixture._get_sentryclirc_file(
        payload_new_project["node"]["repository"]["blobs"]["nodes"],
    ) == (False, False)

    assert g2s_fixture._get_sentryclirc_file(
        payload_sentryclirc_mr_merged_project["node"]["repository"]["blobs"]["nodes"],
    ) == (True, False)

    assert g2s_fixture._get_sentryclirc_file(
        payload_sentry_project["node"]["repository"]["blobs"]["nodes"],
    ) == (True, True)


def test_has_already_sentry(
    g2s_fixture,
    g2s_new_project,
    g2s_sentry_project,
):
    assert g2s_fixture._has_already_sentry(
        g2s_sentry_project
    ) and not g2s_fixture._has_already_sentry(g2s_new_project)


def test_get_g2s_project(
    g2s_fixture,
    g2s_new_project,
    g2s_sentry_project,
    payload_new_project,
    payload_no_repository_project,
    payload_sentry_project,
):
    assert (
        g2s_fixture._get_g2s_project(payload_new_project["node"])
    ) == g2s_new_project

    assert not (g2s_fixture._get_g2s_project(payload_no_repository_project["node"]))

    assert (
        g2s_fixture._get_g2s_project(payload_sentry_project["node"])
    ) == g2s_sentry_project


def test_get_paginated_projects(g2s_fixture, payload_new_project, mocker):
    mocker.patch.object(
        g2s_fixture.gitlab_provider,
        attribute="get_all_projects",
        return_value=[payload_new_project],
    )
    assert isinstance(g2s_fixture._get_paginated_projects(), list)


def test_get_gitlab_project(g2s_fixture, g2s_new_project, payload_new_project, mocker):
    mocker.patch.object(
        g2s_fixture.gitlab_provider, attribute="get_project", return_value={}
    )
    assert not g2s_fixture._get_gitlab_project(g2s_new_project)

    mocker.patch.object(
        g2s_fixture.gitlab_provider,
        attribute="get_project",
        return_value={"project": payload_new_project["node"]},
    )
    assert g2s_fixture._get_gitlab_project(g2s_new_project.full_path) == g2s_new_project


def test_get_gitlab_groups(g2s_fixture, g2s_new_project, payload_new_project, mocker):
    mocker.patch.object(
        g2s_fixture,
        attribute="_get_paginated_projects",
        return_value=[[payload_new_project]],
    )
    assert g2s_new_project.group in g2s_fixture._get_gitlab_groups().keys()


def test_create_sentry_project(g2s_fixture, payload_new_project, mocker):
    mocker.patch.object(
        g2s_fixture.sentry_provider,
        attribute="get_or_create_project",
        return_value={"name": TEST_GROUP_NAME},
    )
    assert (
        g2s_fixture._create_sentry_project(
            payload_new_project["node"]["fullPath"],
            TEST_GROUP_NAME,
            payload_new_project["node"]["name"],
            payload_new_project["node"]["name"],
        )["name"]
        == TEST_GROUP_NAME
    )

    mocker.patch.object(
        g2s_fixture.sentry_provider,
        attribute="get_or_create_project",
        side_effect=SentryProjectCreationFailed("error"),
    )
    assert not g2s_fixture._create_sentry_project(
        payload_new_project["node"]["fullPath"],
        TEST_GROUP_NAME,
        payload_new_project["node"]["name"],
        payload_new_project["node"]["name"],
    )

    mocker.patch.object(
        g2s_fixture.sentry_provider,
        attribute="get_or_create_project",
        side_effect=Exception("error"),
    )
    assert not g2s_fixture._create_sentry_project(
        payload_new_project["node"]["fullPath"],
        TEST_GROUP_NAME,
        payload_new_project["node"]["name"],
        payload_new_project["node"]["name"],
    )


def test_handle_g2s_project(
    g2s_fixture,
    g2s_new_project,
    g2s_disabled_mr_project,
    g2s_sentryclirc_mr_open_project,
    g2s_sentryclirc_mr_closed_project,
    g2s_sentryclirc_mr_merged_project,
    g2s_dsn_mr_open_project,
    g2s_dsn_mr_closed_project,
    g2s_sentry_project,
    mocker,
):
    assert not g2s_fixture._handle_g2s_project(g2s_sentry_project, TEST_GROUP_NAME)
    assert not g2s_fixture._handle_g2s_project(g2s_disabled_mr_project, TEST_GROUP_NAME)
    assert not g2s_fixture._handle_g2s_project(g2s_dsn_mr_open_project, TEST_GROUP_NAME)
    assert not g2s_fixture._handle_g2s_project(
        g2s_dsn_mr_closed_project, TEST_GROUP_NAME
    )
    assert not g2s_fixture._handle_g2s_project(
        g2s_sentryclirc_mr_open_project, TEST_GROUP_NAME
    )
    assert not g2s_fixture._handle_g2s_project(
        g2s_sentryclirc_mr_closed_project, TEST_GROUP_NAME
    )
    mocker.patch.object(
        g2s_fixture.gitlab_provider,
        attribute="create_sentryclirc_mr",
        return_value=True,
    )
    g2s_fixture.run_stats["mr_sentryclirc_created"] = 0
    assert (
        g2s_fixture._handle_g2s_project(g2s_new_project, TEST_GROUP_NAME)
        and g2s_fixture.run_stats["mr_sentryclirc_created"] == 1
    )
    mocker.patch.object(
        g2s_fixture.sentry_provider,
        attribute="set_rate_limit_for_key",
        return_value=settings.sentry_dsn,
    )
    mocker.patch.object(
        g2s_fixture,
        attribute="_create_sentry_project",
        return_value={"name": TEST_GROUP_NAME, "slug": TEST_GROUP_NAME},
    )
    mocker.patch.object(
        g2s_fixture.gitlab_provider, attribute="create_dsn_mr", return_value=True
    )
    g2s_fixture.run_stats["mr_dsn_created"] = 0
    assert (
        g2s_fixture._handle_g2s_project(
            g2s_sentryclirc_mr_merged_project, TEST_GROUP_NAME
        )
        and g2s_fixture.run_stats["mr_dsn_created"] == 1
    )


def test_update(g2s_fixture, g2s_new_project, mocker):
    mocker.patch.object(
        g2s_fixture, attribute="_get_gitlab_project", return_value=g2s_new_project
    )
    mocker.patch.object(g2s_fixture, attribute="_handle_g2s_project", return_value=None)
    assert g2s_fixture.update(full_path=g2s_new_project.full_path) is None

    mocker.patch.object(
        g2s_fixture,
        attribute="_get_gitlab_groups",
        return_value={TEST_GROUP_NAME: g2s_new_project},
    )
    mocker.patch.object(
        g2s_fixture, attribute="_ensure_sentry_group", return_value=None
    )
    mocker.patch.object(g2s_fixture, attribute="_handle_g2s_project", return_value=None)
    assert g2s_fixture.update() is None
