PYTHON ?= python
RUN_ID ?= developer-check-$(shell date -u +%Y%m%dT%H%M%SZ)

.PHONY: help doctor check check-docs check-gpu
help:
	@echo 'doctor: lightweight target diagnosis'
	@echo 'check: source/shell/CLI contracts (activate R4 first)'
	@echo 'check-gpu: review and P2 CUDA regression; requires explicit CUDA_VISIBLE_DEVICES'

doctor:
	$(PYTHON) scripts/humanmimic.py doctor --target r4-v100

check:
	$(PYTHON) scripts/check-runtime-contracts.py --output runs/$(RUN_ID)/contracts
	$(PYTHON) scripts/check-docs.py --output runs/$(RUN_ID)/docs

check-docs:
	$(PYTHON) scripts/check-docs.py --output runs/$(RUN_ID)/docs

check-gpu:
	$(PYTHON) scripts/check-r4-review-fixes-gpu.py --extended --output runs/$(RUN_ID)/review-gpu
	$(PYTHON) scripts/check-r4-p2-gpu.py --output runs/$(RUN_ID)/p2-gpu
