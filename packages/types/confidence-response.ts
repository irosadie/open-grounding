import type {
  CalibrationResultInput,
  CalibrationFixtureInput,
  ConfidenceConfigInput,
  FixtureEntryInput,
  UnlabeledAnswerRunInput,
} from "@open-grounding/schemas"

export type ConfidenceConfigResponse = ConfidenceConfigInput & {
  retrievalProfileId: string
  activeModelId: string | null
  updatedAt: string | null
  warning?: string | null
}

export type CalibrationFixtureResponse = CalibrationFixtureInput
export type FixtureEntryResponse = FixtureEntryInput
export type UnlabeledAnswerRunResponse = UnlabeledAnswerRunInput
export type CalibrationResultResponse = CalibrationResultInput

export type ThresholdEvalResponse = {
  threshold: number
  precision: number
  recall: number
  f1: number
}
