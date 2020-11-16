import logging
import os
import re
import time

import gitlab
import requests
from slugify import slugify

GITLAB_URL = os.getenv("GITLAB_URL", "https://gitlab.numberly.in")
GITLAB_TOKEN = os.getenv("GITLAB_TOKEN")
SENTRY_URL = os.getenv("SENTRY_URL", "https://sentry.numberly.net")
SENTRY_TOKEN = os.getenv("SENTRY_TOKEN")

PROJECTS_DONE = []
PROJECTS_IGNORE = []

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


class Sentry:
    def __init__(self, url, *args, **kwargs):
        self.url = url
        self.token = kwargs["auth_token"]
        self.org_slug = kwargs["org_slug"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

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

    def get_project(self, team, project_slug):
        r = requests.get(
            f"{self.url}/api/0/projects/{self.org_slug}/{project_slug}/",
            headers=self.headers,
        )
        if r.status_code != 200:
            return None
        return r.json()

    def create_or_get_project(self, team, project):
        project_slug = slugify(project)
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
            return None

        return result

    def get_clients_keys(self, team, project):
        r = requests.get(
            f"{self.url}/api/0/projects/{self.org_slug}/{project}/keys/",
            headers=self.headers,
        )
        if r.status_code != 200:
            return None
        return r.json()


def create_mr(project, branch_name, file_path, content, title, description):
    try:
        project.branches.get(branch_name)
        logging.info("branch already exists, deleting")
        project.branches.delete(branch_name)
    except Exception:
        pass

    project.branches.create({"branch": branch_name, "ref": "master"})
    try:
        f = project.files.get(file_path=file_path, ref="master")
        f.content = content
        f.save(branch=branch_name, commit_message="Udpate .sentryclirc")
    except Exception:
        f = project.files.create(
            {
                "file_path": file_path,
                "branch": branch_name,
                "content": f"{content}",
                "author_email": "gitlab2sentry@numberly.com",
                "author_name": "gitlab2sentry",
                "commit_message": "Update .sentryclirc",
            }
        )
    project.mergerequests.create(
        {
            "source_branch": branch_name,
            "target_branch": "master",
            "title": title,
            "description": description,
        }
    )


def loop(gl, s):
    groups = gl.groups.list(search="team-")
    for group in groups:
        logging.info(f"doing team {group.full_name}")
        s.create_or_get_team(group.full_name)

    projects = gl.projects.list(list=False, all=True)
    for project in projects:
        if not project.path_with_namespace.startswith("team-"):
            continue
        # FIXME: what is toto?
        # if project.path_with_namespace not in toto:
        #    continue
        # transform `<group>/<subnamespace1>/<subnamespace2>/<project>` to
        # <subnamespace1>-<subnamespace2>-<project>
        match = re.search(
            "(?P<team>team-[a-z]+)/(?P<project>.*)", project.path_with_namespace
        )

        group_name = match.group("team")
        project_name = match.group("project")
        logging.info(project_name)
        project_name_slug = slugify(project_name)

        # Initially check if project exists, if yes, append to DONE
        sentry_project = s.get_project(group_name, project_name_slug)
        if sentry_project:
            PROJECTS_DONE.append(project.id)

        # We avoid doing useless requests by checking if it's present
        if project.id in PROJECTS_DONE or project.id in PROJECTS_IGNORE:
            continue

        logging.info("is there any MR?")
        mrs = project.mergerequests.list(
            state="all", search="Add sentry to this project"
        )
        logging.info(mrs)
        # If not MR, we create one
        if not len(mrs):
            logging.info("no mr, create branch")
            content = """## File generated by gitlab2sentry
[defaults]
url = https://sentry.numberly.net/
"""
            msg = (
                "@all Merge this and it will automatically create a Sentry project "
                f"for {project.name_with_namespace} :cookie:"
            )
            create_mr(
                project,
                "auto_add_sentry",
                ".sentryclirc",
                content,
                "Add sentry to this project",
                msg,
            )
            continue
        # Else If MR merged but no sentry, we create sentry and post DSN
        elif len([x for x in mrs if x.state == "merged"]) and sentry_project is None:
            logging.info("MR merge but no project, let's create it")
            sentry_project = s.create_or_get_project(
                group_name,
                project_name,
            )
            logging.info("sentry project created", sentry_project)
            clients_keys = s.get_clients_keys(group_name, sentry_project["slug"])
            logging.info(clients_keys)
            content = f"""## File generated by gitlab2sentry
[defaults]
url = https://sentry.numberly.net/
dsn = {clients_keys[0]['dsn']['public']}
"""
            msg = (
                "@all Congrats, your Sentry project has been created, merge this "
                "to finalize your Sentry integration :clap: :cookie:"
            )
            create_mr(
                project,
                "auto_add_sentry_bis",
                ".sentryclirc",
                content,
                "Finalize your Sentry integration",
                msg,
            )
            PROJECTS_DONE.append(project.id)
        else:
            PROJECTS_IGNORE.append(project.id)


def main():
    while True:
        gl = gitlab.Gitlab(GITLAB_URL, private_token=GITLAB_TOKEN)
        s = Sentry(SENTRY_URL, auth_token=SENTRY_TOKEN, org_slug="numberly")
        loop(gl, s)
        time.sleep(600)


if __name__ == "__main__":
    main()
