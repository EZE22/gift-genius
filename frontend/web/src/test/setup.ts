// Vitest setup for the web app. jest-dom adds matchers such as toBeInTheDocument.
// cleanup unmounts the rendered page after each test so the next one starts empty.

import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => cleanup());
