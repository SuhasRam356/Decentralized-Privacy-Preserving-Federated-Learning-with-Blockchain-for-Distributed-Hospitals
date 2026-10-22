.PHONY: test lint ci clean

test:
	@echo "Running Blockchain Smart Contract Test Suite (ModelUpdateTracker)..."
	cd Blockchain && npm test
	@echo "All unit tests passing."

lint:
	@echo "Validating smart contracts and python pipeline..."
	cd Blockchain && npx hardhat compile

ci: lint test
	@echo "CI pipeline check passed."
