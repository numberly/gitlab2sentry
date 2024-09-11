# gitlab2sentry

Getting a Sentry project for each of your Gitlab repositories is just one MR merge away!

Gitlab2Sentry will create a Sentry project associated to each of your Gitlab repositories using a Merge Request based automated workflow.

Any new Gitlab repository you create will be offered a Sentry project if you accept (merge the proposal MR) it with respect to the Gitlab group owning it!

## Two-Steps process

1. After creating your new project on Gitlab, ```gitlab2sentry``` will create a first Merge Request asking if you want it to create an associated Sentry project for it. This Merge Request will contain the creation of a ```.sentryclirc``` file which, if you merge it, will be contributed back the newly created Sentry project ```DSN``` for this project.

2. If you merged the first Merge Request, ```gitlab2sentry``` will create a second one to update the newly created ```.sentryclirc``` file with the ```DSN``` of the sentry project. Moreover, after the merge of the first Merge Request ```gitlabsentry``` will create a new ```sentry project```, update its rate limit and save the ```DSN``` inside ```.sentryclirc```. Once you have merged this second Merge Request everything will be set up!

**NOTE**: ```Gitlab2Sentry``` looks only for group projects and searches for MRs having specific keyword inside (check "Configuration" section)


## Run locally

You can install all requirements for this project with:

```bash
python3 -m venv venv
pip3 install -r requirements.txt
source venv/bin/activate
```

After the installation of all requirements you have to:

```bash
export SENTRY_URL=<your sentry's url>
export SENTRY_TOKEN=<your sentry token>
export SENTRY_ENV=<your environment - default production>
export GITLAB_TOKEN=<your gitlab token>
export GITLAB_URL=<your gitlab url>
python3 run.py
```

## Deployment

We prefer to deploy and manage ```gitlab2sentry``` with ```helm```. Inside ```helm/``` folder you can find an example deployment.

You can upgrade your deployment with:

```bash
make upgrade
```

## Configuration

```Gitlab2Sentry``` requires some configuration in 3 specific files.

1. First of all you have to configure the ```helm/values-production.yaml``` file where everything is configured for the ```gitlab2sentry``` service. Here you can find a description for every field:

```yaml
  # Sentry values
  - name: SENTRY_TOKEN
    valueFrom:
      secretKeyRef:
        key: SENTRY_TOKEN
        name: gitlab2sentry-production
  - name: SENTRY_DSN
    value: your-sentry-dsn
  - name: SENTRY_URL
    value: your-sentry-url
  - name: SENTRY_ORG_SLUG
    value: your-sentry-organization-slug
  # Gitlab values
  - name: GITLAB_TOKEN
    valueFrom:
      secretKeyRef:
        key: GITLAB_TOKEN
        name: your-secret
  - name: GITLAB_URL
    value: your-gitlab-url
    # DSN MR (1) values
  - name: GITLAB_DSN_MR_CONTENT
    value: the content of your dsn mr
  - name: GITLAB_DSN_MR_DESCRIPTION
    value: the description of your dsn mr
  - name: GITLAB_DSN_MR_BRANCH_NAME
    value: your-branch-name
  - name: GITLAB_DSN_MR_TITLE
    value: "your-dsn-mr-title"
    # Sentryclirc MR (2) values
  - name: GITLAB_SENTRYCLIRC_MR_CONTENT
    value: your-sentryclirc-mr-content
  - name: GITLAB_SENTRYCLIRC_MR_DESCRIPTION
    value: your-sentryclirc-mr-description
  - name: GITLAB_SENTRYCLIRC_MR_BRANCH_NAME
    value: your-sentryclirc-mr-branch-name
  - name: GITLAB_SENTRYCLIRC_MR_FILEPATH
    value: .sentryclirc
  - name: GITLAB_SENTRYCLIRC_MR_COMMIT_MSG
    value: your-commit-msg
  - name: GITLAB_SENTRYCLIRC_MR_TITLE
    value: "your sentryclirc mr title"
    # Gitlab configuration values
  - name: GITLAB_GRAPHQL_SUFFIX
    value: api/graphql
  # - name: GITLAB_MENTIONS
  #   value:
  #     - "@all"
  - name: GITLAB_MENTIONS_ACCESS_LEVEL
    value: 40 # maintainer
  - name: GITLAB_CREATION_DAYS_LIMIT
    value: 60 # Max days old per project
  - name: GITLAB_MR_KEYWORD
    value: sentry # key word for searching mrs
  - name: GITLAB_REMOVE_SOURCE
    value: true # If the mr will remove the source branch
  - name: GITLAB_GROUP_IDENTIFIER
    value: your-group-identifier # will look only for group projects having this identifier
  - name: GITLAB_AIOHTTP_TIMEOUT
    value: 60
  - name: GITLAB_GRAPHQL_PAGE_LENGTH
    value: 100
```

2. If you want to follow the ```helm``` deployment process you will have to fill your details into the ```helm/values-production.yaml``` and ```helm/Chart.yaml```.

3. You can update ```REG ?= your-registry``` and ```NS	?= your-namespace``` values inside ```Makefile```.

## Manual run

If you want to update a specific project (for example if the project has a very big name or is older than the ```GITLAB_CREATION_DAYS_LIMIT``` value), you can run the ```gitlab2sentry``` manually.

* First, you have to ```export``` all env variables which are listed above in the ```helm/values-production.yaml``` file.

* Next you can run the following commands:

```python
>>> from gitlab2sentry import Gitlab2Sentry
>>> g2s = Gitlab2Sentry()
>>> g2s.update(full_path="projects_full_path", custom_name="optional_custom_name")
```

## Contributions & comments welcomed

Numberly decided to Open Source this project because it saves a lot of time internally to all our developers and helped foster the mass adoption of Sentry in all our Tech teams. We hope this project can benefit someone else.

Feel free to ask questions, suggest improvements and of course contribute features or fixes you might need!

