/**
 * ATMOSPHERE: every cloud / sky / lamp colour and tuning knob in ONE place, so they can be tuned by eye in the browser.
 * Edit a value, save, the dev server hot-reloads. `npm run contrast` re-checks every text-over-atmosphere pair
 * from these same values (scripts/contrast-lib.mjs reads this file), so a careless edit fails the build.
 *
 * Direction: late-afternoon sky. Soft dusty-pink and warm-peach clouds, light apricot illumination, pale blue sky,
 * a breath of lavender, a gentle sun glow. Subtle and sophisticated: NOT saturated orange, NOT pink fantasy.
 *
 * Rules these values must keep (enforced by the contrast script):
 *   - text over any atmosphere is ink, on an ivory scrim at SCRIM.alpha or stronger;
 *   - the darkest pixel the shader can produce (cloud shadow) must still give ink >= 4.5:1 through the scrim;
 *   - the lamp's brightest glow must still give ivory text >= 4.5:1.
 */

/* ---------------------------------------------------------------------------------------------------------------
 * 1. CLOUD SHADER (landing hero; also the dev page). Colours are hex strings, passed straight to <CloudShader />.
 * ------------------------------------------------------------------------------------------------------------- */
export const SKY = {
  /** Cloud body. Dusty-pink / warm-peach. Lighter = fewer muddy shadows. Try #F6D8CA (default), #F2CFC2 (rosier), #F8E2D4 (airier). */
  cloudColor: "#F6D8CA",
  /** Sky at the top of the frame: pale blue. Try #B9D0E6 (default), #C9DAEA (paler). */
  skyTopColor: "#B9D0E6",
  /** Sky at the horizon (bottom of the frame): warm apricot-cream light. Try #F8E3D0 (default), #F5D3B8 (warmer, more apricot). */
  skyBottomColor: "#F8E3D0",
  /** Drift speed multiplier. 1 = the component's default; 0.5 is calm. */
  speed: 0.5,
  /** Number of clouds, 1 to 6. Fewer = cheaper on the GPU and calmer. */
  count: 4,
  /**
   * Render resolution as a fraction of the CSS size (before devicePixelRatio). Clouds are low-frequency, so 0.6
   * looks the same and costs ~36% of the pixels. 1 = full resolution. Lower this first if the sky stutters.
   */
  renderScale: 0.6,
  /** Frame cap. Clouds drift slowly; 30 fps halves the GPU work. 0 = uncapped. */
  maxFps: 30,
  /** devicePixelRatio ceiling (the original allowed 2). */
  maxDpr: 1.5,
} as const;

/** The static fallback sky (CSS only) is built from SKY plus these two extras. Used when WebGL is missing, on low-power devices, or when the visitor turns the sky off. */
export const SKY_STATIC = {
  /** Soft sun glow, upper right. Any CSS colour. */
  sun: "rgba(255, 238, 205, 0.85)",
  /** Where the sun sits, as CSS percentages of the hero. */
  sunAt: "78% 8%",
  /** A breath of lavender between blue and peach. Any CSS colour. */
  lavenderBand: "rgba(217, 210, 230, 0.55)",
  /** Where the lavender sits (percent from the top). */
  lavenderAtPct: 46,
  /** Soft cloud banks (peach, low alpha), as [x%, y%, width%, height%] ellipses. */
  clouds: [
    [18, 62, 46, 22],
    [72, 70, 54, 26],
    [48, 40, 34, 14],
  ] as ReadonlyArray<readonly [number, number, number, number]>,
  cloudAlpha: 0.7,
} as const;

/** The ivory scrim laid over the sky behind the hero text and the navbar, so ink text keeps >= 4.5:1 over the darkest cloud shadow. */
export const SCRIM = {
  /** Alpha of the ivory scrim behind the headline block (0.7 = 70% ivory). Raise it if the text ever feels busy. */
  alpha: 0.72,
  /** Alpha of the ivory wash at the very top of the hero (under the transparent navbar). */
  navAlpha: 0.8,
} as const;

/* ---------------------------------------------------------------------------------------------------------------
 * 2. LAMP (How it works intro). Geometry and technique are the registry's; only the light changes: cyan -> sunlight.
 * ------------------------------------------------------------------------------------------------------------- */
export const LAMP = {
  /** Page colour of the lamp section. Matches the ink band so the lamp section joins the footer family. */
  background: "#2a2630",
  /** The two light beams (conic gradients). Apricot. */
  beam: "#e9a87f",
  /** The wide soft glow behind the lamp (was cyan-500, blur-3xl). */
  glow: "#e9a87f",
  /** Opacity of that wide glow (original 0.5). Lower = calmer and keeps heading contrast high. */
  glowOpacity: 0.35,
  /** The small bright inner glow (was cyan-400, blur-2xl). */
  core: "#f2c6a0",
  /** The thin lamp line (was cyan-400, 0.5rem tall). Champagne gold: a hairline, the only place gold appears larger than an underline. */
  line: "#d9be8a",
} as const;

/* ---------------------------------------------------------------------------------------------------------------
 * 3. TIMELINE (How it works). The scroll-progress line; the track and the node dots use the page tokens.
 * ------------------------------------------------------------------------------------------------------------- */
export const TIMELINE = {
  /** Progress line gradient, from the filled end to the faded end (was purple-500 -> blue-500). Apricot -> dusty rose. */
  progressFrom: "#e9a87f",
  progressVia: "#d9a9a6",
} as const;
