import logging
from typing import List, Optional, Tuple

from gitlab import Gitlab
from gitlab.exceptions import GitlabGetError
from gitlab.v4.objects import Group, Project, ProjectMergeRequest

from gitlab2sentry.resources import (
    DSN_MR_CONTENT,
    DSN_MR_DESCRIPTION,
    DSN_MR_BRANCH_NAME,
    DSN_MR_TITLE,
    GITLAB_AUTHOR_EMAIL,
    GITLAB_AUTHOR_NAME,
    GITLAB_MENTIONS_LIST,
    GITLAB_RMV_SRC_BRANCH,
    GITLAB_TOKEN,
    GITLAB_URL,
    SENTRY_URL,
    SENTRYCLIRC_COM_MSG,
    SENTRYCLIRC_FILEPATH,
    SENTRYCLIRC_MR_CONTENT,
    SENTRYCLIRC_MR_DESCRIPTION,
    SENTRYCLIRC_BRANCH_NAME,
    SENTRYCLIRC_MR_TITLE,
)


class GitlabProvider:
    def __init__(
        self, url: Optional[str] = GITLAB_URL, token: Optional[str] = GITLAB_TOKEN
    ) -> None:
        self.gitlab = self._get_gitlab(url, token)

    def __str__(self):
        return "<GitlabProvider>"

    def _get_gitlab(self, url: Optional[str], token: Optional[str]) -> Gitlab:
        gitlab = Gitlab(url, private_token=token)
        gitlab.auth()
        return gitlab

    @property
    def mrs(self) -> List[ProjectMergeRequest]:
        return self.gitlab.mergerequests.list(
            all=True, state="all", scope="created_by_me"
        )

    @property
    def groups(self) -> List[Group]:
        return self.gitlab.groups.list(all=True, include_subgroups=True)

    def _get_or_create_branch(self, branch_name: str, project: Project) -> None:
        try:
            project.branches.get(branch_name)
            logging.warning(
                "{}: Branch {} already exists, deleting".format(
                    self.__str__(), branch_name
                )
            )
            project.branches.delete(branch_name)
        except Exception:
            pass

        project.branches.create({"branch": branch_name, "ref": project.default_branch})

    def _get_or_create_sentryclirc(
        self, project: Project, branch_name: str, file_path: str, content: str
    ) -> None:
        try:
            f = project.files.get(file_path=file_path, ref=project.default_branch)
            f.content = content
            f.save(branch=branch_name, commit_message=SENTRYCLIRC_COM_MSG)
        except Exception:
            f = project.files.create(
                {
                    "author_email": GITLAB_AUTHOR_EMAIL,
                    "author_name": GITLAB_AUTHOR_NAME,
                    "branch": branch_name,
                    "commit_message": SENTRYCLIRC_COM_MSG,
                    "content": content,
                    "file_path": file_path,
                }
            )

    def _get_mr_msg(self, msg: str, name_with_namespace: str) -> tuple:
        return tuple(
            [
                line.format(
                    mentions=GITLAB_MENTIONS_LIST.join(" ,"),
                    name_with_namespace=name_with_namespace,
                )
                for line in msg.split("\n")
            ]
        )

    def _create_mr(
        self,
        project: Project,
        branch_name: str,
        file_path: str,
        content: str,
        title: str,
        description: tuple,
    ) -> None:
        self._get_or_create_branch(branch_name, project)
        self._get_or_create_sentryclirc(project, branch_name, file_path, content)
        project.mergerequests.create(
            {
                "description": description,
                "remove_source_branch": GITLAB_RMV_SRC_BRANCH,
                "source_branch": branch_name,
                "target_branch": project.default_branch,
                "title": title,
            }
        )

    def create_sentryclirc_mr(self, project: Project) -> None:
        self._create_mr(
            project,
            SENTRYCLIRC_BRANCH_NAME,
            SENTRYCLIRC_FILEPATH,
            SENTRYCLIRC_MR_CONTENT.format(sentry_url=SENTRY_URL),
            SENTRYCLIRC_MR_TITLE.format(project.name),
            self._get_mr_msg(SENTRYCLIRC_MR_DESCRIPTION, project.name_with_namespace),
        )

    def create_dsn_mr(self, project: Project, dsn: str) -> None:
        self._create_mr(
            project,
            DSN_MR_BRANCH_NAME,
            SENTRYCLIRC_FILEPATH,
            DSN_MR_CONTENT.format(sentry_url=SENTRY_URL, dsn=dsn),
            DSN_MR_TITLE.format(project_name=project.name),
            self._get_mr_msg(DSN_MR_DESCRIPTION,  project.name_with_namespace),
        )

    def get_sentryclirc(self, project_id: int) -> Tuple[bool, bool]:
        has_file, has_dsn = False, False
        try:
            project = self.gitlab.projects.get(project_id)
            f = project.files.get(
                file_path=SENTRYCLIRC_FILEPATH, ref=project.default_branch
            )
        except GitlabGetError:
            pass
        else:
            has_file = True
            for line in f.decode().splitlines():
                if line.startswith(b"dsn"):
                    has_dsn = True

        logging.debug(
            "{}: Project {}".format(self.__str__(), project.name_with_namespace),
            "{}: has_sentryclirc={}".format(self.__str__(), has_file),
            "{}: has_dsn={}".format(self.__str__(), has_dsn),
        )
        return has_file, has_dsn
