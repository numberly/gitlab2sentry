import logging

import requests
from slugify import slugify


class Sentry:
    def __init__(self, url, *args, **kwargs):
        self.url = url
        self.token = kwargs["auth_token"]
        self.org_slug = kwargs["org_slug"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def add_project_rule(self, project, rule, frequency):
        logging.info("Sentry add rule")
        project_slug = slugify(project).lower()
        data = {
            "actionMatch": "all",
            "filterMatch": "all",
            "actions": [
                {
                    "id": "sentry.mail.actions.NotifyEmailAction",
                    "targetType": "Team",
                    "targetIdentifier": rule["team_id"],
                }
            ],
            "conditions": [{"id": rule["type"]}],
            "filters": [],
            "name": rule["name"],
            "frequency": frequency,
        }
        if rule.get("interval"):
            data["conditions"][0]["interval"] = rule["interval"]
            data["conditions"][0]["value"] = rule["seen"]
        if rule.get("environment"):
            data["environment"] = rule["environment"]
        r = requests.post(
            f"{self.url}/api/0/projects/{self.org_slug}/{project_slug}/rules/",
            headers=self.headers,
            json=data,
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

    def create_or_get_team(self, team):
        team_slug = slugify(team)
        data = {
            "name": team,
            "slug": team_slug,
        }
        r = requests.post(
            f"{self.url}/api/0/organizations/{self.org_slug}/teams/",
            headers=self.headers,
            data=data,
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

        logging.info(f"team {team} created!")
        return result

    def delete_project_rule(self, project, rule_id):
        logging.info("Sentry delete rule")
        project_slug = slugify(project).lower()
        r = requests.delete(
            f"{self.url}/api/0/projects/{self.org_slug}/{project_slug}/"
            f"rules/{rule_id}/",
            headers=self.headers,
        )
        if r.status_code != 200:
            return None
        return r.json()

    def get_clients_keys(self, team, project):
        r = requests.get(
            f"{self.url}/api/0/projects/{self.org_slug}/{project}/keys/",
            headers=self.headers,
        )
        if r.status_code != 200:
            return None
        return r.json()

    def get_project(self, team, project_slug):
        r = requests.get(
            f"{self.url}/api/0/projects/{self.org_slug}/{project_slug}/",
            headers=self.headers,
        )
        if r.status_code != 200:
            return None
        return r.json()

    def get_projects(self, project):
        logging.info("Sentry get project")
        project_slug = slugify(project).lower()
        r = requests.get(
            f"{self.url}/api/0/organizations/{self.org_slug}/projects/?all_projects=1",
            headers=self.headers,
        )
        if r.status_code != 200:
            return None
        for project in r.json():
            if project["slug"] == project_slug:
                return project

    def get_project_environments(self, project):
        logging.info("Sentry get environments")
        project_slug = slugify(project).lower()
        r = requests.get(
            f"{self.url}/api/0/projects/{self.org_slug}/{project_slug}/environments/",
            headers=self.headers,
        )
        if r.status_code != 200:
            return None
        return r.json()

    def get_project_rules(self, project):
        logging.info("Sentry get project rules")
        r = requests.get(
            f"{self.url}/api/0/organizations/{self.org_slug}/combined-rules/"
            f"?project={project['id']}",
            headers=self.headers,
        )
        if r.status_code != 200:
            return None
        return r.json()

    def get_teams(self):
        logging.info("Sentry get teams")
        r = requests.get(
            f"{self.url}/api/0/organizations/{self.org_slug}/teams/",
            headers=self.headers,
        )
        if r.status_code != 200:
            return None
        return {item["name"]: item for item in r.json()}

    def post_project_team(self, project, team):
        logging.info("Sentry post project team")
        project_slug = slugify(project).lower()
        r = requests.get(
            f"{self.url}/api/0/projects/{self.org_slug}/{project_slug}/teams/{team}/",
            headers=self.headers,
        )
        if r.status_code != 200:
            return None
        return r.json()
