## 1. Protocol Layer

- [x] 1.1 Extend `GenerationAdapter` protocol in `adapter_ports.py` to add optional `messages: list[dict[str, str]] | None = None` parameter to `generate()`

## 2. Infrastructure Layer

- [x] 2.1 Update `LLMGenerationAdapter.generate()` in `generation_adapter.py` to accept `messages` parameter
- [x] 2.2 Update `_call_openai()` to accept and inject `messages` between system prompt and final user message
- [x] 2.3 Update `_call_ollama()` to accept and inject `messages` between system prompt and final user message

## 3. Application Layer

- [x] 3.1 Update `RagQueryService._recent_messages()` to return `list[dict[str, str]]` formatted as `{"role": "user"/"assistant", "content": "..."}`
- [x] 3.2 Capture return value of `_recent_messages()` in `_query_admitted()` and thread it through to `_run_grounded()`
- [x] 3.3 Pass conversation history messages to `RagGenerationService.generate()` in `_run_grounded()`
- [x] 3.4 Update `RagGenerationService.generate()` in `rag_generation.py` to accept and forward `messages` to the adapter

## 4. Tests

- [x] 4.1 Unit test: `GenerationAdapter` protocol compliance — both `prompt`-only and `messages` call styles
- [x] 4.2 Unit test: `LLMGenerationAdapter` correctly formats messages for OpenAI (system + history + final user)
- [x] 4.3 Unit test: `LLMGenerationAdapter` correctly formats messages for Ollama
- [x] 4.4 Unit test: `RagQueryService._recent_messages()` returns correctly formatted role dicts
- [x] 4.5 Unit test: no conversation ID → empty messages → adapter called with prompt only
- [x] 4.6 Unit test: memory chunks and conversation history both present → both injected correctly
