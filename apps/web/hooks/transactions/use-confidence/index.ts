"use client"

import { apiRouters, queryKeys } from "$/constants"
import { axios } from "$/services/axios"
import type { ErrorResponse } from "$/types/generals"
import { pathVariable } from "$/utils/path-variable"
import type { ConfidenceConfigInput } from "@open-grounding/schemas"
import type {
  CalibrationFixtureResponse,
  CalibrationResultResponse,
  ConfidenceConfigResponse,
  FixtureEntryResponse,
  ThresholdEvalResponse,
  UnlabeledAnswerRunResponse,
} from "@open-grounding/types"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { AxiosError } from "axios"

export const useConfidenceConfig = (profileId: string | null) =>
  useQuery<ConfidenceConfigResponse, ErrorResponse<AxiosError>>({
    queryKey: [queryKeys.rag.confidence.config, profileId],
    queryFn: () =>
      axios<ConfidenceConfigResponse>({
        method: "GET",
        url: pathVariable(apiRouters.rag.confidence.config, {
          profileId: profileId as string,
        }),
      }),
    enabled: Boolean(profileId),
  })

export const useUpdateConfidenceConfig = (profileId: string) => {
  const queryClient = useQueryClient()
  return useMutation<
    ConfidenceConfigResponse,
    ErrorResponse<AxiosError>,
    ConfidenceConfigInput
  >({
    mutationKey: [queryKeys.rag.confidence.config, profileId],
    mutationFn: (data) =>
      axios<ConfidenceConfigResponse>({
        method: "PATCH",
        url: pathVariable(apiRouters.rag.confidence.config, { profileId }),
        data: {
          feature_weights: data.featureWeights,
          abstention_threshold: data.abstentionThreshold,
          emit_numeric_score: data.emitNumericScore,
          min_labeled_entries: data.minLabeledEntries,
        },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.confidence.config, profileId],
      })
    },
  })
}

export const useCalibrationFixtures = (profileId: string | null) =>
  useQuery<CalibrationFixtureResponse[], ErrorResponse<AxiosError>>({
    queryKey: [queryKeys.rag.confidence.fixtures, profileId],
    queryFn: () =>
      axios<CalibrationFixtureResponse[]>({
        method: "GET",
        url: apiRouters.rag.confidence.fixtures,
        params: { profile_id: profileId },
      }),
    enabled: Boolean(profileId),
  })

export const useImportFixture = (profileId: string) => {
  const queryClient = useQueryClient()
  return useMutation<
    { fixtureId: string; importedEntries: number },
    ErrorResponse<AxiosError>,
    { file: File; version: string }
  >({
    mutationFn: ({ file, version }) => {
      const form = new FormData()
      form.append("file", file)
      return axios<{ fixtureId: string; importedEntries: number }>({
        method: "POST",
        url: apiRouters.rag.confidence.import,
        params: { profile_id: profileId, version },
        data: form,
        headers: { "Content-Type": "multipart/form-data" },
      })
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.confidence.fixtures, profileId],
      })
    },
  })
}

export const useGenerateSynthetic = (profileId: string) => {
  const queryClient = useQueryClient()
  return useMutation<
    { jobId: string },
    ErrorResponse<AxiosError>,
    { knowledgeBaseId: string; count: number }
  >({
    mutationFn: ({ knowledgeBaseId, count }) =>
      axios<{ jobId: string }>({
        method: "POST",
        url: apiRouters.rag.confidence.generateSynthetic,
        params: { profile_id: profileId },
        data: { knowledge_base_id: knowledgeBaseId, count },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.confidence.fixtures, profileId],
      })
    },
  })
}

export const useFixtureEntries = (fixtureId: string | null, page = 1) =>
  useQuery<
    { items: FixtureEntryResponse[]; page: number; pageSize: number },
    ErrorResponse<AxiosError>
  >({
    queryKey: [queryKeys.rag.confidence.entries, fixtureId, page],
    queryFn: () =>
      axios<{ items: FixtureEntryResponse[]; page: number; pageSize: number }>({
        method: "GET",
        url: pathVariable(apiRouters.rag.confidence.entries, {
          fixtureId: fixtureId as string,
        }),
        params: { page, page_size: 50 },
      }),
    enabled: Boolean(fixtureId),
  })

