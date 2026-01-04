# Add project-level Makefile commands here
.PHONY: test
test:
	./scripts/run_tests.sh

.PHONY: bench
bench:
	python scripts/benchmark_io.py --n-files 50 --n-channels 2 --n-samples 200 --reps 2
