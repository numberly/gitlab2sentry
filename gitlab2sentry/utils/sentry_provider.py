import json
import logging
from typing import Any, Dict, Optional, Tuple

import requests
from requests import Response
from slugify import slugify

from gitlab2sentry.exceptions import (
    SentryProjectCreationFailed,
    SentryProjectKeyIDNotFound,
)
from gitlab2sentry.resources import SENTRY_ORG_SLUG, SENTRY_TOKEN, SENTRY_URL


class SentryAPIClient:
    def __init__(
        self,
        base_url: Optional[str] = SENTRY_URL,
        token: Optional[str] = SENTRY_TOKEN,
    ):
        self.base_url = base_url
        self.url = "{}/api/0/{}"
        self.headers = {"Authorization": f"Bearer {token}"}

    def __str__(self) -> str:
        return "<SentryAPIClient>"

    def _get_json(self, response: Response) -> Tuple[int, Any]:
        try:
            return response.status_code, response.json()
        except json.JSONDecodeError as json_error:
            logging.warning(
                "{}: Error on request suffix: {}".format(
                    self.__str__(), str(json_error)
                )
            )
            return 400, None

    def simple_request(
        self,
        method: str,
        suffix: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Tuple[int, Any]:
        url = self.url.format(self.base_url, suffix)
        logging.debug("{} simple {} request to {}".format(self.__str__(), method, url))
        if method == "post":
            return self._get_json(requests.post(url, data=data, headers=self.headers))
        elif method == "put":
            return self._get_json(requests.put(url, data=data, headers=self.headers))
        else:
            return self._get_json(requests.get(url, headers=self.headers))


class SentryProvider:
    def __init__(
        self,
        url: Optional[str] = SENTRY_URL,
        token: Optional[str] = SENTRY_TOKEN,
        org_slug: Optional[str] = SENTRY_ORG_SLUG,
    ):
        self.url = url
        self.org_slug = org_slug
        self._client = SentryAPIClient(url, token)

    def __str__(self) -> str:
        return "<SentryProvider>"

    def _get_or_create_team(self, team_name: str) -> Optional[Dict[str, Any]]:
        team_slug = slugify(team_name)
        status_code, result = self._client.simple_request(
            "get", "teams/{}/{}/".format(self.org_slug, team_slug)
        )

        if status_code != 200:
            return self._client.simple_request(
                "post",
                "organizations/{}/teams/".format(self.org_slug),
                {
                    "name": team_name,
                    "slug": team_slug,
                },
            )[1]

        if status_code != 201:
            return None

        logging.info("{}: Team {} created!".format(self.__str__(), team_name))
        return result

    def get_or_create_project(
        self, group_name: str, project_name: str
    ) -> Optional[Dict[str, Any]]:

        project_slug = slugify(project_name).lower()
        status_code, result = self._client.simple_request(
            "get", "projects/{}/{}/".format(self.org_slug, project_slug)
        )
        # Create if project not found
        if status_code == 404:
            status_code, result = self._client.simple_request(
                "post",
                "teams/{}/{}/projects/".format(self.org_slug, group_name),
                {
                    "name": project_name,
                    "slug": project_slug,
                },
            )

        if status_code == 201:
            logging.info(
                "{}: [Creating] Sentry project {}".format(self.__str__(), project_name)
            )
        elif status_code == 200:
            logging.info(
                "{}: [Skipping] Sentry project {} exists".format(
                    self.__str__(), project_name
                )
            )
        else:
            raise SentryProjectCreationFailed(result)

        return result

    def _get_dsn_and_key_id(self, project_slug: str) -> tuple:
        status_code, result = self._client.simple_request(
            "get",
            "projects/{}/{}/keys/".format(self.org_slug, project_slug),
        )

        if status_code != 200:
            return None, None
        if (
            result
            and len(result) > 0
            and result[0].get("dsn", None)
            and result[0]["dsn"].get("public", None)
            and result[0].get("id", None)
        ):
            return result[0]["dsn"]["public"], result[0]["id"]
        else:
            raise SentryProjectKeyIDNotFound(result)

    def set_rate_limit_for_key(self, project_slug: str) -> Optional[str]:
        try:
            dsn, key = self._get_dsn_and_key_id(project_slug)
            status_code, result = self._client.simple_request(
                "put",
                "projects/{}/{}/keys/{}/".format(self.org_slug, project_slug, key),
                {"rateLimit": {"window": 60, "count": 300}},
            )
        except SentryProjectKeyIDNotFound as key_id_err:
            logging.warning(
                "{}: Project {} - Sentry key id not found: {}".format(
                    self.__str__(),
                    project_slug,
                    key_id_err,
                )
            )
            return None

        if status_code != 200:
            return None
        return dsn

    def ensure_sentry_team(self, team_name: str) -> bool:
        logging.info(
            "{}: Ensuring team {} exists on sentry".format(self.__str__(), team_name)
        )
        if self._get_or_create_team(team_name):
            return True
        else:
            return False
