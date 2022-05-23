import logging
from collections import Counter, namedtuple
from datetime import datetime, timedelta
from typing import Any, Dict, List, NamedTuple, Optional

from gitlab2sentry.exceptions import (
    SentryProjectCreationFailed,
    SentryProjectKeyIDNotFound,
)
from gitlab2sentry.resources import (
    DSN_MR_TITLE,
    GITLAB_GROUP_IDENTIFIER,
    GITLAB_TOKEN,
    GITLAB_URL,
    SENTRY_ORG_SLUG,
    SENTRY_TOKEN,
    SENTRY_URL,
    SENTRYCLIRC_FILEPATH,
    SENTRYCLIRC_MR_TITLE,
)
from gitlab2sentry.utils import GitlabProvider, SentryProvider

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


G2SProject = namedtuple(
    "G2SProject",
    [
        "id" "name",
        "group",
        "mrs_enabled",
        "name_with_namespace",
        "path_with_namespace",
        "has_sentryclirc_file",
        "sentryclirc_mr_state",
        "dsn_mr_state",
    ],
)


class Gitlab2Sentry:
    def __init__(self):
        self.gitlab_provider = self._get_gitlab_provider()
        self.sentry_provider = self._get_sentry_provider()
        self.run_stats = Counter()
        self.yesterday = datetime.utcnow() - timedelta(hours=24)
        self.sentry_groups = set()

    def __str__(self) -> str:
        return "<Gitlab2Sentry>"

    def _get_gitlab_provider(self) -> GitlabProvider:
        return GitlabProvider(GITLAB_URL, GITLAB_TOKEN)

    def _get_sentry_provider(self) -> SentryProvider:
        return SentryProvider(SENTRY_URL, SENTRY_TOKEN, SENTRY_ORG_SLUG)

    def _ensure_sentry_group(self, group_name: str, name: str) -> None:
        logging.debug("{}: Handling gitlab group {}".format(self.__str__(), group_name))
        if name not in self.sentry_groups:
            self.sentry_provider.ensure_sentry_team(name)
            self.sentry_groups.add(name)

    def _is_opened_mr(
        self, name_with_namespace: str, state: Optional[str], label: str
    ) -> bool:
        if state and state == "opened":
            logging.info(
                "{}: Project {} has a pending {} MR".format(
                    self.__str__(), name_with_namespace, label
                )
            )
            self.run_stats[f"mr_{label}_waiting"] += 1
            return True
        else:
            return False

    def _opened_dsn_mr_found(self, g2s_project: NamedTuple) -> bool:
        return self._is_opened_mr(
            g2s_project.name_with_namespace, g2s_project.dsn_mr_state, "dsn"
        )

    def _opened_sentryclirc_mr_found(self, g2s_project: NamedTuple) -> bool:
        return self._is_opened_mr(
            g2s_project.name_with_namespace,
            g2s_project.sentryclirc_mr_state,
            "sentryclirc",
        )

    def _is_closed_mr(
        self, name_with_namespace: str, state: Optional[str], label: str
    ) -> bool:
        if state and state == "opened":
            logging.info(
                "{}: Project {} has a closed {} MR".format(
                    self.__str__(), name_with_namespace, label
                )
            )
            self.run_stats[f"mr_{label}_waiting"] += 1

            return True
        else:
            return False

    def _closed_dsn_mr_found(self, g2s_project: NamedTuple) -> bool:
        return self._is_closed_mr(
            g2s_project.name_with_namespace, g2s_project.dsn_mr_state, "dsn"
        )

    def _closed_sentryclirc_mr_found(self, g2s_project: NamedTuple) -> bool:
        return self._is_closed_mr(
            g2s_project.name_with_namespace,
            g2s_project.sentryclirc_mr_state,
            "sentryclirc",
        )

    def _get_mr_states(self, mr_list: Optional[List[Dict[str, Any]]]) -> tuple:
        sentryclirc_mr_state, dsn_mr_state = None, None
        if mr_list:
            for mr in mr_list:
                if mr["title"] == SENTRYCLIRC_MR_TITLE:
                    sentryclirc_mr_state = mr["state"]
                elif mr["title"] == DSN_MR_TITLE:
                    dsn_mr_state = mr["state"]
                else:
                    pass
        return sentryclirc_mr_state, dsn_mr_state

    def _is_group_project(self, group: Optional[Dict[str, str]]) -> bool:
        return group and group["name"] and GITLAB_GROUP_IDENTIFIER in group["name"]

    def _get_sentryclirc_file(self, blob: Dict[str, Any]) -> tuple:
        has_sentryclirc_file, has_dsn = False, False
        if blob and blob[0]["name"] == SENTRYCLIRC_FILEPATH:
            has_sentryclirc_file = True
            if "dns=" in blob[0]["plainData"]:
                has_dsn = True
        else:
            return has_sentryclirc_file, has_dsn

    def _get_gitlab_groups(self):
        groups = dict()
        request_gen = self.gitlab_provider._get_g2s_projects()
        page_results = [page for page in request_gen]
        for page_result in page_results:
            for result in page_result:
                sentryclirc_mr_state, dsn_mr_state = None, None
                if self._is_group_project(result["node"]["group"]):
                    group_name = result["node"]["group"]["name"]

                    if not groups.get(group_name):
                        groups[group_name] = list()

                    sentryclirc_mr_state, dsn_mr_state = self._get_mr_states(
                        result["node"]["mergeRequests"]["nodes"]
                    )

                    has_sentryclirc_file, has_dsn = self._get_sentryclirc_file(
                        result["node"]["repository"]["blobs"]["nodes"]
                    )
                    if not self._has_already_sentry(sentryclirc_mr_state, dsn_mr_state):
                        name_with_namespace = "{}/{}".format(
                            result["node"]["name"], group_name
                        )
                        path_with_namespace = "{}/{}".format(
                            result["node"]["name"], group_name
                        )
                        groups[group_name].append(
                            G2SProject(
                                result["node"]["name"],
                                result["node"]["group"]["name"],
                                result["node"]["mergeRequestsEnabled"],
                                name_with_namespace,
                                path_with_namespace,
                                has_sentryclirc_file,
                                has_dsn,
                                sentryclirc_mr_state,
                                dsn_mr_state,
                            )
                        )
        return groups

    def _create_sentry_project(
        self, project_path: str, sentry_group_name: str, name_with_namespace: str
    ) -> Optional[Dict[str, Any]]:
        sentry_project_name = "-".join(project_path.split("/")[1:])
        logging.info(
            "{}: Creating sentry project {}".format(self.__str__(), sentry_project_name)
        )
        try:
            return self.sentry_provider.create_or_get_project(
                sentry_group_name,
                sentry_project_name,
            )
        except SentryProjectCreationFailed as creation_err:
            logging.warning(
                "{} Project {} - failed to create sentry project: {}".format(
                    self.__str__(), name_with_namespace, str(creation_err)
                )
            )
        except Exception as err:
            logging.warning(
                "{} Project {} failed to get/create its sentry project: {}".format(
                    self.__str__(), name_with_namespace, str(err)
                )
            )
        return None

    def update(self) -> Dict[str, Any]:
        """
        Update sentry projects, queries with GraphQL the given
        gitlab url. It loops through the results and skips or creates MergeRequests
        for these cases:
            1. Project is already in sentry [skip]
            2.
        """
        groups = self._get_gitlab_groups()

        for group_name in groups.keys():
            sentry_group_name = group_name.full_name.split("/")[0].strip()
            self._ensure_sentry_group(group_name, sentry_group_name)

            for g2s_project in groups[group_name]:

                # Skip if sentry is installed or
                # Project has disabled MRs
                if not g2s_project.mrs_enabled or (
                    g2s_project.has_sentryclirc_file and g2s_project.has_dsn
                ):
                    continue

                # Case sentryclirc found but
                # dsn not found: Pending MR
                if g2s_project.has_sentryclirc_file and not g2s_project.has_dsn:

                    if self._opened_mr_found(
                        g2s_project.name_with_namespace, g2s_project, "dsn"
                    ):
                        continue
                    else:
                        sentry_project = self._create_sentry_project(
                            g2s_project.path_with_namespace,
                            sentry_group_name,
                            g2s_project.name_with_namespace,
                        )

                        # If Sentry fails to create project skip
                        if not sentry_project:
                            continue

                        try:
                            dsn = self.sentry_provider.set_rate_limit_for_key(
                                sentry_project["slug"]
                            )
                        except SentryProjectKeyIDNotFound as key_id_err:
                            logging.warning(
                                "{}: Project {} sentry key id not found: {}".format(
                                    self.__str__(),
                                    g2s_project.name_with_namespace,
                                    key_id_err,
                                )
                            )
                            continue

                        logging.info(
                            "{}: Project {} sentry dsn: {}. Opening dsn MR".format(
                                self.__str__(), g2s_project.name_with_namespace, dsn
                            )
                        )
                        self.gitlab_provider.create_dsn_mr(g2s_project, dsn)
                        self.run_stats["mr_dsn_created"] += 1

                # Case sentryclirc not found:
                # Declined sentryclirc MR or
                # need to create one
                elif not g2s_project.has_sentryclirc_file:
                    if self._opened_sentryclirc_mr_found(
                        g2s_project
                    ) or self._closed_sentryclirc_mr_found(g2s_project):
                        break
                    else:
                        logging.info(
                            "{}: Project {} needs sentry .sentryclirc MR".format(
                                self.__str__(), g2s_project.name_with_namespace
                            )
                        )
                        self.run_stats["mr_sentryclirc_created"] += 1
                        try:
                            self.gitlab_provider.create_sentryclirc_mr(g2s_project)
                        except Exception as err:
                            logging.warning(
                                "{} project {} failed to create the .sentryclirc MR ({})".format(  # noqa E501
                                    self.__str__(),
                                    g2s_project.name_with_namespace,
                                    str(err),
                                )
                            )
                else:
                    pass

        return dict(self.run_stats)
