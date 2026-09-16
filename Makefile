.PHONY: setup generate build serve check clean

setup:
	uv sync --frozen

generate:
	uv run python scripts/site.py generate

build:
	uv run python scripts/site.py build

serve:
	uv run python scripts/site.py serve

check:
	uv run ruff check scripts tests
	uv run pytest
	uv run python scripts/site.py check

clean:
	rm -rf build dist
