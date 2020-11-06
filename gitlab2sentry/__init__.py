import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from gitlab2sentry.exceptions import SentryProjectCreationFailed
from gitlab2sentry.resources import (
    DSN_MR_TITLE,
    G2S_STATS,
    GITLAB_GRAPHQL_SUFFIX,
    GITLAB_GROUP_IDENTIFIER,
    GITLAB_TOKEN,
    GITLAB_URL,
    GRAPHQL_FETCH_PROJECT_QUERY,
    GRAPHQL_LIST_PROJECTS_QUERY,
    SENTRY_ORG_SLUG,
    SENTRY_TOKEN,
    SENTRY_URL,
    SENTRYCLIRC_FILEPATH,
    SENTRYCLIRC_MR_TITLE,
    G2SProject,
)
from gitlab2sentry.utils import GitlabProvider, SentryProvider

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


class Gitlab2Sentry:
    def __init__(self):
        self.gitlab_provider = self._get_gitlab_provider()
        self.sentry_provider = self._get_sentry_provider()
        self.run_stats = {key: value for key, value in G2S_STATS}
        self.yesterday = datetime.utcnow() - timedelta(hours=24)
        self.sentry_groups = set()

    def __str__(self) -> str:
        return "<Gitlab2Sentry>"

    def _get_gitlab_provider(self) -> GitlabProvider:
        return GitlabProvider(GITLAB_URL, GITLAB_TOKEN)

    def _get_sentry_provider(self) -> SentryProvider:
        return SentryProvider(SENTRY_URL, SENTRY_TOKEN, SENTRY_ORG_SLUG)

    def _ensure_sentry_group(self, name: str) -> None:
        if name not in self.sentry_groups:
            self.sentry_provider.ensure_sentry_team(name)
            self.sentry_groups.add(name)

    def _has_mrs_enabled(self, g2s_project: G2SProject) -> bool:
        if not g2s_project.mrs_enabled:
            logging.info(
                "{}: [Skipping] Project {} - Does not accept MRs.".format(
                    self.__str__(), g2s_project.full_path
                )
            )
            self.run_stats["mr_disabled"] += 1
        return g2s_project.mrs_enabled

    def _is_opened_mr(self, full_path: str, state: Optional[str], label: str) -> bool:
        if state and state == "opened":
            logging.info(
                "{}: [Skipping] Project {} - Has a pending {} MR.".format(
                    self.__str__(), full_path, label
                )
            )
            self.run_stats[f"mr_{label}_waiting"] += 1
            return True
        else:
            return False

    def _opened_dsn_mr_found(self, g2s_project: G2SProject) -> bool:
        return self._is_opened_mr(
            g2s_project.full_path, g2s_project.dsn_mr_state, "dsn"
        )

    def _opened_sentryclirc_mr_found(self, g2s_project: G2SProject) -> bool:
        return self._is_opened_mr(
            g2s_project.full_path,
            g2s_project.sentryclirc_mr_state,
            "sentryclirc",
        )

    def _is_closed_mr(self, full_path: str, state: Optional[str], label: str) -> bool:
        if state and state == "closed":
            logging.info(
                "{}: [Skipping] Project {} - Has a closed {} MR.".format(
                    self.__str__(), full_path, label
                )
            )
            self.run_stats[f"mr_{label}_closed"] += 1

            return True
        else:
            return False

    def _closed_dsn_mr_found(self, g2s_project: G2SProject) -> bool:
        return self._is_closed_mr(
            g2s_project.full_path, g2s_project.dsn_mr_state, "dsn"
        )

    def _closed_sentryclirc_mr_found(self, g2s_project: G2SProject) -> bool:
        return self._is_closed_mr(
            g2s_project.full_path,
            g2s_project.sentryclirc_mr_state,
            "sentryclirc",
        )

    def _get_mr_states(
        self, project_name: str, mr_list: Optional[List[Dict[str, Any]]]
    ) -> tuple:
        sentryclirc_mr_state, dsn_mr_state = None, None
        if mr_list:
            for mr in mr_list:
                if mr["title"] == SENTRYCLIRC_MR_TITLE.format(
                    project_name=project_name
                ):
                    if not (sentryclirc_mr_state and sentryclirc_mr_state == "opened"):
                        sentryclirc_mr_state = mr["state"]
                elif mr["title"] == DSN_MR_TITLE.format(project_name=project_name):
                    if not (dsn_mr_state and dsn_mr_state == "opened"):
                        dsn_mr_state = mr["state"]
                else:
                    pass
        return sentryclirc_mr_state, dsn_mr_state

    def _is_group_project(self, group: Optional[Dict[str, Any]]) -> bool:
        if group and group.get("name"):
            return True
        else:
            return False

    def _get_sentryclirc_file(self, blob: List[Dict[str, Any]]) -> tuple:
        has_sentryclirc_file, has_dsn = False, False
        if blob and blob[0]["name"] == SENTRYCLIRC_FILEPATH:
            has_sentryclirc_file = True
            if blob[0].get("rawTextBlob"):
                for line in blob[0]["rawTextBlob"].split("\n"):
                    if line.startswith("dsn"):
                        has_dsn = True

        return has_sentryclirc_file, has_dsn

    def _has_already_sentry(self, g2s_project: G2SProject) -> bool:
        if g2s_project.has_sentryclirc_file and g2s_project.has_dsn:
            logging.info(
                "{}: [Skipping] Project {} - Has a sentry project.".format(
                    self.__str__(), g2s_project.full_path
                )
            )
        return g2s_project.has_sentryclirc_file and g2s_project.has_dsn

    def _get_g2s_project(self, result: Dict[str, Any]) -> Optional[G2SProject]:
        if result.get("repository"):
            full_path = result["fullPath"]
            group_name = full_path.split("/")[0]
            project_name = result["name"]
            created_at = result["createdAt"]
            mrs_enabled = result["mergeRequestsEnabled"]
            id_url = result["id"].split("/")[len(result["id"].split("/")) - 1]
            sentryclirc_mr_state, dsn_mr_state = self._get_mr_states(
                result["name"], result["mergeRequests"]["nodes"]
            )
            has_sentryclirc_file, has_dsn = self._get_sentryclirc_file(
                result["repository"]["blobs"]["nodes"]
            )
            name_with_namespace = "{} / {}".format(group_name, project_name)
            pid = int(id_url.split("/")[len(id_url.split("/")) - 1])
            return G2SProject(
                pid,
                full_path,
                project_name,
                group_name,
                mrs_enabled,
                created_at,
                name_with_namespace,
                has_sentryclirc_file,
                has_dsn,
                sentryclirc_mr_state,
                dsn_mr_state,
            )
        return None

    def _get_paginated_projects(self) -> List[Dict[str, Any]]:
        query_start_time = time.time()
        logging.info(
            "{}: Starting querying all Gitlab group-projects with Graphql at {}/{}".format(  # noqa
                self.__str__(), GITLAB_URL, GITLAB_GRAPHQL_SUFFIX
            )
        )
        request_gen = self.gitlab_provider.get_all_projects(GRAPHQL_LIST_PROJECTS_QUERY)
        page_results = [page for page in request_gen]
        logging.info(
            "{}: Fetched {} pages. Total time: {} seconds".format(
                self.__str__(),
                len(page_results),
                round(time.time() - query_start_time, 2),
            )
        )
        return page_results

    def _get_gitlab_project(self, full_path: str) -> Optional[G2SProject]:
        GRAPHQL_FETCH_PROJECT_QUERY["full_path"] = full_path
        logging.info(
            "{}: Starting querying for specific Gitlab project with Graphql at {}/{}".format(  # noqa
                self.__str__(), GITLAB_URL, GITLAB_GRAPHQL_SUFFIX
            )
        )
        result = self.gitlab_provider.get_project(GRAPHQL_FETCH_PROJECT_QUERY)
        return (
            self._get_g2s_project(result.get("project"))
            if result.get("project")
            else None
        )

    def _get_gitlab_groups(self):
        groups = dict()
        valid_projects = 0
        for page_result in self._get_paginated_projects():
            for result_node in page_result:
                result = result_node["node"]
                if self._is_group_project(result["group"]):
                    group_name = result["fullPath"].split("/")[0]
                    if group_name.startswith(GITLAB_GROUP_IDENTIFIER):
                        g2s_project = self._get_g2s_project(result)

                        if g2s_project:
                            if not groups.get(group_name):
                                groups[group_name] = list()
                            groups[group_name].append(g2s_project)
                            valid_projects += 1
        logging.info(
            "{}: Total filtered projects: {}".format(self.__str__(), valid_projects)
        )
        return groups

    def _create_sentry_project(
        self, full_path: str, sentry_group_name: str
    ) -> Optional[Dict[str, Any]]:

        sentry_project_name = "-".join(full_path.split("/")[1:])
        try:
            return self.sentry_provider.get_or_create_project(
                sentry_group_name,
                sentry_project_name,
            )
        except SentryProjectCreationFailed as creation_err:
            logging.warning(
                "{} Project {} - Failed to create sentry project: {}".format(
                    self.__str__(), full_path, str(creation_err)
                )
            )
        except Exception as err:
            logging.warning(
                "{} Project {} - Failed to get/create its sentry project: {}".format(
                    self.__str__(), full_path, str(err)
                )
            )
        return None

    def _handle_g2s_project(
        self, g2s_project: G2SProject, sentry_group_name: str
    ) -> bool:
        """
        Creates sentry project for all given gitlab projects. It
        follows a two steps process.
            1. Adds the .sentryclirc file to the gitlab repo (via
                a mergeRequest).
            2. If the .sentryclirc file is added to master branch (
                or another default branch) it creates the sentry
                project and it inserts the dsn inside the .sentryclirc
                file.
        The flow for creating mrs inlcudes specific cases for creating
        or skiping. These cases are:
            1. Project is already in sentry [skip]
            2. Project has MRs disabled [skip]
            3. Project has an opened dsn MR and a .sentryclirc file.
                This means that the second MR is pending [skip]
            4. If the .sentryclirc file exists and there is no
                opened MR for dsn, creates the dsn MR [create]
            5. If the project has no .sentryclirc file but it
                has an MR (closed or opened) [skip]
            6. Project has no .sentryclirc file and no MR for
                this. Create the sentryclirc file [create]
        """
        if self._has_already_sentry(g2s_project):
            return False

        if not self._has_mrs_enabled(g2s_project):
            return False
        # Case sentryclirc found but
        # dsn not found: Pending MR
        elif g2s_project.has_sentryclirc_file and not g2s_project.has_dsn:
            if self._opened_dsn_mr_found(g2s_project) or self._closed_dsn_mr_found(
                g2s_project
            ):
                return False
            else:
                sentry_project = self._create_sentry_project(
                    g2s_project.full_path,
                    sentry_group_name,
                )

                # If Sentry fails to create project skip
                if not sentry_project:
                    return False

                dsn = self.sentry_provider.set_rate_limit_for_key(
                    sentry_project["slug"]
                )

                # If fetch of dsn failed skip
                if not dsn:
                    return False

                mr_created = self.gitlab_provider.create_dsn_mr(g2s_project, dsn)
                if mr_created:
                    self.run_stats["mr_dsn_created"] += 1
                return True
        # Case sentryclirc not found:
        # Declined sentryclirc MR or
        # need to create one
        elif not g2s_project.has_sentryclirc_file:
            if self._opened_sentryclirc_mr_found(
                g2s_project
            ) or self._closed_sentryclirc_mr_found(g2s_project):
                return False
            else:
                mr_created = self.gitlab_provider.create_sentryclirc_mr(g2s_project)
                if mr_created:
                    self.run_stats["mr_sentryclirc_created"] += 1
                return True
        else:
            logging.info(
                "{}: Project {} - Not included in Gitlab2Sentry cases".format(
                    self.__str__(), g2s_project.full_path
                )
            )
            self.run_stats["not_in_g2s_cases"] += 1
        return False

    def update(self, **kwargs) -> None:
        """
        kwargs: full_path
        description: Full path of project (e.g. my-team/my-project)

        If the fullPath of a specific project is given it will run
        the script only for this project.

        If no full_path is provided it will run the script. If
        creation_days_limit is provided it will fetch all projects
        created after this period. If no it will fetch every project
        """
        full_path = kwargs.get("full_path", None)
        if full_path:
            g2s_project = self._get_gitlab_project(full_path)
            if g2s_project:
                sentry_group_name = g2s_project.group.split("/")[0].strip()
                self._handle_g2s_project(g2s_project, sentry_group_name)  # type: ignore
            else:
                logging.info(
                    "{}: Project with fullPath - {} not found".format(
                        self.__str__(), full_path
                    )
                )
        # If no kwarg is given fetch all
        else:
            groups = self._get_gitlab_groups()

            for group_name in groups.keys():
                sentry_group_name = group_name.split("/")[0].strip()
                self._ensure_sentry_group(sentry_group_name)
                for g2s_project in groups[group_name]:
                    # Skip if sentry is installed or
                    # Project has disabled MRs
                    self._handle_g2s_project(
                        g2s_project, sentry_group_name
                    )  # type: ignore

        for key in self.run_stats.keys():
            logging.info(
                "{}: RESULTS - {}: {}".format(self.__str__(), key, self.run_stats[key])
            )
