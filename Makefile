.DEFAULT_GOAL := all
sources = dependencies tests

.PHONY: .pdm  ## Check that PDM is installed
.pdm:
	@pdm -V || echo 'Please install PDM: https://pdm.fming.dev/latest/#installation'

.PHONY: .pre-commit  ## Check that pre-commit is installed
.pre-commit:
	@pre-commit -V || echo 'Please install pre-commit: https://pre-commit.com/'

.PHONY: install  ## Install the package, dependencies, and pre-commit for local development
install: .pdm .pre-commit
	pdm info
	pdm install --group :all
	pre-commit install --install-hooks

.PHONY: refresh-lockfiles  ## Sync lockfiles with requirements files.
refresh-lockfiles: .pdm
	pdm update --update-reuse --group :all

.PHONY: rebuild-lockfiles  ## Rebuild lockfiles from scratch, updating all dependencies
rebuild-lockfiles: .pdm
	pdm update --update-eager --group :all

.PHONY: format  ## Auto-format python source files
format: .pdm
	pdm run ruff --fix $(sources)
	pdm run ruff format $(sources)

.PHONY: lint  ## Lint python source files
lint: .pdm
	pdm run ruff $(sources)
	pdm run ruff format --check $(sources)

.PHONY: codespell  ## Use Codespell to do spellchecking
codespell: .pre-commit
	pre-commit run codespell --all-files

.PHONY: typecheck  ## Perform type-checking
typecheck: .pre-commit .pdm
	pre-commit run typecheck --all-files

.PHONY: test  ## Run all tests, skipping the type-checker integration tests
test: .pdm
	pdm run coverage run -m pytest --durations=10

.PHONY: testcov  ## Run tests and generate a coverage report, skipping the type-checker integration tests
testcov: test
	@echo "building coverage html"
	@pdm run coverage html
	@echo "building coverage lcov"
	@pdm run coverage lcov


.PHONY: all  ## Run the standard set of checks performed in CI
all: lint typecheck codespell testcov

.PHONY: help  ## Display this message
help:
	@grep -E \
		'^.PHONY: .*?## .*$$' $(MAKEFILE_LIST) | \
		sort | \
		awk 'BEGIN {FS = ".PHONY: |## "}; {printf "\033[36m%-19s\033[0m %s\n", $$2, $$3}'

