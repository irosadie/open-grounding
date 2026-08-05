"use client"

import { apiRouters, queryKeys } from "$/constants"
import { axios } from "$/services/axios"
import type { ErrorResponse } from "$/types/generals"
import { pathVariable } from "$/utils/path-variable"
import { useMutation } from "@tanstack/react-query"
import {
  type RagAnswerFeedbackProps,
  ragAnswerFeedbackSchema,
} from "@vibecoding-starter/schemas"
import type { RagAnswerFeedbackResponse } from "@vibecoding-starter/types"
import type { AxiosError } from "axios"

const submitFeedback = async (args: {
  traceId: string
  payload: RagAnswerFeedbackProps
}) => {
  const validated = ragAnswerFeedbackSchema.parse(args.payload)
  const result = await axios<RagAnswerFeedbackResponse>({
    method: "POST",
    url: pathVariable(apiRouters.rag.query.feedback, { traceId: args.traceId }),
    data: validated,
  })
  return result
}

type UseRagFeedbackArgs = {
  traceId: string
}

export const useRagFeedback = (args: UseRagFeedbackArgs) => {
  const { traceId } = args
  const mutation = useMutation<
    RagAnswerFeedbackResponse,
    ErrorResponse<AxiosError>,
    RagAnswerFeedbackProps,
    unknown
  >({
    mutationKey: [queryKeys.rag.query.feedback, traceId],
    mutationFn: (payload) => submitFeedback({ traceId, payload }),
  })

  return {
    ...mutation,
  }
}

export default useRagFeedback
