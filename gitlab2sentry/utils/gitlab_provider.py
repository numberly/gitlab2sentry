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

from gitlab2sentry.resources import G2SProject, settings


class GraphQLClient:
    def __init__(
        self,
        url: Optional[str] = settings.gitlab_url,
        token: Optional[str] = settings.gitlab_token,
    ):
        self._client = Client(
            transport=self._get_transport(url, token),
            fetch_schema_from_transport=True,
            execute_timeout=settings.gitlab_graphql_timeout,
        )
        websockets_logger.setLevel(logging.WARNING)

    def __str__(self) -> str:
        return "<GraphQLClient>"

    def _get_transport(
        self, url: Optional[str], token: Optional[str]
    ) -> AIOHTTPTransport:
        return AIOHTTPTransport(
            url="{}/{}".format(url, settings.gitlab_graphql_suffix),
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
        blobsPaths = '(paths: "{}")'.format(settings.sentryclirc_filepath)
        titlesListMRs = '(sourceBranches: ["{}","{}"])'.format(
            settings.sentryclirc_branch_name, settings.dsn_branch_name
        )
        query = query_dict["body"] % (project_full_path, blobsPaths, titlesListMRs)
        return self._query(query_dict["name"], query)

    def project_list_query(
        self, query_dict: Dict[str, str], endCursor: str
    ) -> Dict[str, Any]:
        whereStatement = ' searchNamespaces: true sort: "createdAt_desc"'
        edgesStatement = "(first: {}{}{})".format(
            settings.gitlab_graphql_page_length,
            f' after: "{endCursor}"' if endCursor else "",
            whereStatement,
        )
        blobsPaths = '(paths: "{}")'.format(settings.sentryclirc_filepath)
        titlesListMRs = '(sourceBranches: ["{}","{}"])'.format(
            settings.sentryclirc_branch_name, settings.dsn_branch_name
        )
        query = query_dict["body"] % (edgesStatement, blobsPaths, titlesListMRs)
        return self._query(query_dict["name"], query)


class GitlabProvider:
    def __init__(
        self,
        url: Optional[str] = settings.gitlab_url,
        token: Optional[str] = settings.gitlab_token,
    ) -> None:
        self.gitlab = self._get_gitlab(url, token)
        self._gql_client = GraphQLClient(url, token)
        self.update_limit = self._get_update_limit()

    def __str__(self) -> str:
        return "<GitlabProvider>"

    def _get_gitlab(self, url: Optional[str], token: Optional[str]) -> Gitlab:
        gitlab = Gitlab(url, private_token=token)
        if settings.env != "test":
            gitlab.auth()
        return gitlab

    def _get_update_limit(self) -> Optional[datetime]:
        if settings.gitlab_project_creation_limit:
            return datetime.now() - timedelta(
                days=settings.gitlab_project_creation_limit
            )
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
            f.save(branch=branch_name, commit_message=settings.sentryclirc_com_msg)
        except GitlabGetError:
            logging.info(
                "{}: [Creating] Project {} - File not found for project {}.".format(
                    self.__str__(),
                    settings.sentryclirc_filepath,
                    full_path,
                )
            )
            data = {
                "author_email": settings.gitlab_author_email,
                "author_name": settings.gitlab_author_name,
                "branch": branch_name,
                "commit_message": settings.sentryclirc_com_msg,
                "content": content,
                "file_path": file_path,
            }
            # When commit signing is enabled in GitLab (e.g. via pre-hook),
            # commit requires that the author information matches the signer identity
            # https://gitlab.com/gitlab-org/gitlab/-/merge_requests/150855
            if settings.gitlab_signed_commit:
                data.pop("author_email")
                data.pop("author_name")
            f = project.files.create(data=data)

    def _get_default_mentions(self, project: Project) -> str:
        return ", ".join(
            [
                f"@{member.username}"
                for member in project.members_all.list(iterator=True)
                if (
                    member.access_level >= settings.gitlab_mentions_access_level
                    and member.state != "blocked"
                )
            ]
        )

    def _get_mr_description(
        self, project: Project, msg: str, name_with_namespace: str
    ) -> str:
        mentions = (
            self._get_default_mentions(project)
            if not settings.gitlab_mentions
            else ", ".join(settings.gitlab_mentions)
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
                        settings.sentryclirc_mr_description,
                        g2s_project.name_with_namespace,
                    ),
                    "remove_source_branch": settings.gitlab_rmv_src_branch,
                    "source_branch": branch_name,
                    "target_branch": project.default_branch,
                    "title": title,
                    "labels": settings.gitlab_mr_label_list,
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
            settings.sentryclirc_branch_name,
            settings.sentryclirc_filepath,
            settings.sentryclirc_mr_content.format(sentry_url=settings.sentry_url),
            settings.sentryclirc_mr_title.format(project_name=g2s_project.name),
        )

    def create_dsn_mr(
        self, g2s_project: G2SProject, dsn: str, project_slug: str
    ) -> bool:
        logging.info(
            "{}: [Creating] Project {} - Sentry dsn: {}. Needs dsn MR.".format(
                self.__str__(), g2s_project.full_path, dsn
            )
        )
        return self._create_mr(
            g2s_project,
            settings.dsn_branch_name,
            settings.sentryclirc_filepath,
            settings.dsn_mr_content.format(
                sentry_url=settings.sentry_url, dsn=dsn, project_slug=project_slug
            ),
            settings.dsn_mr_title.format(project_name=g2s_project.name),
        )
