import logging
from typing import Tuple

import requests
from slugify import slugify
from gitlab.v4.objects import Project

class SentryProvider:
    def __init__(self, url, *args, **kwargs):
        self.url = url
        self.token = kwargs["auth_token"]
        self.org_slug = kwargs["org_slug"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def __str__(self):
        return "<SentryProvider>"

    def get_projects(self):
        url = f"{self.url}/api/0/projects/"
        while True:
            r = requests.get(
                url,
                headers=self.headers,
            )
            yield r.json()
            if r.links["next"]["results"] == "true":
                url = r.links["next"]["url"]
            else:
                break

    def _create_or_get_team(self, team):
        team_slug = slugify(team)
        r = requests.post(
            f"{self.url}/api/0/organizations/{self.org_slug}/teams/",
            headers=self.headers,
            data={
                "name": team,
                "slug": team_slug,
            },
        )
        result = r.json()
        if r.status_code != 201:
            if r.status_code == 409:
                r = requests.get(
                    f"{self.url}/api/0/teams/{self.org_slug}/{team_slug}/",
                    headers=self.headers,
                )
                return r.json()
            return None

        logging.info(f"{self.__str__()}team {team} created!")
        return result

    def get_project(self, team, project_slug):
        r = requests.get(
            f"{self.url}/api/0/projects/{self.org_slug}/{project_slug}/",
            headers=self.headers,
        )
        if r.status_code != 200:
            return None
        return r.json()

    def create_or_get_project(self, team, project):
        project_slug = slugify(project).lower()
        data = {
            "name": project,
            "slug": project_slug,
        }
        r = requests.post(
            f"{self.url}/api/0/teams/{self.org_slug}/{team}/projects/",
            headers=self.headers,
            data=data,
        )
        result = r.json()
        if r.status_code != 201:
            if r.status_code == 409:
                return self.get_project(team, project_slug)
            raise Exception(result)

        return result

    def get_dsn_and_key_id(self, project_slug: str) -> Tuple[str, int]:
        r = requests.get(
            f"{self.url}/api/0/projects/{self.org_slug}/{project_slug}/keys/",
            headers=self.headers,
        )
        if r.status_code != 200:
            return None
        
        response = r.json()
        
        return response[0]["dsn"]["public"], response[0]["id"]


    def set_rate_limit_for_key(self, project: str) -> str:
        dsn, key = self._get_dsn_and_key_id(project)
        data = {"rateLimit": {"window": 60, "count": 300}}
        url = f"{self.url}/api/0/projects/{self.org_slug}/{project}/keys/{key}/"
        r = requests.put(
            f"{self.url}/api/0/projects/{self.org_slug}/{project}/keys/{key}/",
            headers=self.headers,
            json=data,
        )
        if r.status_code != 200:
            return None
        return dsn

    def ensure_sentry_team(self, team_name: str):
        logging.info(
            f"{self.__str__()}: Ensuring team {team_name} exists on sentry"
        )
        self._create_or_get_team(team_name)