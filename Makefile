# project name
PRJ	?= gitlab2sentry
REG ?= registry.numberly.in
NS	?= team-infrastructure
IMG	?= $(REG)/$(NS)/$(PRJ)
TAG	?= $(shell git describe --tags)

switch-env:
	make boumbo

boumbo:
	docker login registry.numberly.in
	kubectl config use-context k8s-pr-1
	kubectl config set-context --current --namespace=$(NS)

build: switch-env
	docker build -t $(IMG):$(TAG) .

push: build
	docker push $(IMG):$(TAG)

qa:
	isort --profile black . && black . && flake8

mypy:
	mypy gitlab2sentry/ --config-file .mypy.ini --ignore-missing-imports

run:
	# needed env: GITLAB_TOKEN + SENTRY_TOKEN
	python3 gitlab2sentry/run.py

upgrade: push
	helm secrets -d vault -n team-infrastructure upgrade -f helm/values-production.yaml --set cronjob.imageTag=$(TAG) gitlab2sentry ./helm
