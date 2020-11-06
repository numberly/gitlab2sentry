import os
import gitlab
import requests
from slugify import slugify
import logging

GITLAB_URL = 'https://gitlab.numberly.in'
GITLAB_TOKEN = os.getenv('GITLAB_TOKEN')
SENTRY_URL = 'https://sentry.numberly.net'
SENTRY_TOKEN = os.getenv('SENTRY_TOKEN')

class Sentry(object):
    def __init__(self, url, *args, **kwargs):
        self.url = url
        self.token = kwargs['auth_token']
        self.org_slug = kwargs['org_slug']
        self.headers = {'Authorization': u'Bearer {}'.format(self.token)}

    def create_or_get_team(self, team):
        team_slug = slugify(team)
        data = {
            'name': team,
            'slug': team_slug,
        }
        r = requests.post(
            '{url}/api/0/organizations/{org_slug}/teams/'.format(
                url=self.url,
                org_slug=self.org_slug
            ),
            headers=self.headers,
            data=data
        )
        result = r.json()
        if r.status_code != 201:
            if r.status_code == 409:
                r = requests.get(
                    '{url}/api/0/teams/{org_slug}/{team}/'.format(
                        url=self.url,
                        org_slug=self.org_slug,
                        team=team_slug,
                    ),
                    headers=self.headers,
                )
                return r.json()
            return None

        logging.info('Team {team} created!'.format(team=team))
        return result

    def create_or_get_project(self, team, project):
        project_slug = slugify(project)
        data = {
            'name': project,
            'slug': project_slug,
        }
        r = requests.post(
            '{url}/api/0/teams/{org_slug}/{team}/projects/'.format(
                url=self.url,
                org_slug=self.org_slug,
                team=team,
            ),
            headers=self.headers,
            data=data
        )
        result = r.json()
        if r.status_code != 201:
            if r.status_code == 409:
                r = requests.get(
                    '{url}/api/0/projects/{org_slug}/{project_slug}/'.format(
                        url=self.url,
                        org_slug=self.org_slug,
                        project_slug=project_slug,
                    ),
                    headers=self.headers,
                    data=data
                )
                return r.json()
            return None

        return result

def main():
    gl = gitlab.Gitlab(GITLAB_URL, private_token=GITLAB_TOKEN)
    s = Sentry(SENTRY_URL, auth_token=SENTRY_TOKEN, org_slug='numberly')

    groups = gl.groups.list(search="team-")
    for group in groups:
        print('Doing team {}'.format(group.full_name))
        team = s.create_or_get_team(group.full_name)
#        for project in projects:
#        s.create_project(team['slug'], 'disintegrator')
        project = s.create_or_get_project('team-infrastructure',
                                          'disintegrator')
        print(project)
        break


if __name__ == '__main__':
    main()
