qa:
	isort --profile black . && black . && flake8

run:
	# needed env: GITLAB_TOKEN + SENTRY_TOKEN
	 python3 main.py
