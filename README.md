# gitlab2sentry

This project aims to automate Sentry project creation.

Read the documentation in the [Numberly Handbook](https://pages.numberly.in/numberly/handbook/Numberly/Software/Sentry%20at%20numberly/).

## Usage

```
GITLAB_TOKEN='sup3rs3cr3t' SENTRY_TOKEN='m0r3sup3rs3cr3t' make run
```



# gitlab2sentry-alerting

```
[alert.new_issue]
notify = team-uep-back #optional
environment = production #optional

[alert.issue_interval]
notify = team-uep-back #optional
seen = 100 #optional
interval = 1h #optional
environment = staging #optional
```