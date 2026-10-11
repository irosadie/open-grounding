import { PARSER_OPTIONS, ingestionConfigSchema } from "@open-grounding/schemas"
import { describe, expect, it } from "vitest"

describe("Ingestion config schema", () => {
  it("defaults to the auto parser", () => {
    const result = ingestionConfigSchema.parse({})

    expect(result.parser).toBe("auto")
    expect(result.doclingServeUrl).toBeNull()
  })

  it("accepts every supported parser option", () => {
    for (const parser of PARSER_OPTIONS) {
      const result = ingestionConfigSchema.safeParse({ parser })

      expect(result.success).toBe(true)
    }
  })

  it("limits a docling-serve URL to the database column size", () => {
    const result = ingestionConfigSchema.safeParse({
      doclingServeUrl: `https://${"a".repeat(2041)}`,
    })

    expect(result.success).toBe(false)
  })
})
