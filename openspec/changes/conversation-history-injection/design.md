## Context

The RAG query service currently loads recent conversation messages from the database (`_recent_messages`) but immediately discards the return value. This was likely implemented as a placeholder for future work. As a result, every query is stateless — the LLM has no awareness of prior turns in the conversation.

**Current state:**
- `ConversationHistoryRepository.recent_messages()` retrieves messages from `rag_conversation_messages` table
- Messages have `speaker` (USER/ASSISTANT) and `content` fields
- `RagQueryService._recent_messages()` is called but return value ignored
- `LLMGenerationAdapter` sends a single prompt string to OpenAI/Ollama
- Memory chunks (Qdrant-based) are already injected as supplementary context

**Constraints:**
- Must remain backward compatible — existing callers using `prompt` only must not break
- Token budget is already controlled by `rag_query_recent_messages` setting
- Both OpenAI and Ollama must work identically
- Memory chunks and conversation history must coexist without conflict

## Goals / Non-Goals

**Goals:**
- Enable multi-turn conversational context by injecting recent messages into generation
- Use industry-standard messages array format for better LLM reasoning
- Maintain backward compatibility — no breaking changes to existing code
- Preserve existing memory chunk retrieval (Qdrant long-term memory)

**Non-Goals:**
- Changing token budget logic or conversation storage mechanism
- Adding new conversation management features (that's separate work)
- Modifying how memory chunks are retrieved or formatted
- Supporting providers beyond OpenAI/Ollama in this change

## Decisions

### Decision 1: Extend protocol with optional `messages` parameter

**Choice:** Add `messages: list[dict[str, str]] | None = None` to `GenerationAdapter.generate()` signature.

**Rationale:**
- Backward compatible — existing calls with `prompt` continue working
- Allows gradual migration — services adopt messages independently
- Mirrors OpenAI/Anthropic/Ollama native API format
- Clear contract: `messages` takes precedence if both provided

**Alternatives considered:**
- **Create a new method** (`generate_with_history()`): Rejected — creates API bloat and splits the interface
- **Always require messages array**: Rejected — breaks all existing callers
- **Keep prompt-only and serialize messages to string**: Rejected — loses role information and LLM performance degrades

### Decision 2: Inject history as messages array, not prompt string

**Choice:** Pass conversation history as structured `[{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]` instead of serializing to text.

**Rationale:**
- LLMs are trained on role-based formats — better reasoning and context awareness
- Token-efficient — providers optimize for native message structure
- Preserves turn boundaries — LLM knows when user vs assistant is speaking
- Industry standard across all major LLM APIs

**Alternatives considered:**
- **Serialize to "CONVERSATION HISTORY:\nUSER: ...\nASSISTANT: ..."**: Rejected — wastes tokens, loses semantic structure
- **Inject as supplementary context**: Rejected — supplementary is for non-citable external knowledge, not conversation turns

### Decision 3: Messages inserted between system and final user prompt

**Choice:** Message order: `[system_prompt, ...conversation_history, {role: "user", content: grounded_prompt}]`

**Rationale:**
- System prompt establishes the rules (grounded generation, structured output)
- History provides conversational context
- Final user message contains the current question + evidence context
- This ordering matches how conversational RAG systems work in production

**Alternatives considered:**
- **Append history after grounded prompt**: Rejected — evidence context should be closest to the question
- **System prompt after history**: Rejected — system instructions must come first to set behavior

### Decision 4: Keep memory chunks as supplementary, not in messages

**Choice:** Long-term memory (Qdrant chunks) stay in `supplementary` parameter; short-term history goes in `messages`.

**Rationale:**
- Memory chunks are summarized knowledge, not exact conversation turns — shouldn't be cited as chat history
- Supplementary context already works and is labeled as non-citable
- Avoids confusion between "what the user said" (messages) vs "what we know about them" (memory)

**Alternatives considered:**
- **Merge memory into messages as system messages**: Rejected — memory chunks are not system instructions
- **Drop memory when history exists**: Rejected — both provide value and should coexist

### Decision 5: Conversion in adapter layer, not service layer

**Choice:** `LLMGenerationAdapter` handles conversion of `messages` list to provider-native format.

**Rationale:**
- Adapter layer owns provider-specific details (OpenAI vs Ollama format differences)
- Service layer remains provider-agnostic — just passes structured data
- Easier to add new providers — conversion logic is isolated

**Alternatives considered:**
- **Pre-format in RagQueryService**: Rejected — leaks provider details into application layer
- **Pass raw messages to provider SDK**: Rejected — need to inject system prompt and grounded prompt consistently

## Risks / Trade-offs

**[Risk]** Token usage increases with conversation history  
→ **Mitigation:** Already bounded by `rag_query_recent_messages` config (default is reasonable); existing token budget controls apply

**[Risk]** Backward compatibility not preserved if callers depend on internal behavior  
→ **Mitigation:** Only extending protocol, not changing existing behavior; `prompt`-only path unchanged; gradual rollout possible

**[Risk]** Message formatting differences between OpenAI/Ollama cause inconsistent behavior  
→ **Mitigation:** Both providers use identical message format; integration tests will catch discrepancies

**[Trade-off]** Messages array slightly more complex than plain text  
→ **Benefit:** Significantly better LLM reasoning and context handling; industry standard approach

**[Risk]** Conversation history may reference outdated information if memory chunks conflict  
→ **Mitigation:** Not introduced by this change — existing issue with memory vs current evidence; separate concern for future work

## Migration Plan

**Deployment steps:**
1. Extend `GenerationAdapter` protocol with optional `messages` parameter
2. Update `LLMGenerationAdapter` to handle both `prompt` and `messages`
3. Modify `RagQueryService._recent_messages` to return messages and inject them
4. Run integration tests with conversation ID provided vs not provided
5. Deploy to staging and validate multi-turn conversations
6. Deploy to production (zero downtime — backward compatible)

**Rollback strategy:**
- If issues arise, revert `RagQueryService` to ignore `_recent_messages` return value
- Adapter changes are harmless (unused code path if service doesn't pass messages)
- No database migrations required — conversation storage already exists

**Validation:**
- Unit tests: protocol compliance, both parameter styles
- Integration tests: multi-turn conversation flow with real DB
- Manual QA: verify follow-up questions reference prior context

## Open Questions

None — design is ready for implementation.
