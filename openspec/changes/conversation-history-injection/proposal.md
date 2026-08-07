## Why

Conversation history is currently loaded from the database but immediately discarded — return values are never used. This makes every query stateless, forcing users to repeat context and preventing the RAG system from understanding multi-turn conversations. For enterprise users expecting conversational AI, this is a critical gap that undermines the product's core value proposition.

## What Changes

- Extend `GenerationAdapter` protocol to support both legacy `prompt: str` and new `messages: list[dict]` parameters (backward compatible)
- Update `LLMGenerationAdapter` to handle messages array and convert to provider-native chat format (OpenAI/Ollama)
- Modify `RagQueryService._recent_messages` to return conversation history instead of discarding it
- Inject recent messages as proper role-based chat history into generation context
- Format conversation history with explicit role markers (USER/ASSISTANT) for LLM consumption
- Preserve existing memory chunk retrieval (Qdrant-based long-term memory) as supplementary context

## Capabilities

### New Capabilities
- `conversation-history-injection`: Enable multi-turn conversational context by injecting recent messages from the database into LLM generation requests as a properly formatted messages array

### Modified Capabilities
<!-- No existing capabilities are being modified at the spec level — this is net-new functionality -->

## Impact

**Affected code:**
- `apps/api/app/domain/rag/adapter_ports.py` — protocol signature extension
- `apps/api/app/infrastructure/generation_adapter.py` — message array handling
- `apps/api/app/application/rag_query_service.py` — capture and pass conversation history
- `apps/api/app/application/rag_generation.py` — accept and format messages

**Affected systems:**
- OpenAI/Ollama API calls — will receive messages array instead of single prompt string
- Token usage — may increase due to conversation context (tracked via existing budget controls)

**Backward compatibility:**
- Zero breaking changes — existing `prompt` parameter remains functional
- Gradual migration path — services can adopt messages array independently

**Testing surface:**
- Unit tests for protocol compliance (both param styles)
- Integration tests for multi-turn conversation flow
- Token budget validation with conversation context
