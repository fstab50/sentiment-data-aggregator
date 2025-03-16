#---------------------------------------------------------------------------------------#
#                                                                                       #
#	 - Makefile, version 1.8.8                                                          #
#	 - PROJECT:  spotprice-lambda                                                       #
# 	 - copyright, Blake Huber.  All rights reserved.                                    #
#                                                                                       #
#---------------------------------------------------------------------------------------#


PROJECT := spotprice-lambda
PYTHON_VERSION := python3.8
CUR_DIR = $(shell pwd)
VENV_DIR := $(CUR_DIR)/venv
PIP_CALL := $(VENV_DIR)/bin/pip
AWS_PROFILE := $$(cat $(CUR_DIR)/aws.profile)
PYTHON3_PATH := $(shell which $(PYTHON_VERSION))
MAKE := $(shell which make)

AWS_REGION := us-east-2
TARGET_ENV := dev

S3_BASEPATH := s3-$(AWS_REGION)-install-$(TARGET_ENV)

MODULE_PATH := $(CUR_DIR)/Code
DOC_PATH := $(CUR_DIR)/doc
REQUIREMENT = $(CUR_DIR)/requirements.txt
ZIPNAME = spotprices-codebase.zip
S3KEY = Code/$(PROJECT)
CFN_TEMPLATE = $(PROJECT).template.yml
LAMBDA_NAME = $(PROJECT)


# --- targets -------------------------------------------------------------------------------------


.PHONY: pre-build
pre-build:   ## Remove residual build artifacts
	rm -rf $(CUR_DIR)/dist
	mkdir $(CUR_DIR)/dist


setup-venv: $(VENV_DIR)  ## Setup virtual environment

$(VENV_DIR): pre-build      ## Create and activiate python virtual env
	$(PYTHON3_PATH) -m venv $(VENV_DIR)
	. $(VENV_DIR)/bin/activate && $(PIP_CALL) install -U setuptools pip && \
	$(PIP_CALL) install -r $(CUR_DIR)/requirements.txt || true


.PHONY: test
test: setup-venv   ## Execute unittests
	if [ $(JOB_NAME) ]; then coverage run --source Code -m py.test $(CUR_DIR)/tests; coverage html; else \
	bash $(CUR_DIR)/scripts/make-test.sh $(CUR_DIR) $(VENV_DIR) $(MODULE_PATH) $(PDB); fi


build: setup-venv    ## Build lambda zip archive
	cd $(CUR_DIR)/Code && zip -r $(CUR_DIR)/dist/$(ZIPNAME) *.py ls
	cd $(VENV_DIR)/lib/*/site-packages && zip -ur $(CUR_DIR)/dist/$(ZIPNAME) *
	cd $(CUR_DIR)/cloudformation && cp * $(CUR_DIR)/dist/
	sed -i -e 's/\__MPCBUILDVERSION__/$(MPCBUILDVERSION)/' $(CUR_DIR)/dist/$(CFN_TEMPLATE)


validate:	## Validate cloudformation template for errors
	@echo "CloudFormation validation"
	aws cloudformation validate-template --region $(AWS_REGION) \
		--template-body file://$(CUR_DIR)/cloudformation/$(CFN_TEMPLATE) \
		--profile $(AWS_PROFILE);


deploy: clean build		## Deploy zip archive, cloudformation template to Amazon S3
	$(eval S3_BUCKET_PREFIX = s3-$(AWS_REGION)-install)
	@echo "Uploading zip file $(ZIPNAME) to Amazon S3"
	aws s3 cp $(CUR_DIR)/dist/$(ZIPNAME) s3://$(S3_BUCKET_PREFIX)-$(TARGET_ENV)/$(S3KEY)/$(ZIPNAME) --profile $(AWS_PROFILE)
	@echo "Uploading cloudformation file $(CFN_TEMPLATE) to Amazon S3"
	aws s3 cp $(CUR_DIR)/dist/$(CFN_TEMPLATE) s3://$(S3_BUCKET_PREFIX)-$(TARGET_ENV)/CFT/$(CFN_TEMPLATE) --profile $(AWS_PROFILE)


.PHONY:  dev-deploy
dev-deploy:		## Deploy lambda zip archive to development S3 bucket
	AWS_REGION=us-east-2 && TARGET_ENV=dev && versionpro --update && $(MAKE) deploy


.PHONY: disable
disable: setup-venv  ## Disable cloudwatch rules to prevent spotprice loader lambda from executing
	if [[ "$$(gcreds -s | grep expired)" ]] || [[ ! "$$(which rulemanager)" ]]; then \
		echo -e "\nValid role credentials were not found or rulemanager utility missing.\n"; \
	else . $(VENV_DIR)/bin/activate && cd $(CUR_DIR) && \
		rulemanager --disable --keyword spot --profile $(AWS_PROFILE) --region us-east-2; fi;


.PHONY: enable
enable:   ## Enable cloudwatch rules to trigger spotprice loader lambda
	if [[ "$$(gcreds -s | grep expired)" ]] || [[ ! "$$(which rulemanager)" ]]; then \
		echo -e "\nValid role credentials were not found or rulemanager utility missing.\n"; \
	else . $(VENV_DIR)/bin/activate && cd $(CUR_DIR) && \
		rulemanager --enable --keyword spot --profile $(AWS_PROFILE) --region us-east-2; fi;


.PHONY:  qa-deploy
qa-deploy:		## Deploy lambda zip archive to qa S3 bucket
	AWS_REGION=us-east-2 && TARGET_ENV=qa && versionpro --update && $(MAKE) deploy


.PHONY:  prod-deploy
prod-deploy:			## Deploy lambda zip archive to production S3 bucket
	AWS_REGION=us-east-2 && TARGET_ENV=prod && versionpro --update && $(MAKE) deploy


.PHONY: simulate
simulate:   ## Simulate a build to show version labels to be applied
	cd $(CUR_DIR) && versionpro --dryrun;


.PHONY: trigger-times
trigger-times:   ## Display Amazon Cloudwatch rule execution times
	cd $(CUR_DIR) && rulemanager --view --keyword spot --profile default --region us-east-2;


.PHONY: update
update:  build		## Update code for installed lambda function
	bash $(CUR_DIR)/scripts/update-function.sh --accounts da \
		--zipfile $(CUR_DIR)/dist/$(ZIPNAME) \
		--region $(AWS_REGION) \
		--skip;


.PHONY: help
help:   ## Print help index
	@printf "\n\033[0m %-15s\033[0m %-13s\u001b[37;1m%-15s\u001b[0m\n\n" " " "make targets: " $(PROJECT)
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {sub("\\\\n",sprintf("\n%22c"," "), $$2);printf "\033[0m%-2s\033[36m%-15s\033[33m %-8s\033[0m%-5s\n\n"," ", $$1, "-->", $$2}' $(MAKEFILE_LIST)
	@printf "\u001b[37;0m%-2s\u001b[37;0m%-2s\n\n" " " "______________________________________________________________________"
	@printf "\u001b[37;1m%-3s\u001b[37;1m%-3s\033[0m %-6s\u001b[44;1m%-9s\u001b[37;0m%-15s\n\n" " " "  make" "zero-build[deb|rpm] " "VERSION=X" " to build specific version id"


clean:    ## Clean build artifacts
	rm -rf $(CUR_DIR)/dist || true
	rm -rf $(VENV_DIR) || true
	rm -rf $(CUR_DIR)/Code/__pycache__ || true
	rm -rf $(CUR_DIR)/tests/__pycache__ || true
	rm -rf $(CUR_DIR)/.pytest_cache || true
