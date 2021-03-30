import configparser
import io
import logging
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta

import requests
import sentry_sdk
from gitlab import Gitlab
from gitlab.exceptions import GitlabGetError
from slugify import slugify

GITLAB_URL = os.getenv("GITLAB_URL", "https://gitlab.numberly.in")
GITLAB_TOKEN = os.getenv("GITLAB_TOKEN")
SENTRY_URL = os.getenv("SENTRY_URL", "https://sentry.numberly.net")
SENTRY_TOKEN = os.getenv("SENTRY_TOKEN")

ISSUE_TITLE = "[Alerting Sentry]"
MR_TITLE = "[Alerting Sentry] Proposal"
ALERT_NEW_ISSUE = "new_issue"
ALERT_INTERVAL = "issue_interval"
RULES_DEFAULT_FREQUENCY = 30

RULES = {
    "new_issue": {
        "type": "sentry.rules.conditions.first_seen_event.FirstSeenEventCondition",
        "name": "[Gitlab2Sentry] First seen event",
    },
    "issue_interval": {
        "type": "sentry.rules.conditions.event_frequency.EventFrequencyCondition",
        "name": "[Gitlab2Sentry] Event Frequency",
        "interval": "1d",
        "seen": "10",
    },
}
DEFAULT_RULE = ALERT_NEW_ISSUE
INTERVAL = ["1m", "1d", "1w"]
SCRIPT_CRON_HOUR_INTERVAL = 3

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

    def get_project(self, project):
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

    def get_project_environments(self, project):
        logging.info("Sentry get environments")
        project_slug = slugify(project).lower()
        r = requests.get(
            f"{self.url}/api/0/projects/{self.org_slug}/{project_slug}/environments",
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

    def add_project_rule(self, project, rule):
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
            "frequency": RULES_DEFAULT_FREQUENCY,
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
                "author_email": "gitlab2sentry@numberly.com",
                "author_name": "gitlab2sentry",
                "branch": branch_name,
                "commit_message": "Update .sentryclirc",
                "content": f"{content}",
                "file_path": file_path,
            }
        )
    project.mergerequests.create(
        {
            "description": description,
            "remove_source_branch": True,
            "source_branch": branch_name,
            "target_branch": "master",
            "title": title,
        }
    )


def get_sentryclirc(project):
    has_file, has_dsn, sentryclirc = False, False, False
    alerts = []
    try:
        f = project.files.get(file_path=".sentryclirc", ref="master")
    except GitlabGetError:
        pass
    else:
        ff = f.decode()
        sentryclirc = configparser.ConfigParser()
        sentryclirc.read_string(ff.decode())
        sections = sentryclirc.sections()
        has_file = True
        if sentryclirc.has_section("defaults"):
            if sentryclirc.has_option("defaults", "dsn"):
                has_dsn = True
                if any("alert." in section for section in sections):
                    for section in sentryclirc.sections():
                        if "alert." in section:
                            alert = dict()
                            alert["type"] = section.split(".")[1]
                            alert["notify"] = sentryclirc.get(
                                section, "notify", fallback=""
                            )
                            if alert["type"] == ALERT_INTERVAL:
                                alert["seen"] = sentryclirc.get(
                                    section, "seen", fallback=""
                                )
                                alert["interval"] = sentryclirc.get(
                                    section, "interval", fallback=""
                                )
                            alerts.append(alert)
            else:
                logging.debug("Missing dsn")
        else:
            alerts = None

    return has_file, has_dsn, alerts, sentryclirc


def propose_sentry_mr(project, config):
    with io.StringIO() as ss:
        config.write(ss)
        ss.seek(0)
        content = f"## File generated by gitlab2sentry\n{ss.read()}"
    msg = (
        "@all Merge this and it will automatically create a default alert in Sentry "
        f"for {project.name_with_namespace}"
    )
    create_mr(
        project,
        "auto_add_sentry",
        ".sentryclirc",
        content,
        f"[gitlab2sentry] Merge me to add alerting to {project.name} or close me",
        msg,
    )


