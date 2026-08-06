import { z } from "zod"

const envSchema = z.object({
  NODE_ENV: z
    .enum(["development", "test", "production"])
    .default("development"),
  REDIS_URL: z.string().url().default("redis://127.0.0.1:6379"),
  INTERNAL_API_URL: z.string().url().default("http://127.0.0.1:8000"),
  INTERNAL_API_SECRET: z.string().default("dev-internal-secret"),
})

export const env = envSchema.parse(process.env)
