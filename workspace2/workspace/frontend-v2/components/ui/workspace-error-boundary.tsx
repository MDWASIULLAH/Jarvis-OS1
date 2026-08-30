"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";
import { EmptyState } from "./empty-state";

type Props = { children: ReactNode };
type State = { failed: boolean };

/** Keeps a feature failure local so the operating-system shell remains usable. */
export class WorkspaceErrorBoundary extends Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("JARVIS workspace module failed to render", error, info);
  }

  render(): ReactNode {
    if (this.state.failed) {
      return <EmptyState title="Module unavailable" description="This workspace module could not start. The rest of JARVIS OS remains available." action={<button onClick={() => this.setState({ failed: false })}>Try again</button>} />;
    }
    return this.props.children;
  }
}
