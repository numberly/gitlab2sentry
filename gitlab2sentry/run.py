import sentry_sdk

from gitlab2sentry import Gitlab2Sentry
from gitlab2sentry.resources import SENTRY_DSN, SENTRY_ENV

if __name__ == "__main__":
    sentry_sdk.init(
        debug=False,
        dsn=SENTRY_DSN,
        environment=SENTRY_ENV,
    )
    runner = Gitlab2Sentry()
    runner.update()
