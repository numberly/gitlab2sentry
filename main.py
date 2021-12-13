import io
import logging
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

import sentry_sdk
from gitlab import Gitlab

from gitlab_tools import create_mr, get_sentryclirc
from sentry import Sentry

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
        "interval": "1m",
        "seen": "100",
    },
}
DEFAULT_RULE = ALERT_NEW_ISSUE
DEFAULT_ENVIRONNEMENT = "production"
INTERVAL = ["1m", "1h", "1d", "1w"]
SCRIPT_CRON_HOUR_INTERVAL = 3

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def ensure_sentry_team(team_name, sentry):
    logging.info(f"ensuring team {team_name} exists on sentry")
    sentry.create_or_get_team(team_name)


def propose_sentry_mr(project, config=False):
    if config:
        mr_object = "alerting"
        with io.StringIO() as ss:
            config.write(ss)
            ss.seek(0)
            content = f"## File generated by gitlab2sentry\n{ss.read()}"
        msg = (
            "@all Merge this and it will automatically create a default alert in "
            f"Sentry for {project.name_with_namespace}"
        )
    else:
        mr_object = "sentry"
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
        f"[gitlab2sentry] Merge me to add {mr_object} to {project.name} or close me",
        msg,
    )


def add_sentry_dsn_mr(project, dsn):
    content = f"""## File generated by gitlab2sentry
[defaults]
url = https://sentry.numberly.net/
dsn = {dsn}
"""
    msg = (
        "@all Congrats, your Sentry project has been created, merge this "
        "to finalize your Sentry integration :clap: :cookie:"
    )
    create_mr(
        project,
        "auto_add_sentry_dsn",
        ".sentryclirc",
        content,
        f"[gitlab2sentry] Merge me to add your sentry DSN to {project.name}",
        msg,
    )


