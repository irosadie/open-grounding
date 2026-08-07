import { z } from "zod"

export const confidenceLabels = ["SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED", "ABSTAIN"] as const

export type ConfidenceLabel = (typeof confidenceLabels)[number]

export const calibrationSources = ["OPERATOR_LABELED", "SYNTHETIC_BOOTSTRAP"] as const

export type CalibrationSource = (typeof calibrationSources)[number]

export const confidenceLabelOptions = confidenceLabels.map((value) => ({
  label: value.replaceAll("_", " "),
  value,
}))

export const calibrationSourceOptions = calibrationSources.map((value) => ({
  label: value.replaceAll("_", " "),
  value,
}))

export const confidenceConfigSchema = z.object({
  featureWeights: z.record(z.string(), z.number()).nullable(),
  abstentionThreshold: z.number().min(0).max(1),
  emitNumericScore: z.boolean(),
  minLabeledEntries: z.number().int().min(1),
})

export const calibrationFixtureSchema = z.object({
  id: z.string().min(1),
  retrievalProfileId: z.string().min(1),
  version: z.string().min(1),
  source: z.enum(calibrationSources),
  entryCount: z.number().int().nonnegative(),
  isActive: z.boolean(),
  createdAt: z.string(),
})

export const fixtureEntrySchema = z.object({
  id: z.string().min(1),
  fixtureId: z.string().min(1),
  answerRunId: z.string().nullable(),
  query: z.string(),
  answer: z.string(),
  confidenceLabel: z.enum(confidenceLabels),
  createdAt: z.string(),
})

export const unlabeledAnswerRunSchema = z.object({
  answerRunId: z.string().min(1),
  queryPreview: z.string(),
  answerPreview: z.string(),
})

export const calibrationResultSchema = z.object({
  jobId: z.string().min(1),
  status: z.enum(["pending", "running", "complete", "failed"]),
  modelVersionId: z.string().nullable(),
  prCurveSvg: z.string().nullable(),
  f1OptimalThreshold: z.number().min(0).max(1).nullable(),
})

export type ConfidenceConfigInput = z.infer<typeof confidenceConfigSchema>
export type CalibrationFixtureInput = z.infer<typeof calibrationFixtureSchema>
export type FixtureEntryInput = z.infer<typeof fixtureEntrySchema>
export type UnlabeledAnswerRunInput = z.infer<typeof unlabeledAnswerRunSchema>
export type CalibrationResultInput = z.infer<typeof calibrationResultSchema>
