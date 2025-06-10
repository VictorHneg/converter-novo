import { z } from "zod";

export const envSchema = z.object({
  FRONTEND_URL: z.string().url(),
  PORT: z.string().optional(),
  // Adicione outras variáveis de ambiente conforme necessário
});
