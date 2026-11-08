// Shown when the search stops with an error event or a failed request.
// The message is the one the client already made safe to display. Try again
// reruns the same description and budget.

import { forwardRef } from "react";

export const ErrorPanel = forwardRef<HTMLDivElement, { message: string; onRetry: () => void }>(function ErrorPanel(
  { message, onRetry },
  ref,
) {
  return (
    <div className="error-panel" role="alert" tabIndex={-1} ref={ref}>
      <h2 className="section-heading">The search stopped</h2>
      <p>{message}</p>
      <button type="button" className="primary" onClick={onRetry}>
        Try again
      </button>
    </div>
  );
});
