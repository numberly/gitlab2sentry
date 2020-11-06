import json

import pytest
from requests import Response

from gitlab2sentry.exceptions import (
    SentryProjectCreationFailed,
    SentryProjectKeyIDNotFound,
)
from gitlab2sentry.resources import TEST_SENTRY_DSN
from tests.conftest import TEST_GROUP_NAME, TEST_PROJECT_NAME

STATUS_CODE, DETAIL = 400, b'{"msg": "error_details"}'


def mocked_response(status_code):
    response = Response()
    response._content = DETAIL
    response.status_code = status_code
    return response


def test_get_json(sentry_provider_fixture):
    assert sentry_provider_fixture._client._get_json(mocked_response(STATUS_CODE)) == (
        STATUS_CODE,
        json.loads(DETAIL.decode()),
    )


def test_simple_request(sentry_provider_fixture, mocker):
    mocker.patch("requests.post", return_value=mocked_response(200))
    assert sentry_provider_fixture._client.simple_request("post", "", None)
    mocker.patch("requests.put", return_value=mocked_response(200))
    assert sentry_provider_fixture._client.simple_request("put", "", None)

    mocker.patch("requests.get", return_value=mocked_response(200))
    assert sentry_provider_fixture._client.simple_request("get", "", None)


def test_get_or_create_team(sentry_provider_fixture, mocker):
    mocker.patch("requests.post", return_value=mocked_response(404))
    mocker.patch("requests.get", return_value=mocked_response(201))
    assert sentry_provider_fixture._get_or_create_team(TEST_GROUP_NAME) == json.loads(
        DETAIL.decode()
    )

    mocker.patch("requests.post", return_value=mocked_response(200))
    assert sentry_provider_fixture._get_or_create_team(TEST_GROUP_NAME) == json.loads(
        DETAIL.decode()
    )

    mocker.patch("requests.post", return_value=mocked_response(404))
    mocker.patch("requests.get", return_value=mocked_response(200))
    assert sentry_provider_fixture._get_or_create_team(TEST_GROUP_NAME) is None


def test_get_or_create_project(sentry_provider_fixture, mocker):
    mocker.patch("requests.post", return_value=mocked_response(404))
    mocker.patch("requests.get", return_value=mocked_response(201))
    assert sentry_provider_fixture.get_or_create_project(
        TEST_GROUP_NAME, TEST_PROJECT_NAME
    ) == json.loads(DETAIL.decode())

    mocker.patch("requests.get", return_value=mocked_response(200))
    assert sentry_provider_fixture.get_or_create_project(
        TEST_GROUP_NAME, TEST_PROJECT_NAME
    ) == json.loads(DETAIL.decode())

    mocker.patch("requests.get", return_value=mocked_response(400))
    with pytest.raises(SentryProjectCreationFailed):
        assert sentry_provider_fixture.get_or_create_project(
            TEST_GROUP_NAME, TEST_PROJECT_NAME
        )


def test_get_dsn_and_key_id(sentry_provider_fixture, mocker):
    response = Response()
    detail = b"[{}]"
    decoded_detail = json.loads(detail.decode())
    response._content = detail
    response.status_code = 400

    mocker.patch("requests.get", return_value=response)
    assert sentry_provider_fixture._get_dsn_and_key_id(TEST_PROJECT_NAME) == (
        None,
        None,
    )

    response = Response()
    detail = b"[{}]"
    decoded_detail = json.loads(detail.decode())
    response._content = detail
    response.status_code = 200

    mocker.patch("requests.get", return_value=response)
    with pytest.raises(SentryProjectKeyIDNotFound):
        assert sentry_provider_fixture._get_dsn_and_key_id(TEST_PROJECT_NAME)

    response = Response()
    detail = b'[{"dsn":{"public": "test-dsn"}, "id": "test_id"}]'
    decoded_detail = json.loads(detail.decode())
    response._content = detail
    response.status_code = 200

    mocker.patch("requests.get", return_value=response)
    assert sentry_provider_fixture._get_dsn_and_key_id(TEST_PROJECT_NAME) == (
        decoded_detail[0]["dsn"]["public"],
        decoded_detail[0]["id"],
    )


def test_set_rate_limit_for_key(sentry_provider_fixture, mocker):
    mocker.patch.object(
        sentry_provider_fixture,
        attribute="_get_dsn_and_key_id",
        return_value=(TEST_SENTRY_DSN, "result"),
    )
    mocker.patch.object(
        sentry_provider_fixture._client,
        attribute="simple_request",
        return_value=(200, "result"),
    )
    assert (
        sentry_provider_fixture.set_rate_limit_for_key(TEST_PROJECT_NAME)
        == TEST_SENTRY_DSN
    )

    mocker.patch.object(
        sentry_provider_fixture._client,
        attribute="simple_request",
        return_value=(400, "result"),
    )
    assert sentry_provider_fixture.set_rate_limit_for_key(TEST_PROJECT_NAME) is None

    mocker.patch.object(
        sentry_provider_fixture,
        attribute="_get_dsn_and_key_id",
        side_effect=SentryProjectKeyIDNotFound(),
    )
    assert sentry_provider_fixture.set_rate_limit_for_key(TEST_PROJECT_NAME) is None


def test_ensure_sentry_team(sentry_provider_fixture, mocker):
    mocker.patch.object(
        sentry_provider_fixture, attribute="_get_or_create_team", return_value=True
    )
    assert sentry_provider_fixture.ensure_sentry_team(TEST_GROUP_NAME)

    mocker.patch.object(
        sentry_provider_fixture, attribute="_get_or_create_team", return_value=False
    )
    assert not sentry_provider_fixture.ensure_sentry_team(TEST_GROUP_NAME)
