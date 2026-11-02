import { render, waitFor } from "@testing-library/react";
import type { ReactElement } from "react";
import { expect } from "vitest";
import { MemoryRouter } from "react-router";
import { App } from "../app/App";
import type { SessionState } from "../state/session";
import { SessionProvider } from "../state/store";

/** Render the whole shell at a route (default /check-claim, where the workflow lives). */
export async function renderApp(initial?: Partial<SessionState>, route = "/check-claim") {
  const out = render(
    <MemoryRouter initialEntries={[route]}>
      <SessionProvider initial={initial}>
        <App />
      </SessionProvider>
    </MemoryRouter>,
  );
  // pages are lazy chunks: wait until the route's page has rendered (every page has one [data-page-heading])
  await waitFor(() => expect(document.querySelector("main [data-page-heading]")).toBeTruthy());
  return out;
}

/** Render one component inside the session provider (and a router, for components with links). */
export function renderIn(ui: ReactElement, initial?: Partial<SessionState>) {
  return render(
    <MemoryRouter>
      <SessionProvider initial={initial}>{ui}</SessionProvider>
    </MemoryRouter>,
  );
}
