import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import { App } from "./app/App";
import { ServiceProvider } from "./app/ServiceStatus";
import { SessionProvider } from "./state/store";
import "./styles/index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <ServiceProvider>
        <SessionProvider>
          <App />
        </SessionProvider>
      </ServiceProvider>
    </BrowserRouter>
  </StrictMode>,
);
