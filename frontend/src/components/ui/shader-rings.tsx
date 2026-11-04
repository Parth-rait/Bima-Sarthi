"use client";

import { useEffect, useRef, useState } from "react";
import { RINGS } from "@/design/atmosphere";
import { cn } from "@/lib/utils";

/*
 * Parth's ShaderAnimation (concentric drifting rings), ported from three.js to a raw WebGL quad so it does not pull
 * the three.js chunk into the result screen (three.js is only ever loaded by the lazy work-stage scene). Changes:
 *   - recoloured from RGB channels to the palette (atmosphere.ts RINGS), drawn with alpha so the ink plate shows through
 *   - paused off screen and in a hidden tab, capped at RINGS.maxFps and RINGS.maxDpr
 *   - reduced motion draws one still frame; no WebGL (or jsdom) renders nothing, and the plate's CSS gradient remains
 */

const VERT = `attribute vec2 p; void main(){ gl_Position = vec4(p, 0.0, 1.0); }`;
const FRAG = `
precision highp float;
uniform vec2 resolution;
uniform float time;
uniform float lineWidth;
uniform float ceiling;
uniform vec3 c0; uniform vec3 c1; uniform vec3 c2;
void main(void) {
  vec2 uv = (gl_FragCoord.xy * 2.0 - resolution.xy) / min(resolution.x, resolution.y);
  float t = time * 0.05;
  vec3 k = vec3(0.0);
  for (int j = 0; j < 3; j++) {
    for (int i = 0; i < 5; i++) {
      k[j] += lineWidth * float(i * i) / abs(fract(t - 0.01 * float(j) + float(i) * 0.01) * 5.0 - length(uv) + mod(uv.x + uv.y, 0.2));
    }
  }
  k = clamp(k, 0.0, 1.0);
  vec3 col = c0 * k.x + c1 * k.y + c2 * k.z;
  float a = clamp(max(max(k.x, k.y), k.z), 0.0, ceiling);
  gl_FragColor = vec4(col * a, a);
}`;

const rgb = (hex: string) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255) as [number, number, number];

export function ShaderRings({ className }: { className?: string }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const [ok, setOk] = useState(true);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas || /jsdom/i.test(navigator.userAgent)) return setOk(false);
    const gl = canvas.getContext("webgl", { premultipliedAlpha: true, antialias: false, alpha: true });
    if (!gl) return setOk(false);
    const sh = (type: number, src: string) => {
      const s = gl.createShader(type)!;
      gl.shaderSource(s, src);
      gl.compileShader(s);
      return gl.getShaderParameter(s, gl.COMPILE_STATUS) ? s : null;
    };
    const vs = sh(gl.VERTEX_SHADER, VERT);
    const fs = sh(gl.FRAGMENT_SHADER, FRAG);
    if (!vs || !fs) return setOk(false);
    const prog = gl.createProgram()!;
    gl.attachShader(prog, vs);
    gl.attachShader(prog, fs);
    gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) return setOk(false);
    gl.useProgram(prog);
    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(prog, "p");
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    const u = (n: string) => gl.getUniformLocation(prog, n);
    gl.uniform1f(u("lineWidth"), RINGS.lineWidth);
    gl.uniform1f(u("ceiling"), RINGS.ceiling);
    gl.uniform3fv(u("c0"), rgb(RINGS.lineViolet));
    gl.uniform3fv(u("c1"), rgb(RINGS.lineSaffron));
    gl.uniform3fv(u("c2"), rgb(RINGS.linePeri));
    const uRes = u("resolution");
    const uTime = u("time");

    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    let time = 1;
    let raf = 0;
    let last = 0;
    let inView = true;
    const draw = () => {
      gl.uniform1f(uTime, time);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    };
    const size = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, RINGS.maxDpr);
      canvas.width = Math.max(1, Math.round(canvas.clientWidth * dpr));
      canvas.height = Math.max(1, Math.round(canvas.clientHeight * dpr));
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.uniform2f(uRes, canvas.width, canvas.height);
      draw();
    };
    const loop = (now: number) => {
      raf = requestAnimationFrame(loop);
      if (now - last < 1000 / RINGS.maxFps) return;
      time += ((now - (last || now)) / 1000) * 60 * RINGS.speed;
      last = now;
      draw();
    };
    const run = () => {
      cancelAnimationFrame(raf);
      last = 0;
      if (!mq.matches && inView && !document.hidden) raf = requestAnimationFrame(loop);
      else draw();
    };
    const ro = new ResizeObserver(size);
    ro.observe(canvas);
    const io = new IntersectionObserver(([e]) => {
      inView = e.isIntersecting;
      run();
    });
    io.observe(canvas);
    document.addEventListener("visibilitychange", run);
    mq.addEventListener("change", run);
    size();
    run();
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      io.disconnect();
      document.removeEventListener("visibilitychange", run);
      mq.removeEventListener("change", run);
      // free what this run made, but never lose the context: React's StrictMode runs the effect twice on one canvas,
      // and a lost context would leave the second run with nothing to draw on
      gl.deleteBuffer(buf);
      gl.deleteProgram(prog);
      gl.deleteShader(vs);
      gl.deleteShader(fs);
    };
  }, []);

  return ok ? <canvas ref={ref} aria-hidden="true" className={cn("pointer-events-none block h-full w-full", className)} /> : null;
}
