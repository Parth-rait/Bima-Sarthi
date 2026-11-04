import { Component, createRef, type ReactNode } from "react";

/*
 * The claim flow's page change, after the "tumble deck" Parth sent: the sheets stand one behind the other; going
 * forward, the sheet you were on tips over its bottom edge and falls flat while the next one slides up to the line;
 * going back, the old sheet slips back into the deck and the earlier one stands up again from the floor.
 *
 * How: just before React swaps the screens, getSnapshotBeforeUpdate copies the outgoing sheet's DOM (cloneNode, no
 * HTML strings); after the swap, that copy plays the fall on top of the new sheet and removes itself. The copy is
 * decoration: aria-hidden, inert, its ids, names and canvases stripped, so assistive tech, forms and focus only ever
 * meet the real new screen, which is in the document from the first frame. No Web Animations API (jsdom, very old
 * browsers) or reduced motion: no copy, the new screen simply appears.
 */

type Props = { view: string; dir: 1 | -1; reduce: boolean; children: ReactNode };
type Snap = { clone: HTMLElement; height: number } | null;

const FALL: Keyframe[] = [
  { transform: "perspective(1600px) rotateX(0deg)", opacity: 1, offset: 0 },
  { transform: "perspective(1600px) rotateX(-86deg)", opacity: 0.9, offset: 0.78 },
  { transform: "perspective(1600px) rotateX(-80deg)", opacity: 0.55, offset: 0.88 },
  { transform: "perspective(1600px) rotateX(-90deg)", opacity: 0, offset: 1 },
];
const RECEDE: Keyframe[] = [
  { transform: "perspective(1600px) translate3d(0, 0, 0)", opacity: 1 },
  { transform: "perspective(1600px) translate3d(0, -26px, -140px)", opacity: 0 },
];

export class Tumble extends Component<Props> {
  private host = createRef<HTMLDivElement>();
  private stage = createRef<HTMLDivElement>();

  getSnapshotBeforeUpdate(prev: Props): Snap {
    const el = this.host.current?.firstElementChild as HTMLElement | null;
    if (prev.view === this.props.view || this.props.reduce || !el || typeof el.animate !== "function") return null;
    const clone = el.cloneNode(true) as HTMLElement;
    clone.querySelectorAll("canvas, video, iframe").forEach((n) => n.remove());
    clone.querySelectorAll("[id],[name],[for],[autofocus]").forEach((n) => {
      n.removeAttribute("id");
      n.removeAttribute("name");
      n.removeAttribute("for");
      n.removeAttribute("autofocus");
    });
    clone.removeAttribute("id");
    return { clone, height: el.getBoundingClientRect().height };
  }

  componentDidUpdate(_prev: Props, _state: unknown, snap: Snap) {
    const stage = this.stage.current;
    if (!snap || !stage) return;
    const ghost = document.createElement("div");
    ghost.className = "tumble-ghost";
    ghost.setAttribute("aria-hidden", "true");
    ghost.setAttribute("inert", "");
    // a falling sheet taller than the window would hinge far below it; fall the part you were looking at
    ghost.style.height = `${Math.min(snap.height, Math.round(window.innerHeight * 0.85))}px`;
    ghost.appendChild(snap.clone);
    stage.replaceChildren(ghost);
    const forward = this.props.dir === 1;
    const anim = ghost.animate(forward ? FALL : RECEDE, {
      duration: forward ? 620 : 420,
      easing: forward ? "cubic-bezier(0.55, 0, 0.85, 0.36)" : "cubic-bezier(0.4, 0, 1, 1)",
      fill: "forwards",
    });
    const done = () => ghost.remove();
    anim.onfinish = done;
    anim.oncancel = done;
  }

  render() {
    return (
      <>
        <div ref={this.stage} className="tumble-stage" aria-hidden="true" />
        <div ref={this.host} className="tumble-host">
          {this.props.children}
        </div>
      </>
    );
  }
}
