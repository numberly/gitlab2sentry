import logging
import json
from typing import Any, Dict, Optional, Tuple

import requests
from requests import Response
from slugify import slugify
from gitlab2sentry.exceptions import SentryProjectCreationFailed, SentryProjectKeyIDNotFound
from gitlab2sentry.resources import SENTRY_URL


class SentryAPIClient:
    def __init__(
        self,
        token: str,
        base_url: Optional[str]=SENTRY_URL,
    ):
        self.base_url = base_url
        self.url = "{}/api/0/{}"
        self.headers = {
            "Authorization": f"Bearer {token}"
        }

    def __str__() -> str:
        return "<SentryAPIClient>"

    def _get_json(self, response: Response) -> Optional[Dict[str, Any]]:
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
        suffix: Optional[str]=None,
        data: Optional[Dict[str, Any]]=None,
    ) -> Dict[str, Any]:
        url = self.url.format(
            self.base_url, suffix
        )
        logging.debug(
            "{} simple {} request to {}".format(
                self.__str__(), method, url
            )
        )
        if method == "post":
            return self._get_json(
                requests.post(
                    url,
                    data=data,
                    headers=self.headers
                )
            )
        elif method == "put":
            return self._get_json(
                requests.put(
                    url,
                    data=data,
                    headers=self.headers
                )
            )
        else:
            return self._get_json(
                requests.get(
                    url,
                    headers=self.headers
                )
            )

    def page_request(self, suffix: str) -> Optional[Dict[str, Any]]:
        url = self.url.format(self.base_url, suffix)
        logging.debug(
            "{} paginated get request to {}".format(
                self.__str__(), url
            )
        )
        while True:
            r = requests.get(
                url,
                headers=self.headers,
            )
            yield self._get_json(r)
            if (hasattr(r, "links") and r.links
                and r.links.get("next", None)
                and r.links["next"].get("results", None)
                and r.links["nex"]["results"] == "true"
            ):
                url = r.links["next"]["url"]
            else:
                break


class SentryProvider:
    def __init__(self, url: str, token: str, org_slug: str):
        self.url = url
        self.org_slug = org_slug
        self._client = SentryAPIClient(token, SENTRY_URL)

    def __str__(self) -> str:
        return "<SentryProvider>"

    def _create_or_get_team(self, team_name: str) -> Optional[Dict[str, Any]]:
        team_slug = slugify(team_name)
        status_code, result = self._client.simple_request(
            "post",
            "/organizations/{}/teams/".format(self.org_slug),
            {
                "name": team_name,
                "slug": team_slug,
            },
        )

        if status_code == 409:
            return self._client.simple_request(
                "get",
                "teams/{}/{}/".format(
                    self.org_slug, team_slug
                )
            )[1]

        if status_code != 201:
            return None

        logging.info(
            "{}: Team {} created!".format(
                self.__str__(), team_name
            )
        )
        return result

    def _get_project(self, project_slug: str) -> Optional[Dict[str, Any]]:
        status_code, result = self._client.simple_request(
            "get",
            "projects/{}/{}/".format(
                self.org_slug, project_slug
            )
        )
        if status_code != 200:
            return None
        return result

    def create_or_get_project(self, team: str, project: str) -> Optional[Dict[str, Any]]:
        project_slug = slugify(project).lower()
        status_code, result = self._client.simple_request(
            "post",
            "teams/{}/{}/projects/".format(
                self.org_slug, team
            ),
            {
                "name": project,
                "slug": project_slug,
            }
        )
        if status_code != 201:
            if status_code == 409:
                return self._get_project(project_slug)
            raise SentryProjectCreationFailed(result)

        return result

    def _get_dsn_and_key_id(self, project_slug: str) -> Tuple[str, int]:
        status_code, result = self._client.simple_request(
            "get",
            "projects/{}/{}/keys/".format(
                self.org_slug, project_slug
            ),
        )

        if status_code != 200:
            return None
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


    def set_rate_limit_for_key(self, project: str) -> Optional[str]:
        dsn, key = self._get_dsn_and_key_id(project)
        status_code, result = self._client.simple_request(
            "put",
            "projects/{}/{}/keys/{}/".format(
                self.org_slug, project, key
            ),
            {
                "rateLimit": {
                    "window": 60,
                    "count": 300
                }
            }
        )

        if status_code != 200:
            return None
        return dsn

    def ensure_sentry_team(self, team_name: str) -> None:
        logging.info(
            "{}: Ensuring team {} exists on sentry".format(
                self.__str__(), team_name
            )
        )
        self._create_or_get_team(team_name)