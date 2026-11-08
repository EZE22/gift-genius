import { Component, type ErrorInfo, type ReactNode } from "react";

interface State {
  crashed: boolean;
}

/** Last line of defence: if rendering throws, show a way out instead of a blank page. */
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { crashed: false };

  static getDerivedStateFromError(): State {
    // React calls this during render, so it only flips the flag. Logging
    // happens in componentDidCatch, which runs after the tree has committed.
    return { crashed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("Gift Genius page error", error, info.componentStack);
  }

  render() {
    if (!this.state.crashed) return this.props.children;
    return (
      <main className="page">
        <header className="masthead">
          <h1>Gift Genius</h1>
        </header>
        <section className="panel error" role="alert" aria-labelledby="crash-heading">
          <h2 id="crash-heading" className="section-heading">
            Something went wrong on this page
          </h2>
          <p>Reload the page to start a new search.</p>
          <div className="button-row">
            <button type="button" className="button button-primary" onClick={() => window.location.reload()}>
              Reload
            </button>
          </div>
        </section>
      </main>
    );
  }
}
