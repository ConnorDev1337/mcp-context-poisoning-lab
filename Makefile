.PHONY: install dev lint test demo bench-ollama report clean help

SCENARIOS ?= lab/scenarios
OUT       ?= runs
REPS      ?= 10
MODEL     ?= qwen2.5:7b-instruct
BASE_URL  ?= http://localhost:11434/v1

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'

install:  ## Install the package with all extras
	pip install -e ".[services,agent,dev,plot]"

dev:  ## Install the package in development mode
	pip install -e ".[dev]"

lint:  ## Run ruff linter and formatter check
	ruff check src tests scripts poc
	ruff format --check src tests scripts poc

test:  ## Run the test suite
	pytest -q

demo:  ## Run deterministic mock controls over all scenarios
	mcplab demo --scenarios $(SCENARIOS) --out-dir $(OUT)
	@echo "---"
	@cat $(OUT)/report.md

bench-ollama:  ## Run the benchmark with a local Ollama model (set MODEL= REPS=)
	mcplab run --backend ollama --model $(MODEL) \
	  --base-url $(BASE_URL) \
	  --scenarios $(SCENARIOS) \
	  --reps $(REPS) \
	  --out $(OUT)/raw-$(MODEL).jsonl
	mcplab report --in $(OUT)/raw-$(MODEL).jsonl --out-dir $(OUT)/$(MODEL)
	@echo "---"
	@cat $(OUT)/$(MODEL)/report.md

report:  ## Generate report from existing raw.jsonl
	mcplab report --in $(OUT)/raw.jsonl --out-dir $(OUT)

list:  ## List all scenarios, objectives, vectors and defenses
	mcplab list --scenarios $(SCENARIOS)

wire:  ## Start the over-the-wire lab with Docker
	docker compose -f lab/docker-compose.yml --profile wire up --build

clean:  ## Remove run artifacts and build caches
	rm -rf runs/ dist/ build/ .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '*.egg-info' -exec rm -rf {} + 2>/dev/null || true