def test_alert_config(alerts, teams, group, project_name, sentry):
    for alert in alerts:
        if alert["type"] and alert["type"] in RULES:
            atype = alert["type"]
            alert["name"] = RULES[alert["type"]]["name"]
            alert["type"] = RULES[alert["type"]]["type"]
            # Check notify
            if alert.get("notify"):
                if teams.get(alert["notify"]):
                    # is the custom team linked to the project ?
                    if not next(
                        (
                            project
                            for project in teams[alert["notify"]]["projects"]
                            if project["slug"] == project_name
                        ),
                        None,
                    ):
                        sentry.post_project_team(project_name, alert["notify"])

                    alert["team_id"] = teams[alert["notify"]]["id"]
                else:
                    return False
            elif group == "team-uep" and any(
                subteam in project_name for subteam in ["backend", "frontend"]
            ):
                subteam = project_name.split("-")[-1]
                alert["notify"] = f"{group}-{subteam}"
                alert["team_id"] = teams[alert["notify"]]["id"]
            else:
                alert["notify"] = group
                alert["team_id"] = teams[alert["notify"]]["id"]
            # Check interval & seen
            if "interval" in atype:
                if alert.get("interval"):
                    if not alert["interval"] in INTERVAL:
                        return False
                else:
                    alert["interval"] = RULES[atype]["interval"]
                if alert.get("seen"):
                    if not 1 <= int(alert["seen"]) <= 100:
                        return False
                else:
                    alert["interval"] = RULES[atype]["interval"]
            # Get existing dev environnements set in the project
            environments = sentry.get_project_environments(project_name)
            for env in environments:
                if 'production' in env.get('name'):
                    alert["environment"] = env.get('name')
        else:
            return False
    return alerts


def add_new_issue(project):
    description = """The file .sentryclirc has been modified.
It contains a configuration to add alerts on Sentry.
This configuration could not be added because there is an error.
Please, correct this error and close the issue to add this
configuration to sentry.
"""
    project.issues.create(
        {
            "title": f"{ISSUE_TITLE} Syntax Error on .sentryclirc",
            "description": description,
        }
    )


