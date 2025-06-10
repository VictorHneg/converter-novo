import { Router } from "express";

export const googleDriveRouter = Router();

// Exemplo de rota
googleDriveRouter.get("/", (req, res) => {
  res.json({ message: "Google Drive route funcionando!" });
});
