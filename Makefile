PYTHON ?= python3
PORT   ?= 8000

.PHONY: help install experiment study-quick export test test-py test-web serve

help:            ## list targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

install:         ## install Python dependencies
	$(PYTHON) -m pip install -r requirements.txt

experiment:      ## original static-vs-adaptive experiment -> results/results.json
	cd src && $(PYTHON) run_experiment.py

study-quick:     ## routing-study smoke test (a few minutes)
	cd src && $(PYTHON) scenario_experiment.py --quick

export:          ## write results/hybrid_v3 into index.html
	cd src && $(PYTHON) export_dashboard.py

test: test-py test-web ## run all tests

test-py:         ## Python simulation tests
	$(PYTHON) -m unittest discover -s tests -v

test-web:        ## dashboard tests (Node 20+)
	node --test tests/dashboard.test.mjs

serve:           ## serve the dashboard on http://localhost:$(PORT)
	$(PYTHON) -m http.server $(PORT)
