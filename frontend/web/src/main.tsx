// Mount the page. StrictMode double-invokes render in development so
// side effects that are not safe show up early. The error boundary catches
// a crash in the tree and offers a reload instead of a blank page.

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { ErrorBoundary } from "./components/ErrorBoundary";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
);
