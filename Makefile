# Add project-level Makefile commands here
.PHONY: dev test lint fmt clean test-core test-records test-stw test-plugins bench check-docs check-docs-sync \
	check-doc-links check-plugin-deps test-bundles docs-bundles

# The project baseline is Python 3.10+. Override this explicitly when several
# interpreters are installed, e.g. ``make WAVEFORM_PYTHON=/path/to/python``.
WAVEFORM_PYTHON ?= python3

dev:
	pip install -e ".[dev]"

test:
	./scripts/run_tests.sh

lint:
	ruff check .
	black --check waveform_analysis tests

fmt:
	black waveform_analysis tests
	ruff check . --fix

clean:
	rm -rf build dist *.egg-info htmlcov .coverage .coverage.* .pytest_cache .mypy_cache .ruff_cache \
		__pycache__ .venv node_modules outputs test_output

test-core:
	pytest -q tests -k "not plugins"

test-records:
	pytest -q tests -k "records"

test-stw:
	pytest -q tests -k "waveform_struct or waveform_width or st_waveforms"

test-plugins: test-records test-stw

bench:
	python scripts/benchmark_io.py --n-files 50 --n-channels 2 --n-samples 200 --reps 2

check-docs:
	@$(WAVEFORM_PYTHON) scripts/check_doc_anchors.py

check-docs-sync:
	@$(WAVEFORM_PYTHON) scripts/check_doc_anchors.py --check-sync --base origin/main

check-doc-links:
	@$(WAVEFORM_PYTHON) -m waveform_analysis.utils.cli_docs check links --docs-dir docs

check-plugin-deps:
	python scripts/check_plugin_deps.py

test-bundles:
	pytest -q waveform_analysis/core/plugins/builtin

docs-bundles:
	$(WAVEFORM_PYTHON) -m waveform_analysis.utils.cli_docs generate plugins-agent -o docs/plugins/reference/agent/
