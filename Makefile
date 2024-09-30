# project name
PRJ	?= gitlab2sentry
REG ?= your-registry
NS	?= your-namespace
IMG	?= $(REG)/$(NS)/$(PRJ)
TAG	?= $(shell git describe --tags)

build:
	docker build -t $(IMG):$(TAG) .

push: build
	docker push $(IMG):$(TAG)

test:
	pytest

qa:
	isort --profile black . && black . && flake8

mypy:
	mypy gitlab2sentry/ --config-file .mypy.ini --ignore-missing-imports

run:
	# needed env: GITLAB_TOKEN + SENTRY_TOKEN
	python3 gitlab2sentry/run.py

upgrade: push
	helm secrets -d vault -n $(NS) upgrade -f helm/values-production.yaml --set cronjob.imageTag=$(TAG) gitlab2sentry ./helm
