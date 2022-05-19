import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from gitlab.v4.objects import Project, ProjectMergeRequest

from gitlab2sentry.exceptions import (
    SentryProjectCreationFailed,
    SentryProjectKeyIDNotFound,
)
from gitlab2sentry.resources import (
    GITLAB_MR_KEYWORD,
    GITLAB_TOKEN,
    GITLAB_URL,
    SENTRY_ORG_SLUG,
    SENTRY_TOKEN,
    SENTRY_URL,
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
        self.run_stats = Counter()
        self.yesterday = datetime.utcnow() - timedelta(hours=24)
        self.sentry_groups = set()

    def __str__(self) -> str:
        return "<Gitlab2Sentry>"

    def _get_gitlab_provider(self) -> GitlabProvider:
        return GitlabProvider(GITLAB_URL, GITLAB_TOKEN)

    def _get_sentry_provider(self) -> SentryProvider:
        return SentryProvider(SENTRY_URL, SENTRY_TOKEN, SENTRY_ORG_SLUG)

    def _get_mr_counters(self) -> Dict[str, List[ProjectMergeRequest]]:
        by_project = defaultdict(list)
        for mr in self.gitlab_provider.mrs:
            if GITLAB_MR_KEYWORD in mr.title.lower():
                by_project[mr.project_id].append(mr)
        return by_project

    def _ensure_sentry_group(self, group, name) -> None:
        logging.debug(
            "{}: Handling gitlab group {}".format(self.__str(), group.full_name)
        )
        if name not in self.sentry_groups:
            self.sentry_provider.ensure_sentry_team(name)
            self.sentry_groups.add(name)

    def _project_mrs_disabled(self, project: Project) -> bool:
        if not project.merge_requests_enabled:
            logging.info(
                "{}: Project {} does not accept MRs".format(
                    self.__str__(), project.name_with_namespace
                )
            )
            self.run_stats["mr_disabled"] += 1
            return True
        else:
            return False

    def _project_created_yesterday(self, project: Project) -> bool:
        if (
            datetime.fromisoformat(project.last_activity_at.replace("Z", ""))
            < self.yesterday
        ):
            logging.info(
                "{}: Project {} skipped due to last".format(
                    self.__str__(), project.name_with_namespace
                ),
                "{}: Activity being {}".format(
                    self.__str__(), project.last_activity_at
                ),
            )
            return False
        else:
            return True

    def _project_has_dsn_file(self, project: Project) -> bool:
        has_sentryclirc, has_dsn = self.gitlab_provider.get_sentryclirc(project.id)

        if has_sentryclirc and has_dsn:
            logging.info(
                "{}: Project {} has a sentry project".format(
                    self.__str__(), project.name_with_namespace
                )
            )
            self.run_stats["has_sentry_dsn"] += 1

        return has_sentryclirc, has_dsn

    def _opened_mr_found(
        self, name_with_namespace: Project, mr: ProjectMergeRequest, mr_type: str
    ) -> bool:
        if mr.state == "opened":
            logging.info(
                "{}: Project {} has a pending {} MR".format(
                    self.__str__(), name_with_namespace, mr_type
                )
            )
            self.run_stats[f"mr_{mr_type}_waiting"] += 1
            return True
        else:
            return False

    def _create_sentry_project_created(
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
        mr_by_project = self._get_mr_counters()

        # loop for all team gitlab groups
        for group in self.gitlab_provider.groups:

            # Only team groups will be taken into account
            if not group.full_name.startswith("team-"):
                continue

            sentry_group_name = group.full_name.split("/")[0].strip()

            self._ensure_sentry_group(sentry_group_name)

            for project in group.projects.list(all=True, archived=False):
                # Skip MR if:
                # Project has MR disabled
                # Project was created before yesterday
                # Has both dsn and sentryclirc files
                has_sentryclirc, has_dsn = self._project_has_dsn_file(project)
                if (
                    self._project_mrs_disabled(project)
                    or not self._project_created_yesterday(project)
                    or (has_sentryclirc and has_dsn)
                ):
                    continue

                # Case dsn not found: Pending MR
                if has_sentryclirc and not has_dsn:
                    for mr in mr_by_project[project.id]:
                        if self._opened_mr_found(
                            project.name_with_namespace, mr, "dsn"
                        ):
                            break
                    else:
                        sentry_project = self._sentry_project_created(
                            self,
                            project.path_with_namespace,
                            sentry_group_name,
                            project.name_with_namespace,
                        )

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
                                    project.name_with_namespace,
                                    key_id_err,
                                )
                            )
                            continue

                        logging.info(
                            "{}: Project {} sentry dsn: {}".format(
                                self.__str__(), project.name_with_namespace, dsn
                            )
                        )
                        logging.info(
                            "{}: Project {} needs sentry dsn MR".format(
                                self.__str__(), project.name_with_namespace
                            )
                        )
                        self.gitlab_provider.create_dsn_mr(project, dsn)
                        self.run_stats["mr_dsn_created"] += 1

                # Case sentryclirc not found:
                # Declined sentryclirc MR or
                # need to create one
                elif not has_sentryclirc:
                    for mr in mr_by_project[project.id]:
                        if self._opened_mr_found(
                            project.name_with_namespace, mr, "sentryclirc"
                        ):
                            break
                        elif self._closed_mr_found(project.name_with_namespace, mr):
                            logging.info(
                                "{} Project {} declined our sentryclirc MR".format(
                                    self.__str__(), project.name_with_namespace
                                )
                            )
                            self.run_stats["mr_sentryclirc_closed"] += 1
                            break
                    else:
                        logging.info(
                            "{}: Project {} needs sentry .sentryclirc MR".format(
                                self.__str__(), project.name_with_namespace
                            )
                        )
                        self.run_stats["mr_sentryclirc_created"] += 1
                        try:
                            self.gitlab_provider.create_sentryclirc_mr(project)
                        except Exception as err:
                            logging.warning(
                                "{} project {} failed to create the .sentryclirc MR ({})".format(
                                    self.__str__(),
                                    project.name_with_namespace,
                                    str(err),
                                )
                            )
        return dict(self.run_stats)
