import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { AppShell } from "./components/AppShell";
import "./theme/tokens.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppShell>
      <App />
    </AppShell>
  </StrictMode>,
);