def main():
    # connect to gitlab & sentry
    gitlab = Gitlab(GITLAB_URL, private_token=GITLAB_TOKEN)
    gitlab.auth()
    sentry = Sentry(SENTRY_URL, auth_token=SENTRY_TOKEN, org_slug="numberly")
    logging.info("connect to gitlab & sentry")

    # prepare our run variables
    mr_by_project = defaultdict(list)
    mr_counts = Counter()
    issue_by_project = defaultdict(list)
    issue_counts = Counter()
    run_stats = Counter()

    # get all the MRs we ever done
    logging.info("Getting all MR")
    for mr in gitlab.mergerequests.list(all=True, state="all", scope="created_by_me"):
        if MR_TITLE in mr.title:
            mr_counts[mr.project_id] += 1
            mr_by_project[mr.project_id].append(mr)

    # get all the issues we ever opened
    logging.info("Getting all Issue")
    for issue in gitlab.issues.list(state="opened"):
        issue_counts[issue.project_id] += 1
        issue_by_project[issue.project_id].append(issue)

    # loop for all team gitlab groups
    sentry_groups = set()
    groups = gitlab.groups.list(all=True, include_subgroups=True)
    logging.info("Loop in Groups")
    for group in groups:
        # we are only interested in team groups
        if not group.full_name.startswith("team-"):
            continue

        # TODO: Remove after testing
        if group.id != 1029:
            continue

        sentry_group_name = group.full_name.split("/")[0].strip()

        # ensure each gitlab group has a sentry sibling
        logging.debug(f"handling gitlab group {group.full_name}")
        if sentry_group_name not in sentry_groups:
            sentry_groups.add(sentry_group_name)

        # check every project of the group
        for project in group.projects.list(all=True, archived=False):
            # skip project if MRs are disabled
            if not project.merge_requests_enabled:
                logging.info(
                    f"project {project.name_with_namespace} does not accept MRs"
                )
                run_stats["mr_disabled"] += 1
                continue

            # check sentryclirc presence and dsn in the file
            project = gitlab.projects.get(project.id)
            has_sentryclirc, has_dsn, alerts, sentryclirc = get_sentryclirc(project)
            logging.debug(
                f"project {project.name_with_namespace} "
                f"has_sentryclirc={has_sentryclirc} "
                f"has_dsn={has_dsn}"
                f"alerts={alerts if alerts else ''}"
            )

            # CASE 1 : no dsn and or no sentryclirc, nothing we can do here yet
            if not has_sentryclirc or not has_dsn:
                logging.info(
                    f"project {project.name_with_namespace} doesnt have a sentry "
                    "project yet"
                )
                run_stats["alerting_disable"] += 1
                continue
            # CASE 2 : no alerting set
            elif has_sentryclirc and has_dsn and not alerts:
                logging.info(
                    f"project {project.name_with_namespace} : no alerting "
                    "config detected"
                )
                # check for pending MR
                for mr in mr_by_project[project.id]:
                    if mr.state == "opened":
                        logging.info(
                            f"project {project.name_with_namespace} has a "
                            f"pending {MR_TITLE} MR"
                        )
                        run_stats["mr_waiting"] += 1
                        break
                    elif mr.state == "closed":
                        logging.info(
                            f"project {project.name_with_namespace} declined "
                            f"our {MR_TITLE} MR"
                        )
                        run_stats["mr_closed"] += 1
                        break
                else:
                    # check for pending issue
                    for issue in issue_by_project[project.id]:
                        if issue.state == "opened":
                            logging.info(
                                f"project {project.name_with_namespace} has an "
                                f"open issue {ISSUE_TITLE}"
                            )
                            run_stats["issue_waiting"] += 1
                            break
                    # Project is eligible for an alert by default
                    else:
                        logging.info(
                            f"project {project.name_with_namespace} needs alerting "
                            f"{MR_TITLE} MR"
                        )
                        # add default alert to config
                        sentryclirc.add_section(f"alert.{DEFAULT_RULE}")

                        # Propose MR avec new config
                        run_stats["mr_created"] += 1
                        try:
                            propose_sentry_mr(project, sentryclirc)
                        except Exception as err:
                            logging.warning(
                                f"project {project.name_with_namespace} failed to "
                                f"create the MR ({err})"
                            )
            # CASE 4 : alerts config detected
            elif has_sentryclirc and has_dsn and alerts:
                logging.info(
                    f"project {project.name_with_namespace} : alerting config detected"
                )
                # check for pending issue
                for issue in issue_by_project[project.id]:
                    if issue.state == "opened":
                        logging.info(
                            f"project {project.name_with_namespace} has an "
                            f"open issue {ISSUE_TITLE}"
                        )
                        run_stats["issue_waiting"] += 1
                        break
                else:
                    # Check alert set in config file
                    teams = sentry.get_teams()
                    sentry_project_name = "-".join(
                        project.path_with_namespace.split("/")[1:]
                    )
                    alerts = test_alert_config(
                        alerts, teams, sentry_group_name, sentry_project_name, sentry
                    )
                    # Syntax ok
                    if alerts:
                        logging.info(
                            f"project {project.name_with_namespace} : alerting syntax "
                            "is OK"
                        )
                        try:
                            sentry_project = sentry.get_project(
                                sentry_project_name,
                            )
                            sentry_project_rules = sentry.get_project_rules(
                                sentry_project,
                            )
                        except Exception as err:
                            logging.warning(
                                f"project {project.name_with_namespace} failed to "
                                f"get its sentry project ({err})"
                            )
                            continue
                        # Sentry has alert rules already
                        if sentry_project_rules:
                            logging.info(
                                f"project {project.name_with_namespace} : alerts are "
                                "already set in sentry"
                            )
                            project_o = gitlab.projects.get(project.id)
                            sentryclirc = project_o.files.get(
                                file_path=".sentryclirc", ref="master"
                            )
                            commit = project_o.commits.get(sentryclirc.last_commit_id)

                            # considere only if commit more recent than last script run
                            last_run = datetime.today() - timedelta(
                                hours=SCRIPT_CRON_HOUR_INTERVAL
                            )
                            commit_date = datetime.strptime(
                                commit.committed_date.replace("T", " ").split(".")[0],
                                "%Y-%m-%d %H:%M:%S",
                            )
                            if last_run < commit_date:
                                logging.info(
                                    f"project {project.name_with_namespace} : alerting "
                                    "config is more recent than our last run"
                                )
                                # remove all sentry rule
                                if len(sentry_project_rules) >= 1:
                                    for sentry_rule in sentry_project_rules:
                                        sentry.delete_project_rule(
                                            sentry_project_name, sentry_rule["id"]
                                        )
                                # add all rule from file to sentry
                                for rule in alerts:
                                    try:
                                        sentry.add_project_rule(
                                            sentry_project_name, rule
                                        )
                                    except Exception as err:
                                        logging.warning(
                                            f"project {project.name_with_namespace} "
                                            "failed to add rule in sentry "
                                            f"project ({err})"
                                        )
                                        continue
                                    logging.info(
                                        f"project {project.name_with_namespace} : rule "
                                        f"{rule['name']} added"
                                    )
                                    run_stats["sentry_rules_added"] += 1
                        # Sentry doesnt have rules yet
                        else:
                            logging.info(
                                f"project {project.name_with_namespace} : no alert set "
                                "in sentry yet"
                            )
                            for rule in alerts:
                                sentry.add_project_rule(sentry_project_name, rule)
                                logging.info(
                                    f"project {project.name_with_namespace} : rule "
                                    f"{rule['name']} added"
                                )
                                run_stats["sentry_rules_added"] += 1
                    else:
                        logging.info(
                            f"project {project.name_with_namespace} : bad syntax"
                        )
                        add_new_issue(gitlab.projects.get(project.id))

    logging.info(f"run stats: {dict(run_stats)}")


if __name__ == "__main__":
    sentry_sdk.init(
        debug=False,
        dsn="https://7dbff29bc3e049829ba89831c20fa21e@sentry.numberly.net/64",
        environment="production",
    )
    main()
