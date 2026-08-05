import {
  type documentVersionLifecycleStates,
  getDocumentVersionLifecycleLabel,
  isTerminalLifecycleState,
} from "@vibecoding-starter/schemas"

export type IngestionStageId =
  | "intake"
  | "parse"
  | "embed"
  | "index"
  | "complete"

export type IngestionStage = {
  id: IngestionStageId
  label: string
  description: string
}

export const ingestionStages: IngestionStage[] = [
  {
    id: "intake",
    label: "Upload",
    description: "Source uploaded and validated",
  },
  {
    id: "parse",
    label: "Parse",
    description: "Structure-aware content extraction",
  },
  {
    id: "embed",
    label: "Embed",
    description: "Vector and sparse encoding",
  },
  {
    id: "index",
    label: "Index",
    description: "Vector store indexing",
  },
  {
    id: "complete",
    label: "Ready",
    description: "Available for retrieval",
  },
]

const stageByLifecycleState: Record<string, IngestionStageId> = {
  PENDING: "intake",
  STORED: "parse",
  PARSING: "parse",
  EMBEDDING: "embed",
  INDEXING: "index",
  READY: "complete",
  FAILED: "complete",
  DELETING: "intake",
}

export const getIngestionStage = (lifecycleState: string): IngestionStageId => {
  return stageByLifecycleState[lifecycleState] ?? "intake"
}

export const getCurrentStageIndex = (lifecycleState: string): number => {
  const stageId = getIngestionStage(lifecycleState)
  return ingestionStages.findIndex((stage) => stage.id === stageId)
}

export const getIngestionStageLabel = (lifecycleState: string): string => {
  return getDocumentVersionLifecycleLabel(
    lifecycleState as (typeof documentVersionLifecycleStates)[number],
  )
}

export const isIngestionTerminal = (lifecycleState: string): boolean => {
  return isTerminalLifecycleState(lifecycleState)
}
