import { Component, type ReactNode } from "react";

/** Catches a failed lazy chunk (offline, blocked) or a render error inside decorative 3D/WebGL, and shows the static fallback instead. */
export class Boundary extends Component<{ fallback: ReactNode; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch() {
    /* nothing to report: the fallback is the designed degraded state */
  }
  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}
