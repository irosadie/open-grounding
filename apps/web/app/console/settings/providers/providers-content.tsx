"use client"

import { Button } from "$/components/button"
import { Input } from "$/components/input"
import { PanelCard } from "$/components/panel-card"
import {
  useProviderCredentials,
  useRevokeProviderCredential,
  useSetProviderCredential,
} from "$/hooks/transactions/use-provider-credentials"
import { CheckCircle, Key, Trash2, XCircle } from "lucide-react"
import { type ChangeEvent, useState } from "react"

type ProviderConfig = {
  provider: string
  keyName: string
  label: string
  description: string
  placeholder: string
  docsUrl?: string
}

const PROVIDER_CONFIGS: ProviderConfig[] = [
  {
    provider: "openai",
    keyName: "api_key",
    label: "OpenAI API Key",
    description:
      "Required for OpenAI embedding models (text-embedding-3-small, text-embedding-3-large) and GPT generation.",
    placeholder: "sk-...",
    docsUrl: "https://platform.openai.com/api-keys",
  },
  {
    provider: "ollama",
    keyName: "base_url",
    label: "Ollama Base URL",
    description:
      "URL of your self-hosted Ollama server for local embedding and generation models.",
    placeholder: "http://localhost:11434",
  },
  {
    provider: "huggingface",
    keyName: "token",
    label: "HuggingFace Token",
    description:
      "Required to access private HuggingFace models and higher rate limits.",
    placeholder: "hf_...",
    docsUrl: "https://huggingface.co/settings/tokens",
  },
]

export default function ProvidersContent() {
  const { data: credentials, isLoading } = useProviderCredentials()
  const setMutation = useSetProviderCredential()
  const revokeMutation = useRevokeProviderCredential()

  const [values, setValues] = useState<Record<string, string>>({})
  const [editing, setEditing] = useState<string | null>(null)
  const [errors, setErrors] = useState<Record<string, string>>({})

  const getStatus = (provider: string, keyName: string) =>
    credentials?.find((c) => c.provider === provider && c.keyName === keyName)

  const handleSet = async (config: ProviderConfig) => {
    const key = `${config.provider}:${config.keyName}`
    const value = values[key] ?? ""
    if (!value.trim()) {
      setErrors((e) => ({ ...e, [key]: "Value is required." }))
      return
    }
    setErrors((e) => ({ ...e, [key]: "" }))
    try {
      await setMutation.mutateAsync({
        provider: config.provider,
        keyName: config.keyName,
        value: value.trim(),
      })
      setValues((v) => ({ ...v, [key]: "" }))
      setEditing(null)
    } catch (error) {
      setErrors((e) => ({
        ...e,
        [key]: (error as { message?: string })?.message ?? "Failed to save.",
      }))
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">
          Provider Credentials
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          Configure API keys for embedding and generation providers. Keys are
          encrypted at rest and never displayed after saving.
        </p>
      </div>

      {isLoading ? (
        <div className="py-8 text-center text-sm text-gray-400">Loading...</div>
      ) : (
        <div className="flex flex-col gap-4">
          {PROVIDER_CONFIGS.map((config) => {
            const key = `${config.provider}:${config.keyName}`
            const status = getStatus(config.provider, config.keyName)
            const isConfigured = status?.isConfigured ?? false
            const isEditing = editing === key

            return (
              <PanelCard key={key}>
                <div className="flex flex-col gap-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-3">
                      <Key className="mt-0.5 h-5 w-5 shrink-0 text-gray-400" />
                      <div>
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-semibold text-gray-900">
                            {config.label}
                          </p>
                          {isConfigured ? (
                            <span className="flex items-center gap-1 rounded-full bg-success-100 px-2 py-0.5 text-[10px] font-medium text-success-700">
                              <CheckCircle className="h-3 w-3" /> Configured
                            </span>
                          ) : (
                            <span className="flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-500">
                              <XCircle className="h-3 w-3" /> Not configured
                            </span>
                          )}
                        </div>
                        <p className="mt-0.5 text-xs text-gray-500">
                          {config.description}
                        </p>
                        {config.docsUrl ? (
                          <a
                            href={config.docsUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="mt-0.5 text-xs text-primary-600 hover:underline"
                          >
                            Get API key →
                          </a>
                        ) : null}
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      {isConfigured && !isEditing ? (
                        <>
                          <Button
                            intent="secondary"
                            size="small"
                            bordered
                            onClick={() => setEditing(key)}
                          >
                            Update
                          </Button>
                          <Button
                            intent="secondary"
                            size="small"
                            bordered
                            leftIcon={<Trash2 className="h-3.5 w-3.5" />}
                            onClick={() =>
                              revokeMutation.mutate({
                                provider: config.provider,
                                keyName: config.keyName,
                              })
                            }
                            loading={revokeMutation.isPending}
                          >
                            Revoke
                          </Button>
                        </>
                      ) : !isEditing ? (
                        <Button
                          intent="primary"
                          size="small"
                          onClick={() => setEditing(key)}
                        >
                          Configure
                        </Button>
                      ) : null}
                    </div>
                  </div>

                  {isEditing ? (
                    <div className="flex flex-col gap-3 rounded-lg border border-gray-200 bg-gray-50 p-4">
                      <Input
                        label={config.label}
                        name={key}
                        type="password"
                        placeholder={config.placeholder}
                        value={values[key] ?? ""}
                        onChange={(e: ChangeEvent<HTMLInputElement>) => {
                          setValues((v) => ({ ...v, [key]: e.target.value }))
                          setErrors((er) => ({ ...er, [key]: "" }))
                        }}
                        hint="Entered value is encrypted immediately and never displayed."
                        error={errors[key]}
                        required
                      />
                      <div className="flex gap-2">
                        <Button
                          intent="primary"
                          size="small"
                          onClick={() => handleSet(config)}
                          loading={setMutation.isPending}
                          disabled={!values[key]?.trim()}
                        >
                          Save
                        </Button>
                        <Button
                          intent="secondary"
                          size="small"
                          bordered
                          onClick={() => {
                            setEditing(null)
                            setValues((v) => ({ ...v, [key]: "" }))
                            setErrors((er) => ({ ...er, [key]: "" }))
                          }}
                        >
                          Cancel
                        </Button>
                      </div>
                    </div>
                  ) : null}
                </div>
              </PanelCard>
            )
          })}
        </div>
      )}
    </div>
  )
}
