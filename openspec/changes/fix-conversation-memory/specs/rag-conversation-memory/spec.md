## ADDED Requirements

### Requirement: Completed eligible conversations trigger summarization

When a query completes for a knowledge base with enabled conversation memory, the system
SHALL enqueue a background memory summarization job for that conversation and knowledge
base. The enqueue operation MUST NOT delay or fail the completed query response. The
existing summarizer remains responsible for skipping conversations below the configured
minimum turn count and conversations that were already summarized.

#### Scenario: Enabled memory schedules a completed conversation
- **WHEN** a query completes with a conversation ID and memory is enabled for the selected knowledge base
- **THEN** the system enqueues a `memory.summarize` job containing the tenant, user, knowledge base, and conversation identifiers

#### Scenario: Disabled memory does not schedule a job
- **WHEN** a query completes for a knowledge base whose memory configuration is absent or disabled
- **THEN** the system does not enqueue a `memory.summarize` job for that knowledge base

#### Scenario: Summarization enqueue failure does not fail the query
- **WHEN** the memory job enqueue operation fails after a query has completed
- **THEN** the query response remains successful and the enqueue failure is logged

#### Scenario: Repeated completed turns remain retry-safe
- **WHEN** multiple queries complete within the same conversation before the minimum turn count is reached
- **THEN** each eligible scheduling attempt remains distinct enough for a later attempt to be processed, while the summarizer's duplicate guard prevents more than one memory chunk per conversation

#### Scenario: Summarizer uses provider-compatible defaults
- **WHEN** the configured OpenAI model only accepts its default sampling parameter
- **THEN** the memory summarizer request remains valid and can continue to the embedding and memory-chunk persistence steps

#### Scenario: First memory chunk provisions its vector collection
- **WHEN** a memory summary is ready to persist and the Qdrant `memory` collection does not exist
- **THEN** the system creates the collection using the generated embedding dimension before upserting the memory point
