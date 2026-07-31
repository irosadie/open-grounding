# Checklist: API Bugfix

## Preparation

- [ ] Read `.agents/settings.json`
- [ ] Read `references/context.md`
- [ ] Write down the bug symptom or failing behavior

## Execution

- [ ] Root cause localized to the smallest layer
- [ ] Changes remain minimal touch
- [ ] Pydantic schema/DTO/OpenAPI updated when affected
- [ ] No unrelated refactor
- [ ] Reproduction or guard test added/updated

## Finalization

- [ ] Backend contract stays in sync
- [ ] `uv run python -m app.export_openapi` run if contract changed
- [ ] `uv run ruff check app tests` passes
- [ ] `uv run mypy app` passes
- [ ] `uv run pytest` passes
- [ ] No unrelated changes carried along
- [ ] All files end with a newline (EOF)
