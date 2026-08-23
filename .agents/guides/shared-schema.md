# Guide: Shared Schema (`packages/schemas/`)

> **Important:** After the backend migration to Python/FastAPI, `packages/schemas/` is **frontend-only** (used by `apps/web` and `apps/worker`). The backend uses Python `StrEnum` in `apps/api/app/domain/models.py` as its enum source of truth. Enum values must be kept in sync manually between Python `StrEnum` and the frontend Zod schemas.

## Folder Contract

✅ Allowed:
- Type constants array + labels array + `get{Type}Label()` helper
- Zod schema for form payload, request body, job data
- `z.infer<>` types from schema
- Shared enum/constant values
- Export from `index.ts`

❌ Forbidden:
- Import FE-specific libraries (React) or BE-specific libraries (the BE is Python — it does not import this package)
- Business logic, side effects, API calls
- Response types — those belong in `packages/types/`
- Use `any`

---

## Conventions

### Schema File — Complete Pattern

```typescript
// packages/schemas/payment-method.ts
import { z } from "zod"

// 1. Type constants (array of valid values — must match Python StrEnum)
export const paymentMethodTypes = [
  "BANK_TRANSFER",
  "E_WALLET",
  "CREDIT_CARD",
  "QRIS",
  "COD",
] as const

// 2. Labels array (for dropdown/select)
export const paymentMethodLabels = [
  { label: "Bank Transfer", value: "BANK_TRANSFER" },
  { label: "E-Wallet", value: "E_WALLET" },
  { label: "Credit Card", value: "CREDIT_CARD" },
  { label: "QRIS", value: "QRIS" },
  { label: "Cash on Delivery", value: "COD" },
]

// 3. Helper function for display label
export const getPaymentMethodLabel = (value: typeof paymentMethodTypes[number]) => {
  const method = paymentMethodLabels.find((m) => m.value === value)
  return method ? method.label : value
}

// 4. Zod schema
export const paymentMethodSchema = z.object({
  name: z.string().min(1, "Name is required"),
  code: z.string().min(1, "Code is required"),
  type: z.enum(paymentMethodTypes),
  isActive: z.boolean().optional(),
})

// 5. Type alias
export type PaymentMethodSchemaProps = z.infer<typeof paymentMethodSchema>
```

### Re-export from Index

```typescript
// packages/schemas/index.ts
export * from "./payment-method"
export * from "./user"
export * from "./notification-channel"
```

---

## Cross-Stack Enum Sync

Since the backend is Python and the frontend is TypeScript, enums must be synced manually:

1. **Python (source of truth for BE):** `StrEnum` in `apps/api/app/domain/models.py`
2. **TypeScript (FE mirror):** `as const` array in `packages/schemas/{domain}.ts`

Both must have the same values in `SCREAMING_SNAKE_CASE`. When adding a new enum value:
1. Add to the Python `StrEnum` in `domain/models.py`
2. Add to the TypeScript `as const` array in `packages/schemas/{domain}.ts`
3. Add to the labels array (if applicable)

---

## Additional Rules

- **If a field has a fixed set of values, it MUST be declared here as an `as const` array + `z.enum()`.** This is the source of truth for the frontend. Values are always `SCREAMING_SNAKE_CASE` and must match the Python `StrEnum`.
- Each schema file should have a test file (`*.test.ts`)
- Type alias suffix: `SchemaProps` for form/payload (e.g., `PaymentMethodSchemaProps`)
- File must end with newline
