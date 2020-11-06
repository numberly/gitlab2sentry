import logging
import time
from datetime import datetime, timedelta
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
    DSN_MR_TITLE,
    ENV,
    GITLAB_AUTHOR_EMAIL,
    GITLAB_AUTHOR_NAME,
    GITLAB_GRAPHQL_PAGE_LENGTH,
    GITLAB_GRAPHQL_SUFFIX,
    GITLAB_GRAPHQL_TIMEOUT,
    GITLAB_MENTIONS_ACCESS_LEVEL,
    GITLAB_MENTIONS_LIST,
    GITLAB_PROJECT_CREATION_LIMIT,
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

    def __str__(self) -> str:
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

    def _query(self, name: str, query: str) -> Dict[str, Any]:
        try:
            start_time = time.time()
            result = self._client.execute(gql(query))
            logging.info(
                "{}: Query {} execution_time: {}s".format(  # noqa
                    self.__str__(), name, round(time.time() - start_time, 2)
                )
            )
            return result
        except aiohttp.client_exceptions.ClientResponseError:
            logging.warning("{}: Query {} - Returned 404".format(self.__str__(), name))
            return {}

    def project_fetch_query(self, query_dict: Dict[str, str]) -> Dict[str, Any]:
        project_full_path = f"{query_dict['full_path']}"
        blobsPaths = '(paths: "{}")'.format(SENTRYCLIRC_FILEPATH)
        titlesListMRs = '(sourceBranches: ["{}","{}"])'.format(
            SENTRYCLIRC_BRANCH_NAME, DSN_BRANCH_NAME
        )
        query = query_dict["body"] % (project_full_path, blobsPaths, titlesListMRs)
        return self._query(query_dict["name"], query)

    def project_list_query(
        self, query_dict: Dict[str, str], endCursor: str
    ) -> Dict[str, Any]:
        whereStatement = ' searchNamespaces: true sort: "createdAt_desc"'
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
        return self._query(query_dict["name"], query)


class GitlabProvider:
    def __init__(
        self, url: Optional[str] = GITLAB_URL, token: Optional[str] = GITLAB_TOKEN
    ) -> None:
        self.gitlab = self._get_gitlab(url, token)
        self._gql_client = GraphQLClient(url, token)
        self.update_limit = self._get_update_limit()

    def __str__(self) -> str:
        return "<GitlabProvider>"

    def _get_gitlab(self, url: Optional[str], token: Optional[str]) -> Gitlab:
        gitlab = Gitlab(url, private_token=token)
        if ENV != "test":
            gitlab.auth()
        return gitlab

    def _get_update_limit(self) -> Optional[datetime]:
        if GITLAB_PROJECT_CREATION_LIMIT:
            return datetime.now() - timedelta(days=GITLAB_PROJECT_CREATION_LIMIT)
        else:
            return None

    def _from_iso_to_datetime(self, datetime_str: str) -> datetime:
        return datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%SZ")

    def get_project(self, query: Dict[str, Any]):
        return self._gql_client.project_fetch_query(query)

    def get_all_projects(self, query: Dict[str, Any], endCursor: str = "") -> Generator:
        while True:
            result = self._gql_client.project_list_query(query, endCursor)
            if (
                result
                and result.get(query["instance"], None)
                and result[query["instance"]].get("edges", None)
                and len(result[query["instance"]]["edges"])
            ):
                result_nodes = result[query["instance"]]["edges"]
                # Check the last item of the ordered list to se its creation
                createdAt = self._from_iso_to_datetime(
                    result_nodes[len(result_nodes) - 1]["node"]["createdAt"]
                )
                if self.update_limit and createdAt < self.update_limit:
                    yield [
                        node
                        for node in result_nodes
                        if self._from_iso_to_datetime(node["node"]["createdAt"])
                        >= self.update_limit
                    ]
                    break
                else:
                    yield result_nodes
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
        self,
        project: Project,
        full_path: str,
        branch_name: str,
        file_path: str,
        content: str,
    ) -> None:
        try:
            f = project.files.get(file_path=file_path, ref=project.default_branch)
            f.content = content
            f.save(branch=branch_name, commit_message=SENTRYCLIRC_COM_MSG)
        except GitlabGetError:
            logging.info(
                "{}: [Creating] Project {} - File not found for project {}.".format(
                    self.__str__(),
                    SENTRYCLIRC_FILEPATH,
                    full_path,
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

    def _get_default_mentions(self, project: Project) -> str:
        return ", ".join(
            [
                f"@{member.username}"
                for member in project.members.all()
                if member.access_level >= GITLAB_MENTIONS_ACCESS_LEVEL
            ]
        )

    def _get_mr_description(
        self, project: Project, msg: str, name_with_namespace: str
    ) -> str:
        mentions = (
            self._get_default_mentions(project)
            if not GITLAB_MENTIONS_LIST
            else ", ".join(GITLAB_MENTIONS_LIST)
        )
        return "\n".join(
            [
                line.format(
                    mentions=mentions,
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
    ) -> bool:
        try:
            project = self.gitlab.projects.get(g2s_project.pid)
            self._get_or_create_branch(branch_name, project)
            self._get_or_create_sentryclirc(
                project, g2s_project.full_path, branch_name, file_path, content
            )
            project.mergerequests.create(
                {
                    "description": self._get_mr_description(
                        project,
                        SENTRYCLIRC_MR_DESCRIPTION,
                        g2s_project.name_with_namespace,
                    ),
                    "remove_source_branch": GITLAB_RMV_SRC_BRANCH,
                    "source_branch": branch_name,
                    "target_branch": project.default_branch,
                    "title": title,
                }
            )
            return True
        except Exception as err:
            logging.warning(
                "{}: Project {} - Failed to create MR ({}): {}".format(
                    self.__str__(),
                    g2s_project.full_path,
                    branch_name,
                    str(err),
                )
            )
            return False

    def create_sentryclirc_mr(self, g2s_project: G2SProject) -> bool:
        logging.info(
            "{}: [Creating] Project {} - Needs sentry .sentryclirc MR.".format(
                self.__str__(), g2s_project.full_path
            )
        )
        return self._create_mr(
            g2s_project,
            SENTRYCLIRC_BRANCH_NAME,
            SENTRYCLIRC_FILEPATH,
            SENTRYCLIRC_MR_CONTENT.format(sentry_url=SENTRY_URL),
            SENTRYCLIRC_MR_TITLE.format(project_name=g2s_project.name),
        )

    def create_dsn_mr(self, g2s_project: G2SProject, dsn: str) -> bool:
        logging.info(
            "{}: [Creating] Project {} - Sentry dsn: {}. Needs dsn MR.".format(
                self.__str__(), g2s_project.full_path, dsn
            )
        )
        return self._create_mr(
            g2s_project,
            DSN_BRANCH_NAME,
            SENTRYCLIRC_FILEPATH,
            DSN_MR_CONTENT.format(sentry_url=SENTRY_URL, dsn=dsn),
            DSN_MR_TITLE.format(project_name=g2s_project.name),
        )
