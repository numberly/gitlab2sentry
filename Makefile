# project name
PRJ	?= gitlab2sentry
REG ?= registry.numberly.in
NS	?= team-infrastructure
IMG	?= $(REG)/$(NS)/$(PRJ)
TAG	?= $(shell grep ref .git/HEAD | sed 's@.*/\(.*\)@\1@g')

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

run:
	# needed env: GITLAB_TOKEN + SENTRY_TOKEN
	python3 main.py

upgrade: push
	helm -n team-infrastructure upgrade -f helm/values-production.yaml gitlab2sentry ./helm
