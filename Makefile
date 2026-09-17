.PHONY: setup generate build serve check check-source clean

SOURCE_REPOSITORY ?= .
SOURCE_FLAGS ?=

setup:
	uv sync --frozen

generate:
	uv run python -m scripts.site generate

build:
	uv run python -m scripts.site build

serve:
	uv run python -m scripts.site serve

check:
	uv run ruff check scripts tests
	uv run pytest
	uv run python -m scripts.site check

check-source:
	uv run python -m scripts.check_source_docs "$(SOURCE_REPOSITORY)" $(SOURCE_FLAGS)

clean:
	rm -rf build dist
