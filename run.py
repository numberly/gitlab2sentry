import sentry_sdk

from gitlab2sentry import Gitlab2Sentry
from gitlab2sentry.resources import settings
if __name__ == "__main__":
    sentry_sdk.init(  # type: ignore
        debug=False,
        dsn=settings.sentry_dsn,
        environment=settings.sentry_env,
    )
    runner = Gitlab2Sentry()
    runner.update()
