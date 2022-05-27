import logging
import time
from typing import Any, Dict, Generator, Optional

import aiohttp
from gitlab import Gitlab
from gitlab.exceptions import GitlabGetError
from gitlab.v4.objects import Project
from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.aiohttp import log as websockets_logger

from gitlab2sentry.resources import (
    DSN_BRANCH_NAME,
    DSN_MR_CONTENT,
    DSN_MR_DESCRIPTION,
    DSN_MR_TITLE,
    GITLAB_AUTHOR_EMAIL,
    GITLAB_AUTHOR_NAME,
    GITLAB_GRAPHQL_PAGE_LENGTH,
    GITLAB_GRAPHQL_SUFFIX,
    GITLAB_GRAPHQL_TIMEOUT,
    GITLAB_GROUP_IDENTIFIER,
    GITLAB_MENTIONS_LIST,
    GITLAB_RMV_SRC_BRANCH,
    GITLAB_TOKEN,
    GITLAB_URL,
    SENTRY_URL,
    SENTRYCLIRC_BRANCH_NAME,
    SENTRYCLIRC_COM_MSG,
    SENTRYCLIRC_FILEPATH,
    SENTRYCLIRC_MR_CONTENT,
    SENTRYCLIRC_MR_DESCRIPTION,
    SENTRYCLIRC_MR_TITLE,
    G2SProject,
)


class GraphQLClient:
    def __init__(
        self, url: Optional[str] = GITLAB_URL, token: Optional[str] = GITLAB_TOKEN
    ):
        self._client = Client(
            transport=self._get_transport(url, token),
            fetch_schema_from_transport=True,
            execute_timeout=GITLAB_GRAPHQL_TIMEOUT,
        )
        websockets_logger.setLevel(logging.WARNING)

    def __str__(self):
        return "<GraphQLClient>"

    def _get_transport(
        self, url: Optional[str], token: Optional[str]
    ) -> AIOHTTPTransport:
        return AIOHTTPTransport(
            url="{}/{}".format(url, GITLAB_GRAPHQL_SUFFIX),
            headers={
                "PRIVATE-TOKEN": token,  # type: ignore
                "Content-Type": "application/json",
            },
        )

    def query(self, query_dict: Dict[str, str], endCursor: str) -> Dict[str, Any]:
        whereStatement = ' searchNamespaces: true search: "{}"'.format(
            GITLAB_GROUP_IDENTIFIER
        )
        edgesStatement = "(first: {}{}{})".format(
            GITLAB_GRAPHQL_PAGE_LENGTH,
            f' after: "{endCursor}"' if endCursor else "",
            whereStatement,
        )
        blobsPaths = '(paths: "{}")'.format(SENTRYCLIRC_FILEPATH)
        titlesListMRs = '(sourceBranches: ["{}","{}"])'.format(
            SENTRYCLIRC_BRANCH_NAME, DSN_BRANCH_NAME
        )
        query = query_dict["body"] % (edgesStatement, blobsPaths, titlesListMRs)
        try:
            start_time = time.time()
            result = self._client.execute(gql(query))
            logging.info(
                "{}: Query {} execution_time: {}s items_returned: {} end_cursor: {}".format(  # noqa
                    self.__str__(),
                    query_dict["name"],
                    round(time.time() - start_time, 2),
                    len(result["projects"]["edges"]),
                    result["projects"]["pageInfo"].get("endCursor"),
                )
            )
            return result
        except aiohttp.client_exceptions.ClientResponseError:
            logging.warning(
                "{}: Query {} - Returned 404".format(self.__str__(), query_dict["name"])
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

    def _get_g2s_query(self, query: Dict[str, Any], endCursor: str = "") -> Generator:
        while True:
            result = self._gql_client.query(query, endCursor)
            if (
                result
                and result.get(query["instance"], None)
                and result[query["instance"]].get("edges", None)
                and len(result[query["instance"]]["edges"])
            ):
                yield result[query["instance"]]["edges"]

                if (
                    result
                    and result.get(query["instance"], None)
                    and result[query["instance"]].get("pageInfo", None)
                    and result[query["instance"]]["pageInfo"].get("endCursor", None)
                    and result[query["instance"]]["pageInfo"]["endCursor"]
                ):
                    endCursor = result[query["instance"]]["pageInfo"]["endCursor"]
            if not (
                result
                and result[query["instance"]].get("pageInfo")
                and result[query["instance"]]["pageInfo"].get("hasNextPage")
            ):
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
        except GitlabGetError:
            pass

        project.branches.create({"branch": branch_name, "ref": project.default_branch})

    def _get_or_create_sentryclirc(
        self, project: Project, branch_name: str, file_path: str, content: str
    ) -> None:
        try:
            f = project.files.get(file_path=file_path, ref=project.default_branch)
            f.content = content
            f.save(branch=branch_name, commit_message=SENTRYCLIRC_COM_MSG)
        except GitlabGetError:
            logging.info(
                "{}: {} file not found for project {}. Creating".format(
                    self.__str__(),
                    SENTRYCLIRC_FILEPATH,
                    project.path_with_namespace,
                )
            )
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

    def _get_mr_msg(self, msg: str, name_with_namespace: str) -> str:
        return "\n".join(
            [
                line.format(
                    mentions=", ".join(GITLAB_MENTIONS_LIST),
                    name_with_namespace=name_with_namespace,
                )
                for line in msg.split("\n")
            ]
        )

    def _create_mr(
        self,
        g2s_project: G2SProject,
        branch_name: str,
        file_path: str,
        content: str,
        title: str,
        description: str,
    ) -> bool:
        try:
            project = self.gitlab.projects.get(g2s_project.pid)
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
            return True
        except Exception as err:
            logging.warning(
                "{}: Project {} failed to create MR ({}): {}".format(
                    self.__str__(),
                    g2s_project.path_with_namespace,
                    branch_name,
                    str(err),
                )
            )
            return False

    def create_sentryclirc_mr(self, g2s_project: G2SProject) -> bool:
        logging.info(
            "{}: Project {} needs sentry .sentryclirc MR".format(
                self.__str__(), g2s_project.path_with_namespace
            )
        )
        return self._create_mr(
            g2s_project,
            SENTRYCLIRC_BRANCH_NAME,
            SENTRYCLIRC_FILEPATH,
            SENTRYCLIRC_MR_CONTENT.format(sentry_url=SENTRY_URL),
            SENTRYCLIRC_MR_TITLE.format(project_name=g2s_project.name),
            self._get_mr_msg(
                SENTRYCLIRC_MR_DESCRIPTION, g2s_project.name_with_namespace
            ),
        )

    def create_dsn_mr(self, g2s_project: G2SProject, dsn: str) -> bool:
        logging.info(
            "{}: Project {} sentry dsn: {}. Opening dsn MR".format(
                self.__str__(), g2s_project.path_with_namespace, dsn
            )
        )
        return self._create_mr(
            g2s_project,
            DSN_BRANCH_NAME,
            SENTRYCLIRC_FILEPATH,
            DSN_MR_CONTENT.format(sentry_url=SENTRY_URL, dsn=dsn),
            DSN_MR_TITLE.format(project_name=g2s_project.name),
            self._get_mr_msg(DSN_MR_DESCRIPTION, g2s_project.name_with_namespace),
        )