export const useUnlabeledRuns = (profileId: string | null, page = 1) =>
  useQuery<
    { items: UnlabeledAnswerRunResponse[]; page: number; pageSize: number },
    ErrorResponse<AxiosError>
  >({
    queryKey: [queryKeys.rag.confidence.unlabeled, profileId, page],
    queryFn: () =>
      axios<{
        items: UnlabeledAnswerRunResponse[]
        page: number
        pageSize: number
      }>({
        method: "GET",
        url: apiRouters.rag.confidence.unlabeled,
        params: { profile_id: profileId, page, page_size: 50 },
      }),
    enabled: Boolean(profileId),
  })

export const useLabelRun = (fixtureId: string) => {
  const queryClient = useQueryClient()
  return useMutation<
    { labeled: number },
    ErrorResponse<AxiosError>,
    { answerRunId: string; label: string }
  >({
    mutationFn: ({ answerRunId, label }) =>
      axios<{ labeled: number }>({
        method: "POST",
        url: pathVariable(apiRouters.rag.confidence.label, { fixtureId }),
        data: { answer_run_id: answerRunId, label },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.confidence.unlabeled],
      })
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.confidence.entries, fixtureId],
      })
    },
  })
}

export const useBulkLabelRuns = (fixtureId: string) => {
  const queryClient = useQueryClient()
  return useMutation<
    { labeled: number },
    ErrorResponse<AxiosError>,
    { labels: Record<string, string> }
  >({
    mutationFn: ({ labels }) =>
      axios<{ labeled: number }>({
        method: "POST",
        url: pathVariable(apiRouters.rag.confidence.labelBulk, { fixtureId }),
        data: { labels },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.confidence.unlabeled],
      })
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.confidence.entries, fixtureId],
      })
    },
  })
}

export const useRunCalibration = (profileId: string) => {
  const queryClient = useQueryClient()
  return useMutation<
    { jobId: string },
    ErrorResponse<AxiosError>,
    { fixtureId: string }
  >({
    mutationFn: ({ fixtureId }) =>
      axios<{ jobId: string }>({
        method: "POST",
        url: pathVariable(apiRouters.rag.confidence.calibrate, { profileId }),
        data: { fixture_id: fixtureId },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.confidence.calibrateStatus],
      })
    },
  })
}

export const useCalibrationStatus = (jobId: string | null) =>
  useQuery<CalibrationResultResponse, ErrorResponse<AxiosError>>({
    queryKey: [queryKeys.rag.confidence.calibrateStatus, jobId],
    queryFn: () =>
      axios<CalibrationResultResponse>({
        method: "GET",
        url: pathVariable(apiRouters.rag.confidence.calibrateStatus, {
          jobId: jobId as string,
        }),
      }),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === "pending" || status === "running" ? 2000 : false
    },
  })

export const useThresholdEval = (
  modelVersionId: string | null,
  threshold: number | null,
) =>
  useQuery<ThresholdEvalResponse, ErrorResponse<AxiosError>>({
    queryKey: [queryKeys.rag.confidence.models, modelVersionId, threshold],
    queryFn: () =>
      axios<ThresholdEvalResponse>({
        method: "GET",
        url: pathVariable(apiRouters.rag.confidence.threshold, {
          modelVersionId: modelVersionId as string,
        }),
        params: { threshold },
      }),
    enabled: Boolean(modelVersionId) && threshold !== null,
  })

export const usePromoteModel = (modelVersionId: string) => {
  const queryClient = useQueryClient()
  return useMutation<
    object,
    ErrorResponse<AxiosError>,
    { promotedBy?: string }
  >({
    mutationFn: ({ promotedBy }) =>
      axios<object>({
        method: "POST",
        url: pathVariable(apiRouters.rag.confidence.promote, {
          modelVersionId,
        }),
        data: { promoted_by: promotedBy },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.confidence.config],
      })
      void queryClient.invalidateQueries({
        queryKey: [queryKeys.rag.confidence.models],
      })
    },
  })
}
