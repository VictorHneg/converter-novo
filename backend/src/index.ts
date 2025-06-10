import "dotenv/config";
import express from "express";
import cors from "cors";
import { envSchema } from "./utils/env";
import { googleDriveRouter } from "./routes/googleDrive";
import * as z from "zod";

// Validação do .env
const env = envSchema.parse(process.env);

const app = express();

app.use(cors({ origin: env.FRONTEND_URL, credentials: true }));
app.use(express.json());

// Rotas principais
app.use("/api/drive", googleDriveRouter);

app.get("/health", (_, res) => res.json({ status: "ok" }));

// Tratamento de erros globais
app.use((err: any, _req: any, res: any, _next: any) => {
  if (err instanceof z.ZodError) {
    return res.status(400).json({ error: err.errors });
  }
  return res.status(500).json({ error: err.message || "Erro interno" });
});

const port = env.PORT || 4000;
app.listen(port, () => {
  console.log(`Servidor rodando na porta ${port}`);
});