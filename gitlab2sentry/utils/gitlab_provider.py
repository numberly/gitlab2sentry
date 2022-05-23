import logging
from typing import Dict, Generator, NamedTuple, Optional

import aiohttp
from gitlab import Gitlab
from gitlab.v4.objects import Project
from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport, ExecutionResult
from gql.transport.aiohttp import log as websockets_logger

from gitlab2sentry.resources import (
    DSN_BRANCH_NAME,
    DSN_MR_CONTENT,
    DSN_MR_DESCRIPTION,
    DSN_MR_TITLE,
    GITLAB_AUTHOR_EMAIL,
    GITLAB_AUTHOR_NAME,
    GITLAB_GRAPHQL_SUFFIX,
    GITLAB_MENTIONS_LIST,
    GITLAB_RMV_SRC_BRANCH,
    GITLAB_TOKEN,
    GITLAB_URL,
    GRAPHQL_PROJECTS_QUERY,
    SENTRY_URL,
    SENTRYCLIRC_BRANCH_NAME,
    SENTRYCLIRC_COM_MSG,
    SENTRYCLIRC_FILEPATH,
    SENTRYCLIRC_MR_CONTENT,
    SENTRYCLIRC_MR_DESCRIPTION,
    SENTRYCLIRC_MR_TITLE,
)


class GraphQLClient:
    def __init__(self, url: str = None, token: str = None):
        self._client = Client(
            transport=self._get_transport(url, token), fetch_schema_from_transport=True
        )
        websockets_logger.setLevel(logging.WARNING)

    def __str__(self):
        return "<GraphQLClient>"

    def _get_transport(self, url: str, token: str) -> AIOHTTPTransport:
        return AIOHTTPTransport(
            url="{}/{}".format(url, GITLAB_GRAPHQL_SUFFIX),
            headers={"PRIVATE-TOKEN": token, "Content-Type": "application/json"},
        )

    def query(self, query: Dict[str, str], endCursor: str) -> ExecutionResult:
        afterStatement = '(after: "{}")'.format(endCursor) if endCursor else ""
        titlesListMRs = '(sourceBranches: ["{}","{}"])'.format(
            SENTRYCLIRC_BRANCH_NAME, DSN_BRANCH_NAME
        )
        blobsPaths = '(paths: "{}")'.format(SENTRYCLIRC_FILEPATH)
        try:
            logging.info(
                "{}: Quering with GraphQL (query_name: {}) - cursor: {}".format(
                    self.__str__(), query["name"], endCursor
                )
            )
            return self._client.execute(
                gql(query["body"] % (afterStatement, blobsPaths, titlesListMRs))
            )
        except aiohttp.client_exceptions.ClientResponseError:
            logging.warning(
                "{}: Query {} - Returned 404".format(self.__str__(), query["name"])
            )
            return {}


class GitlabProvider:
    def __init__(
        self, url: Optional[str] = GITLAB_URL, token: Optional[str] = GITLAB_TOKEN
    ) -> None:
        self.gitlab = self._get_gitlab(url, token)
        self._gql_client = GraphQLClient(url, token)

    def __str__(self):
        return "<GitlabProvider>"

    def _get_gitlab(self, url: Optional[str], token: Optional[str]) -> Gitlab:
        gitlab = Gitlab(url, private_token=token)
        gitlab.auth()
        return gitlab

    def _get_g2s_projects(self, endCursor: str = "") -> Generator:
        while True:
            result = self._gql_client.query(GRAPHQL_PROJECTS_QUERY, endCursor)
            if (
                result
                and result.get("projects", None)
                and result["projects"].get("edges", None)
                and len(result["projects"]["edges"])
            ):
                yield result["projects"]["edges"]

                if (
                    result
                    and result.get("projects", None)
                    and result["projects"].get("pageInfo", None)
                    and result["projects"]["pageInfo"].get("endCursor", None)
                    and result["projects"]["pageInfo"]["endCursor"]
                ):
                    endCursor = result["projects"]["pageInfo"]["endCursor"]
            else:
                break

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
        g2s_project: NamedTuple,
        branch_name: str,
        file_path: str,
        content: str,
        title: str,
        description: tuple,
    ) -> None:
        project = self.gitlab.project.get(g2s_project.id)
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

    def create_sentryclirc_mr(self, g2s_project: NamedTuple) -> None:
        self._create_mr(
            g2s_project,
            SENTRYCLIRC_BRANCH_NAME,
            SENTRYCLIRC_FILEPATH,
            SENTRYCLIRC_MR_CONTENT.format(sentry_url=SENTRY_URL),
            SENTRYCLIRC_MR_TITLE.format(g2s_project.name),
            self._get_mr_msg(
                SENTRYCLIRC_MR_DESCRIPTION, g2s_project.name_with_namespace
            ),
        )

    def create_dsn_mr(self, g2s_project: NamedTuple, dsn: str) -> None:
        self._create_mr(
            g2s_project,
            DSN_BRANCH_NAME,
            SENTRYCLIRC_FILEPATH,
            DSN_MR_CONTENT.format(sentry_url=SENTRY_URL, dsn=dsn),
            DSN_MR_TITLE.format(project_name=g2s_project.name),
            self._get_mr_msg(DSN_MR_DESCRIPTION, g2s_project.name_with_namespace),
        )
