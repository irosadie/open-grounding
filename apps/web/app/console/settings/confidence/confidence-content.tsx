"use client"

import { Button } from "$/components/button"
import { Input } from "$/components/input"
import { PanelCard } from "$/components/panel-card"
import {
  useBulkLabelRuns,
  useCalibrationFixtures,
  useCalibrationStatus,
  useConfidenceConfig,
  useGenerateSynthetic,
  useImportFixture,
  useLabelRun,
  usePromoteModel,
  useRunCalibration,
  useThresholdEval,
  useUnlabeledRuns,
  useUpdateConfidenceConfig,
} from "$/hooks/transactions/use-confidence"
import { useIndexProfiles } from "$/hooks/transactions/use-index-profiles"
import { useKnowledgeBases } from "$/hooks/transactions/use-knowledge-bases"
import {
  confidenceConfigSchema,
  confidenceLabels,
} from "@open-grounding/schemas"
import { type ChangeEvent, useEffect, useState } from "react"

const defaultForm = {
  featureWeights: null as Record<string, number> | null,
  abstentionThreshold: 0.35,
  emitNumericScore: false,
  minLabeledEntries: 200,
}

export default function ConfidenceContent() {
  const { data: profiles } = useIndexProfiles()
  const { data: knowledgeBases } = useKnowledgeBases()
  const [profileId, setProfileId] = useState<string | null>(null)
  const configQuery = useConfidenceConfig(profileId)
  const fixturesQuery = useCalibrationFixtures(profileId)
  const updateConfig = useUpdateConfidenceConfig(profileId ?? "")

  const [form, setForm] = useState(defaultForm)
  const [weightsText, setWeightsText] = useState("")
  const [configError, setConfigError] = useState("")
  const [showWorkbench, setShowWorkbench] = useState(false)
  const [workbenchFixtureId, setWorkbenchFixtureId] = useState<string | null>(
    null,
  )
  const [workbenchPage, setWorkbenchPage] = useState(1)
  const [pendingLabels, setPendingLabels] = useState<Record<string, string>>({})

  // Dataset management state
  const [importVersion, setImportVersion] = useState("1.0.0")
  const [importFile, setImportFile] = useState<File | null>(null)
  const [syntheticKbId, setSyntheticKbId] = useState<string>("")
  const [syntheticCount, setSyntheticCount] = useState(50)
  const importFixture = useImportFixture(profileId ?? "")
  const generateSynthetic = useGenerateSynthetic(profileId ?? "")

  // Calibration state
  const [calibrationJobId, setCalibrationJobId] = useState<string | null>(null)
  const [thresholdInput, setThresholdInput] = useState<number | null>(null)
  const [promotingModelId, setPromotingModelId] = useState<string | null>(null)
  const [showPromoteConfirm, setShowPromoteConfirm] = useState(false)

  const unlabeledQuery = useUnlabeledRuns(
    showWorkbench ? profileId : null,
    workbenchPage,
  )
  const labelRun = useLabelRun(workbenchFixtureId ?? "")
  const bulkLabelRuns = useBulkLabelRuns(workbenchFixtureId ?? "")
  const runCalibration = useRunCalibration(profileId ?? "")
  const calibrationStatus = useCalibrationStatus(calibrationJobId)
  const thresholdEval = useThresholdEval(
    calibrationStatus.data?.modelVersionId ?? null,
    thresholdInput,
  )
  const promoteModel = usePromoteModel(promotingModelId ?? "")

  useEffect(() => {
    if (!profileId && profiles?.[0]) setProfileId(profiles[0].id)
  }, [profileId, profiles])

  useEffect(() => {
    if (!syntheticKbId && knowledgeBases?.[0])
      setSyntheticKbId(knowledgeBases[0].id)
  }, [syntheticKbId, knowledgeBases])

  useEffect(() => {
    if (!configQuery.data) return
    setForm({
      featureWeights: configQuery.data.featureWeights,
      abstentionThreshold: configQuery.data.abstentionThreshold,
      emitNumericScore: configQuery.data.emitNumericScore,
      minLabeledEntries: configQuery.data.minLabeledEntries,
    })
    setWeightsText(
      configQuery.data.featureWeights
        ? JSON.stringify(configQuery.data.featureWeights, null, 2)
        : "",
    )
  }, [configQuery.data])

  useEffect(() => {
    if (calibrationStatus.data?.f1OptimalThreshold != null) {
      setThresholdInput(calibrationStatus.data.f1OptimalThreshold)
    }
    if (calibrationStatus.data?.modelVersionId) {
      setPromotingModelId(calibrationStatus.data.modelVersionId)
    }
  }, [calibrationStatus.data])

  const saveConfig = async () => {
    let featureWeights: Record<string, number> | null = null
    try {
      featureWeights = weightsText.trim()
        ? (JSON.parse(weightsText) as Record<string, number>)
        : null
    } catch {
      setConfigError("Feature weights must be valid JSON.")
      return
    }
    const parsed = confidenceConfigSchema.safeParse({ ...form, featureWeights })
    if (!parsed.success) {
      setConfigError(
        parsed.error.issues[0]?.message ?? "Invalid confidence settings.",
      )
      return
    }
    setConfigError("")
    await updateConfig.mutateAsync(parsed.data)
  }

  const activeModel = configQuery.data?.activeModelId
  const fixtures = fixturesQuery.data ?? []
  const activeFixture = fixtures.find((f) => f.isActive)
  const minLabeled = configQuery.data?.minLabeledEntries ?? 200
  const labeledCount = activeFixture?.entryCount ?? 0
  const canCalibrate = labeledCount >= minLabeled

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Confidence</h1>
        <p className="mt-1 text-sm text-gray-500">
          Configure numeric confidence calibration for each index profile.
        </p>
      </div>

      {/* ── Calibration Status ─────────────────────────────────────── */}
      <PanelCard title="Calibration Status">
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="confidence-profile"
              className="text-sm font-medium text-main-700"
            >
              Index Profile
            </label>
            <select
              id="confidence-profile"
              value={profileId ?? ""}
              onChange={(e) => setProfileId(e.target.value || null)}
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900"
            >
              <option value="">Select an index profile...</option>
              {profiles?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          {profileId ? (
            <>
              <p className="text-sm text-gray-500">
                Active model:{" "}
                <span className="font-mono text-xs">
                  {activeModel ?? "No promoted model"}
                </span>
              </p>
              <p className="text-sm text-gray-500">
                Labeled entries: {labeledCount} / {minLabeled}
              </p>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Input
                  label="Abstention Threshold"
                  type="number"
                  min="0"
                  max="1"
                  step="0.01"
                  value={form.abstentionThreshold.toString()}
                  onChange={(e: ChangeEvent<HTMLInputElement>) =>
                    setForm((c) => ({
                      ...c,
                      abstentionThreshold: Number(e.target.value),
                    }))
                  }
                />
                <Input
                  label="Minimum Labeled Entries"
                  type="number"
                  min="1"
                  value={form.minLabeledEntries.toString()}
                  onChange={(e: ChangeEvent<HTMLInputElement>) =>
                    setForm((c) => ({
                      ...c,
                      minLabeledEntries: Number(e.target.value),
                    }))
                  }
                />
              </div>

              <label
                title={
                  activeModel
                    ? undefined
                    : "A promoted calibration model is required."
                }
                className="flex items-center gap-2 text-sm font-medium text-main-700"
              >
                <input
                  type="checkbox"
                  checked={form.emitNumericScore}
                  disabled={!activeModel}
                  onChange={(e) =>
                    setForm((c) => ({
                      ...c,
                      emitNumericScore: e.target.checked,
                    }))
                  }
                />
                Emit numeric confidence score
                {!activeModel && (
                  <span className="ml-1 text-xs text-gray-400">
                    (requires promoted model)
                  </span>
                )}
              </label>

              <label className="flex flex-col gap-1.5 text-sm font-medium text-main-700">
                Feature Weights JSON
                <textarea
                  value={weightsText}
                  onChange={(e) => setWeightsText(e.target.value)}
                  placeholder='{"reranker_score_mean": 1}'
                  className="min-h-24 rounded-lg border border-gray-300 px-3 py-2 font-mono text-xs"
                />
              </label>

              {configError ? (
                <p className="text-sm text-danger-500">{configError}</p>
              ) : null}
              {configQuery.data?.warning ? (
                <p className="text-sm text-warning-600">
                  {configQuery.data.warning}
                </p>
              ) : null}

              <Button
                intent="primary"
                onClick={saveConfig}
                loading={updateConfig.isPending}
              >
                Save
              </Button>
            </>
          ) : (
            <p className="text-sm text-gray-500">
              Select an index profile to configure confidence.
            </p>
          )}
        </div>
      </PanelCard>

      {/* ── Dataset Management ─────────────────────────────────────── */}
      <PanelCard
        title="Dataset Management"
        description="Calibration fixtures available for the selected profile."
      >
        {fixturesQuery.isLoading ? (
          <p className="text-sm text-gray-500">Loading...</p>
        ) : fixtures.length === 0 ? (
          <p className="text-sm text-gray-500">No calibration fixtures yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-gray-500">
                <tr>
                  <th className="pb-2">Version</th>
                  <th className="pb-2">Source</th>
                  <th className="pb-2">Entries</th>
                  <th className="pb-2">Status</th>
                  <th className="pb-2" />
                </tr>
              </thead>
              <tbody>
                {fixtures.map((fixture) => (
                  <tr key={fixture.id} className="border-t border-gray-100">
                    <td className="py-2">{fixture.version}</td>
                    <td className="py-2">
                      <span
                        className={
                          fixture.source === "OPERATOR_LABELED"
                            ? "rounded bg-success-100 px-2 py-0.5 text-xs text-success-700"
                            : "rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600"
                        }
                      >
                        {fixture.source.replaceAll("_", " ")}
                      </span>
                    </td>
                    <td className="py-2">{fixture.entryCount}</td>
                    <td className="py-2">
                      {fixture.isActive ? (
                        <span className="rounded bg-success-100 px-2 py-0.5 text-xs text-success-700">
                          Active
                        </span>
                      ) : (
                        <span className="text-xs text-gray-400">Inactive</span>
                      )}
                    </td>
                    <td className="py-2">
                      <button
                        type="button"
                        className="text-xs text-main-600 underline"
                        onClick={() => {
                          setWorkbenchFixtureId(fixture.id)
                          setShowWorkbench(true)
                        }}
                      >
                        View Entries
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {profileId ? (
          <div className="mt-4 flex flex-col gap-4 border-t border-gray-100 pt-4">
            {/* CSV import */}
            <div className="flex flex-col gap-2">
              <p className="text-sm font-medium text-gray-700">Upload CSV</p>
              <div className="flex flex-wrap items-center gap-2">
                <Input
                  label="Version"
                  value={importVersion}
                  onChange={(e: ChangeEvent<HTMLInputElement>) =>
                    setImportVersion(e.target.value)
                  }
                />
                <div className="flex flex-col gap-1">
                  <label
                    htmlFor="csv-file-input"
                    className="text-xs text-gray-500"
                  >
                    CSV File
                  </label>
                  <input
                    id="csv-file-input"
                    type="file"
                    accept=".csv,text/csv"
                    onChange={(e) => setImportFile(e.target.files?.[0] ?? null)}
                    className="text-sm"
                  />
                </div>
                <Button
                  intent="secondary"
                  bordered
                  loading={importFixture.isPending}
                  disabled={!importFile}
                  onClick={() => {
                    if (importFile) {
                      importFixture.mutate({
                        file: importFile,
                        version: importVersion,
                      })
                    }
                  }}
                >
                  Import
                </Button>
              </div>
              {importFixture.isSuccess && (
                <p className="text-xs text-success-600">
                  Imported {importFixture.data.importedEntries} entries.
                </p>
              )}
            </div>

            {/* Generate synthetic */}
            <div className="flex flex-col gap-2">
              <p className="text-sm font-medium text-gray-700">
                Generate Synthetic
              </p>
              <div className="flex flex-wrap items-center gap-2">
                <div className="flex flex-col gap-1">
                  <label
                    htmlFor="synthetic-kb"
                    className="text-xs text-gray-500"
                  >
                    Knowledge Base
                  </label>
                  <select
                    id="synthetic-kb"
                    value={syntheticKbId}
                    onChange={(e) => setSyntheticKbId(e.target.value)}
                    className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm"
                  >
                    <option value="">Select...</option>
                    {knowledgeBases?.map((kb) => (
                      <option key={kb.id} value={kb.id}>
                        {kb.name}
                      </option>
                    ))}
                  </select>
                </div>
                <Input
                  label="Count"
                  type="number"
                  min="1"
                  max="500"
                  value={syntheticCount.toString()}
                  onChange={(e: ChangeEvent<HTMLInputElement>) =>
                    setSyntheticCount(Number(e.target.value))
                  }
                />
                <Button
                  intent="secondary"
                  bordered
                  loading={generateSynthetic.isPending}
                  disabled={!syntheticKbId}
                  onClick={() => {
                    if (syntheticKbId) {
                      generateSynthetic.mutate({
                        knowledgeBaseId: syntheticKbId,
                        count: syntheticCount,
                      })
                    }
                  }}
                >
                  Generate
                </Button>
              </div>
            </div>
          </div>
        ) : null}
      </PanelCard>

      {/* ── Labeling Workbench ─────────────────────────────────────── */}
      <PanelCard
        title="Labeling Workbench"
        description="Label answer runs without leaving this page."
      >
        <div className="flex items-center gap-2">
          <Button
            intent="secondary"
            bordered
            onClick={() => setShowWorkbench((v) => !v)}
          >
            {showWorkbench ? "Hide Workbench" : "Show Workbench"}
          </Button>
          {activeFixture && (
            <span className="text-xs text-gray-500">
              Active fixture: {activeFixture.version}
            </span>
          )}
        </div>

        {showWorkbench && (
          <div className="mt-4 flex flex-col gap-4">
            {/* Progress */}
            <div className="flex flex-col gap-1">
              <div className="flex justify-between text-xs text-gray-500">
                <span>
                  {labeledCount} / {minLabeled} labeled
                </span>
                <span>
                  {Math.min(100, Math.round((labeledCount / minLabeled) * 100))}
                  %
                </span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-gray-200">
                <div
                  className="h-2 rounded-full bg-main-500 transition-all"
                  style={{
                    width: `${Math.min(100, (labeledCount / minLabeled) * 100)}%`,
                  }}
                />
              </div>
            </div>

            {unlabeledQuery.isLoading ? (
              <p className="text-sm text-gray-500">Loading...</p>
            ) : (unlabeledQuery.data?.items.length ?? 0) === 0 ? (
              <p className="text-sm text-gray-500">
                No unlabeled answer runs found.
              </p>
            ) : (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="text-xs text-gray-500">
                      <tr>
                        <th className="pb-2 pr-4">Query</th>
                        <th className="pb-2 pr-4">Answer</th>
                        <th className="pb-2">Label</th>
                        <th className="pb-2" />
                      </tr>
                    </thead>
                    <tbody>
                      {unlabeledQuery.data?.items.map((run) => (
                        <tr
                          key={run.answerRunId}
                          className="border-t border-gray-100"
                        >
                          <td className="py-2 pr-4 max-w-xs truncate text-xs text-gray-700">
                            {run.queryPreview}
                          </td>
                          <td className="py-2 pr-4 max-w-xs truncate text-xs text-gray-500">
                            {run.answerPreview}
                          </td>
                          <td className="py-2">
                            <select
                              aria-label={`Label for run ${run.answerRunId}`}
                              value={pendingLabels[run.answerRunId] ?? ""}
                              onChange={(e) =>
                                setPendingLabels((prev) => ({
                                  ...prev,
                                  [run.answerRunId]: e.target.value,
                                }))
                              }
                              className="rounded border border-gray-300 px-2 py-1 text-xs"
                            >
                              <option value="">Select...</option>
                              {confidenceLabels.map((lbl) => (
                                <option key={lbl} value={lbl}>
                                  {lbl.replaceAll("_", " ")}
                                </option>
                              ))}
                            </select>
                          </td>
                          <td className="py-2">
                            <button
                              type="button"
                              disabled={
                                !pendingLabels[run.answerRunId] ||
                                !workbenchFixtureId
                              }
                              onClick={() => {
                                const label = pendingLabels[run.answerRunId]
                                if (label && workbenchFixtureId) {
                                  labelRun.mutate({
                                    answerRunId: run.answerRunId,
                                    label,
                                  })
                                }
                              }}
                              className="text-xs text-main-600 underline disabled:opacity-40"
                            >
                              Save
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="flex items-center justify-between">
                  <div className="flex gap-2">
                    <Button
                      intent="secondary"
                      bordered
                      disabled={workbenchPage <= 1}
                      onClick={() => setWorkbenchPage((p) => p - 1)}
                    >
                      Prev
                    </Button>
                    <Button
                      intent="secondary"
                      bordered
                      onClick={() => setWorkbenchPage((p) => p + 1)}
                    >
                      Next
                    </Button>
                  </div>
                  <Button
                    intent="primary"
                    loading={bulkLabelRuns.isPending}
                    disabled={
                      !workbenchFixtureId ||
                      Object.keys(pendingLabels).length === 0
                    }
                    onClick={() => {
                      if (workbenchFixtureId) {
                        bulkLabelRuns.mutate(
                          { labels: pendingLabels },
                          { onSuccess: () => setPendingLabels({}) },
                        )
                      }
                    }}
                  >
                    Save All
                  </Button>
                </div>
              </>
            )}
          </div>
        )}
      </PanelCard>

      {/* ── Calibration & Threshold ────────────────────────────────── */}
      <PanelCard
        title="Calibration & Threshold"
        description="Run and review calibration after sufficient operator labels are available."
      >
        <div className="flex flex-col gap-4">
          {/* Run Calibration */}
          <div className="flex flex-wrap items-center gap-2">
            <Button
              intent="primary"
              loading={runCalibration.isPending}
              disabled={!canCalibrate || !activeFixture}
              title={
                !canCalibrate
                  ? `Requires ${minLabeled} labeled entries (currently ${labeledCount})`
                  : undefined
              }
              onClick={() => {
                if (activeFixture) {
                  runCalibration.mutate(
                    { fixtureId: activeFixture.id },
                    { onSuccess: (data) => setCalibrationJobId(data.jobId) },
                  )
                }
              }}
            >
              Run Calibration
            </Button>
            {!canCalibrate && (
              <p className="text-xs text-gray-500">
                {minLabeled - labeledCount} more labeled entries needed.
              </p>
            )}
          </div>

          {/* Status indicator */}
          {calibrationJobId && (
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-700">Status:</span>
              <span
                className={
                  calibrationStatus.data?.status === "complete"
                    ? "text-sm text-success-600"
                    : calibrationStatus.data?.status === "failed"
                      ? "text-sm text-danger-500"
                      : "text-sm text-gray-500"
                }
              >
                {calibrationStatus.data?.status ?? "pending"}
              </span>
            </div>
          )}

          {/* Results */}
          {calibrationStatus.data?.status === "complete" && (
            <div className="flex flex-col gap-4">
              {calibrationStatus.data.prCurveSvg ? (
                <div
                  aria-label="Precision-recall curve"
                  // biome-ignore lint/security/noDangerouslySetInnerHtml: SVG is generated server-side from numeric data only
                  dangerouslySetInnerHTML={{
                    __html: calibrationStatus.data.prCurveSvg,
                  }}
                />
              ) : null}

              <div className="flex flex-wrap items-end gap-4">
                <Input
                  label="Threshold"
                  type="number"
                  min="0"
                  max="1"
                  step="0.01"
                  value={thresholdInput?.toString() ?? ""}
                  onChange={(e: ChangeEvent<HTMLInputElement>) =>
                    setThresholdInput(Number(e.target.value))
                  }
                />
                {thresholdEval.data && (
                  <div className="flex gap-4 text-sm text-gray-700">
                    <span>P: {thresholdEval.data.precision.toFixed(3)}</span>
                    <span>R: {thresholdEval.data.recall.toFixed(3)}</span>
                    <span>F1: {thresholdEval.data.f1.toFixed(3)}</span>
                  </div>
                )}
              </div>

              {/* Promote */}
              {promotingModelId && (
                <div>
                  {showPromoteConfirm ? (
                    <div className="flex items-center gap-2">
                      <Button
                        intent="primary"
                        loading={promoteModel.isPending}
                        onClick={() => {
                          promoteModel.mutate(
                            {},
                            {
                              onSuccess: () => {
                                setShowPromoteConfirm(false)
                                void configQuery.refetch()
                              },
                            },
                          )
                        }}
                      >
                        Promote
                      </Button>
                      <Button
                        intent="secondary"
                        bordered
                        onClick={() => setShowPromoteConfirm(false)}
                      >
                        Cancel
                      </Button>
                      {form.emitNumericScore &&
                        activeFixture?.source === "SYNTHETIC_BOOTSTRAP" && (
                          <p className="text-xs text-warning-600">
                            Warning: emit score is locked for synthetic-only
                            fixtures.
                          </p>
                        )}
                    </div>
                  ) : (
                    <Button
                      intent="secondary"
                      bordered
                      onClick={() => setShowPromoteConfirm(true)}
                    >
                      Promote Model
                    </Button>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </PanelCard>
    </div>
  )
}
