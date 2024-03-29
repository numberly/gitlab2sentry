TEST_SENTRY_URL = "http://sentry.test.com"
TEST_SENTRY_DSN = "http://test.sentry.test.com"
TEST_SENTRY_TOKEN = "test-token"
TEST_GITLAB_URL = "http://test-gitlab-url"
TEST_GITLAB_TOKEN = "test-token"

TEST_SENTRY_ENV = "test"
TEST_SENTRY_ORG_SLUG = "test_org"

# DSN MR configuration.
TEST_DSN_MR_CONTENT = """
## File generated by gitlab2sentry
[defaults]
url = {sentry_url}
dsn = {dsn}
project = {project_slug}
"""
TEST_DSN_BRANCH_NAME = "auto_add_sentry_dsn"
TEST_DSN_MR_TITLE = (
    "[gitlab2sentry] Merge me to add your sentry DSN to {project_name}"
)
TEST_DSN_MR_DESCRIPTION = """
{mentions} Congrats, your Sentry project has been
created, merge this
to finalize your Sentry integration of
{name_with_namespace} :clap: :cookie:
"""

# Sentryclirc MR configuration.
TEST_SENTRYCLIRC_MR_CONTENT = """
## File generated by gitlab2sentry
[defaults]
url = {sentry_url}
"""
TEST_SENTRYCLIRC_BRANCH_NAME = "auto_add_sentry"
TEST_SENTRYCLIRC_MR_TITLE = (
    "[gitlab2sentry] Merge me to add sentry to {project_name} or close me"
)
TEST_SENTRYCLIRC_FILEPATH = ".sentryclirc"
TEST_SENTRYCLIRC_COM_MSG = "Update .sentryclirc"
TEST_SENTRYCLIRC_MR_DESCRIPTION = """
{mentions} Merge this and it will automatically
create a Sentry project \n
for {name_with_namespace} :cookie:
"""

# Gitlab Configuration.
TEST_GITLAB_GRAPHQL_SUFFIX = "test-content"
TEST_GITLAB_GRAPHQL_TIMEOUT = 10
TEST_GITLAB_GRAPHQL_PAGE_LENGTH = 0
TEST_GITLAB_AUTHOR_EMAIL = "test-content"
TEST_GITLAB_AUTHOR_NAME = "test-content"
TEST_GITLAB_RMV_SRC_BRANCH = True
TEST_GITLAB_MR_KEYWORD = "sentry"