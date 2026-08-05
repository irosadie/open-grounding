import {
  completeIntakeSchema,
  createIntakeSchema,
  ingestionMimeTypes,
  ragAnswerFeedbackSchema,
  ragQuerySchema,
} from "@open-grounding/schemas"
import { describe, expect, it } from "vitest"

describe("RAG schemas", () => {
  it("validates a supported intake request", () => {
    const result = createIntakeSchema.safeParse({
      knowledgeBaseId: "kb-1",
      filename: "doc.pdf",
      mimeType: "application/pdf",
      sizeBytes: 1024,
    })
    expect(result.success).toBe(true)
  })

  it("rejects an unsupported mime type", () => {
    const result = createIntakeSchema.safeParse({
      knowledgeBaseId: "kb-1",
      filename: "doc.exe",
      mimeType: "application/octet-stream",
      sizeBytes: 1024,
    })
    expect(result.success).toBe(false)
  })

  it("rejects a zero-size file", () => {
    const result = createIntakeSchema.safeParse({
      knowledgeBaseId: "kb-1",
      filename: "doc.pdf",
      mimeType: "application/pdf",
      sizeBytes: 0,
    })
    expect(result.success).toBe(false)
  })

  it("validates a complete intake request", () => {
    const result = completeIntakeSchema.safeParse({
      documentVersionId: "v-1",
      contentChecksum: "abc123",
    })
    expect(result.success).toBe(true)
  })

  it("requires at least one knowledge base for a query", () => {
    const result = ragQuerySchema.safeParse({
      message: "What is the policy?",
      knowledgeBaseIds: [],
    })
    expect(result.success).toBe(false)
  })

  it("accepts a valid query", () => {
    const result = ragQuerySchema.safeParse({
      message: "What is the retention policy?",
      knowledgeBaseIds: ["kb-1"],
    })
    expect(result.success).toBe(true)
  })

  it("rejects a rating outside 1-5", () => {
    const result = ragAnswerFeedbackSchema.safeParse({ rating: 6 })
    expect(result.success).toBe(false)
  })

  it("accepts a valid feedback rating and comment", () => {
    const result = ragAnswerFeedbackSchema.safeParse({
      rating: 5,
      comment: "Great answer",
    })
    expect(result.success).toBe(true)
  })

  it("lists the supported ingestion mime types", () => {
    expect(ingestionMimeTypes).toContain("application/pdf")
    expect(ingestionMimeTypes).toContain("text/markdown")
    expect(ingestionMimeTypes).toContain("text/plain")
  })
})
