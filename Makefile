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

build_alerting: switch-env
	docker build -f Dockerfile_alerting -t $(IMG)-alerting:$(TAG) .

push: build
	docker push $(IMG):$(TAG)

push_alerting: build_alerting
	docker push $(IMG)-alerting:$(TAG)

qa:
	isort --profile black . && black . && flake8

run:
	# needed env: GITLAB_TOKEN + SENTRY_TOKEN
	python3 main.py

run_alerting:
	# needed env: GITLAB_TOKEN + SENTRY_TOKEN
	python3 alerting.py

upgrade: push
	helm -n team-infrastructure upgrade -f helm/values-production.yaml --set cronjob.imageTag=$(TAG) gitlab2sentry ./helm
