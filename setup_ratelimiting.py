import logging
import os

import requests
import sentry_sdk
from slugify import slugify

from main import Sentry

GITLAB_URL = os.getenv("GITLAB_URL", "https://gitlab.numberly.in")
GITLAB_TOKEN = os.getenv("GITLAB_TOKEN")
SENTRY_URL = os.getenv("SENTRY_URL", "https://sentry.numberly.net")
SENTRY_TOKEN = os.getenv("SENTRY_TOKEN")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def main():
    sentry = Sentry(SENTRY_URL, auth_token=SENTRY_TOKEN, org_slug="numberly")

    for projects in sentry.get_projects():
        for project in projects:
            slug = project["slug"]
            logging.info("Doing project {}..".format(slug))
            keys = sentry.get_clients_keys("numberly", slug)
            for sentry_key in keys:
                key_id = sentry_key["id"]
                data = sentry.set_rate_limit_for_key(slug, key_id)


if __name__ == "__main__":
    main()