def test_alert_config(alerts, teams, group, project_name, sentry, sentryclirc):
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
                    logging.info(f"Alerting syntax : {alert['notify']} not found")
                    return False
            elif group == "team-uep" and (
                project_name.endswith("frontend")
                or re.match(".+backend-v*", project_name)
            ):
                subteam = project_name.split("-")[-1]
                if subteam.startswith("v"):
                    subteam = project_name.split("-")[-2]
                subteam = subteam[:-3]
                alert["notify"] = f"{group}-{subteam}"
                alert["team_id"] = teams[alert["notify"]]["id"]
            else:
                alert["notify"] = group
                alert["team_id"] = teams[alert["notify"]]["id"]
            # Check interval & seen
            if "interval" in atype:
                if alert.get("interval"):
                    if not alert["interval"] in INTERVAL:
                        logging.info(
                            f"Alerting syntax : {alert['interval']} incorrect interval"
                        )
                        return False
                else:
                    alert["interval"] = RULES[atype]["interval"]
                if alert.get("seen"):
                    if (
                        not alert["seen"].isdigit()
                        or not 1 <= int(alert["seen"]) <= 100
                    ):
                        logging.info(
                            f"Alerting syntax : {alert['seen']} incorrect seen"
                        )
                        return False
                else:
                    alert["seen"] = RULES[atype]["seen"]
            # Get existing environments set in the project
            environments = sentry.get_project_environments(project_name)
            for env in environments:
                if not alert["environment"]:
                    if "production" in env.get("name"):
                        alert["environment"] = env.get("name")
                        break
                elif alert["environment"] == env.get("name"):
                    break
                else:
                    logging.info(
                        f"Alerting syntax : {alert['environment']} "
                        "environment doesn't exist"
                    )
                    return False
            else:
                # Create fake event to initialize environnement
                dsn = sentryclirc.get("defaults", "dsn")
                sentry_initializer = sentry_sdk.Client(debug=False, dsn=dsn,)
                event = {
                    "message": "Event generated by gitlab2sentry",
                    "environment": DEFAULT_ENVIRONNEMENT,
                }
                sentry_initializer.capture_event(event)
                sentry_initializer.flush(5)
                alert["environment"] = DEFAULT_ENVIRONNEMENT
        else:
            logging.info(f"Alerting syntax : {alert['environment']} doesn't exist")
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
    yesterday = datetime.utcnow() - timedelta(hours=24)

    # get all the MRs we ever done
    logging.info("Getting all MR")
    for mr in gitlab.mergerequests.list(all=True, state="all", scope="created_by_me"):
        if "sentry" in mr.title.lower():
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

    for group in groups:
        # we are only interested in team groups
        if not group.full_name.startswith("team-"):
            continue
        team-uep = group.full_name.startswith("team-uep")
        sentry_group_name = group.full_name.split("/")[0].strip()
        # ensure each gitlab group has a sentry sibling
        logging.debug(f"handling gitlab group {group.full_name}")
        if sentry_group_name not in sentry_groups:
            ensure_sentry_team(sentry_group_name, sentry)
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

            # we will only run on projects which changed within 24H
            if (
                datetime.fromisoformat(project.last_activity_at.replace("Z", ""))
                < yesterday
            ):
                logging.info(
                    f"project {project.name_with_namespace} skipped due to last"
                    f" activity being {project.last_activity_at}"
                )
                continue

            # check sentryclirc presence and dsn in the file
            project = gitlab.projects.get(project.id)
            (has_sentryclirc, has_dsn, alerts, sentryclirc,) = get_sentryclirc(
                project, ALERT_INTERVAL
            )
            logging.debug(
                f"project {project.name_with_namespace} "
                f"has_sentryclirc={has_sentryclirc} "
                f"has_dsn={has_dsn}"
                f"alerts={alerts if alerts else ''}"
            )

            # CASE 1 : sentryclirc but no dsn
            if has_sentryclirc and not has_dsn:
                # check for pending MR
                for mr in mr_by_project[project.id]:
                    if mr.state == "opened":
                        logging.info(
                            f"project {project.name_with_namespace} has a "
                            "pending dsn MR"
                        )
                        run_stats["mr_dsn_waiting"] += 1
                        break
                else:
                    sentry_project_name = "-".join(
                        project.path_with_namespace.split("/")[1:]
                    )
                    logging.info(f"creating sentry project {sentry_project_name}")
                    try:
                        sentry_project = sentry.create_or_get_project(
                            sentry_group_name, sentry_project_name,
                        )
                    except Exception as err:
                        logging.warning(
                            f"project {project.name_with_namespace} failed to "
                            f"get/create its sentry project ({err})"
                        )
                        continue
                    clients_keys = sentry.get_clients_keys(
                        sentry_group_name, sentry_project["slug"]
                    )
                    dsn = clients_keys[0]["dsn"]["public"]
                    logging.info(
                        f"project {project.name_with_namespace} sentry dsn: {dsn}"
                    )
                    logging.info(
                        f"project {project.name_with_namespace} needs sentry dsn MR"
                    )
                    add_sentry_dsn_mr(project, dsn)
                    run_stats["mr_dsn_created"] += 1

            # CASE 2 : no sentryclirc at all
            elif not has_sentryclirc:
                for mr in mr_by_project[project.id]:
                    if mr.state == "opened":
                        logging.info(
                            f"project {project.name_with_namespace} has a "
                            "pending sentryclirc MR"
                        )
                        run_stats["mr_sentryclirc_waiting"] += 1
                        break
                    elif mr.state == "closed":
                        logging.info(
                            f"project {project.name_with_namespace} declined "
                            "our sentryclirc MR"
                        )
                        run_stats["mr_sentryclirc_closed"] += 1
                        break
                else:
                    logging.info(
                        f"project {project.name_with_namespace} needs sentry "
                        ".sentryclirc MR"
                    )
                    run_stats["mr_sentryclirc_created"] += 1
                    try:
                        propose_sentry_mr(project)
                    except Exception as err:
                        logging.warning(
                            f"project {project.name_with_namespace} failed to "
                            f"create the .sentryclirc MR ({err})"
                        )
            # CASE 3 : sentryclirc, dsn but no alerting set
            elif team-uep and has_sentryclirc and has_dsn and not alerts:
                logging.info(
                    f"project {project.name_with_namespace} : no alerting "
                    "config detected"
                )
                run_stats["has_sentry_dsn"] += 1
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

            # CASE 4 : all is set
            elif team-uep and has_sentryclirc and has_dsn and alerts:
                logging.info(
                    f"project {project.name_with_namespace} : alerting config detected"
                )
                run_stats["has_sentry_dsn"] += 1
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
                        alerts,
                        teams,
                        sentry_group_name,
                        sentry_project_name,
                        sentry,
                        sentryclirc,
                    )
                    # Syntax ok
                    if alerts:
                        logging.info(
                            f"project {project.name_with_namespace} : alerting syntax "
                            "is OK"
                        )
                        try:
                            sentry_project = sentry.get_projects(sentry_project_name,)
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
                                file_path=".sentryclirc", ref=project.default_branch
                            )
                            commit = project_o.commits.get(sentryclirc.last_commit_id)

                            # considere only if commit more recent than last script run
                            last_run = datetime.today().replace(
                                tzinfo=timezone.utc
                            ) - timedelta(hours=SCRIPT_CRON_HOUR_INTERVAL)
                            commit_date = datetime.strptime(
                                commit.committed_date.replace("T", " ").split(".")[0],
                                "%Y-%m-%d %H:%M:%S",
                            )
                            commit_date = commit_date.replace(tzinfo=timezone.utc)
                            if last_run < commit_date:
                                logging.info(
                                    f"project {project.name_with_namespace} : alerting "
                                    "config is more recent than our last run"
                                )
                                # remove all sentry rule
                                for sentry_rule in sentry_project_rules:
                                    sentry.delete_project_rule(
                                        sentry_project_name, sentry_rule["id"]
                                    )
                                # add all rule from file to sentry
                                for rule in alerts:
                                    try:
                                        sentry.add_project_rule(
                                            sentry_project_name,
                                            rule,
                                            RULES_DEFAULT_FREQUENCY,
                                        )
                                    except Exception as err:
                                        logging.warning(
                                            f"project {project.name_with_namespace} "
                                            "failed to add rule in sentry "
                                            f"project ({err})"
                                        )
                                        continue
                                    else:
                                        logging.info(
                                            f"project {project.name_with_namespace} : "
                                            f"rule {rule['name']} added"
                                        )
                                        run_stats["sentry_rules_added"] += 1
                        # Sentry doesnt have rules yet
                        else:
                            logging.info(
                                f"project {project.name_with_namespace} : no alert set "
                                "in sentry yet"
                            )
                            for rule in alerts:
                                sentry.add_project_rule(
                                    sentry_project_name, rule, RULES_DEFAULT_FREQUENCY
                                )
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
