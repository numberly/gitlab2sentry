import configparser
import logging

from gitlab.exceptions import GitlabGetError


def create_mr(project, branch_name, file_path, content, title, description):
    try:
        project.branches.get(branch_name)
        logging.info("branch already exists, deleting")
        project.branches.delete(branch_name)
    except Exception:
        pass

    project.branches.create({"branch": branch_name, "ref": project.default_branch})
    try:
        f = project.files.get(file_path=file_path, ref=project.default_branch)
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
            "target_branch": project.default_branch,
            "title": title,
        }
    )


def get_sentryclirc(project, interval="issue_interval"):
    has_file, has_dsn, sentryclirc = False, False, False
    alerts = []
    try:
        f = project.files.get(file_path=".sentryclirc", ref=project.default_branch)
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
                            alert["environment"] = sentryclirc.get(
                                section, "environment", fallback=""
                            )
                            if alert["type"] == interval:
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
