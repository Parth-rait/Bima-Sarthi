import { useEffect, useMemo, useRef, type RefObject } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Environment, Float, Lightformer, MeshTransmissionMaterial, PresentationControls, RoundedBox } from "@react-three/drei";
import * as THREE from "three";
import { STAGE } from "@/design/atmosphere";

/**
 * The claim flow's working scene: three glass sheets of a claim file.
 *
 *   arrive    a private session is being opened: the sheets rise into a fan
 *   reading   the documents are being read: a saffron scan line passes down the front sheet, lighting each line it reads
 *   saving    the answers are being saved: the fan closes into a stack
 *   checking  the rules check is running: a glass lens moves line by line, and each line it has passed turns indigo
 *
 * It is decoration (the HTML beside it says what is happening, in words), so the canvas is aria-hidden by its parent.
 * The mode comes from the request really in flight; nothing here pretends to measure progress.
 * Drag turns the file (fine pointers only); the pointer also tilts it a little. Lazy-loaded: three.js is fetched only
 * when the claim flow is about to need it.
 */
export type SceneMode = "arrive" | "reading" | "saving" | "checking";

const LINES_FRONT = [0.92, 1.22, 1.08, 1.26, 0.74, 1.18, 1.02, 1.24, 0.66];
const LINES_BACK = [0.9, 1.2, 1.05, 1.22, 0.8, 1.1];
const SHEET_W = 1.72;
const SHEET_H = 2.24;
const SHEET_D = 0.05;
const LINE_LEFT = -0.68;
const LINE_TOP = 0.74;
const LINE_STEP = 0.165;

const lineY = (i: number) => (i === 0 ? LINE_TOP + 0.08 : LINE_TOP - i * LINE_STEP);
const lineH = (i: number) => (i === 0 ? 0.075 : 0.04);

type Pose = { p: [number, number, number]; rz: number };
const FAN: Pose[] = [
  { p: [-0.64, 0.2, -0.58], rz: 0.15 },
  { p: [-0.16, 0.07, -0.29], rz: -0.06 },
  { p: [0.3, -0.06, 0], rz: 0.035 },
];
const STACK: Pose[] = [
  { p: [0.12, 0.02, -0.26], rz: 0.05 },
  { p: [0.2, -0.02, -0.13], rz: -0.025 },
  { p: [0.3, -0.06, 0], rz: 0.01 },
];

const damp = THREE.MathUtils.damp;

/* ---------- the light behind the glass: a slow aurora on a plane far behind the sheets ---------- */
const BACKDROP_VERT = /* glsl */ `
varying vec2 vUv;
void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }
`;
const BACKDROP_FRAG = /* glsl */ `
uniform float uTime;
uniform vec3 uTop;
uniform vec3 uFoot;
uniform vec3 uViolet;
uniform vec3 uSaffron;
varying vec2 vUv;
void main() {
  float t = uTime * 0.12;
  vec3 col = mix(uFoot, uTop, smoothstep(0.0, 1.0, vUv.y));
  float v = 1.0 - smoothstep(0.0, 0.55, distance(vUv, vec2(0.28 + 0.07 * sin(t * 1.7), 0.72 + 0.05 * cos(t * 1.3))));
  float s = 1.0 - smoothstep(0.0, 0.5, distance(vUv, vec2(0.78 + 0.05 * cos(t * 1.1), 0.24 + 0.06 * sin(t * 1.5))));
  col = mix(col, uViolet, v * 0.85);
  col = mix(col, uSaffron, s * 0.75);
  gl_FragColor = vec4(col, 1.0);
  #include <colorspace_fragment>
}
`;

function Backdrop({ still }: { still: boolean }) {
  const mat = useRef<THREE.ShaderMaterial>(null);
  const { camera, viewport } = useThree();
  const v = viewport.getCurrentViewport(camera, new THREE.Vector3(0, 0, -3));
  const uniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uTop: { value: new THREE.Color(STAGE.skyTop) },
      uFoot: { value: new THREE.Color(STAGE.skyFoot) },
      uViolet: { value: new THREE.Color(STAGE.bloomViolet) },
      uSaffron: { value: new THREE.Color(STAGE.bloomSaffron) },
    }),
    [],
  );
  useFrame((_, dt) => {
    if (!still && mat.current) mat.current.uniforms.uTime.value += dt;
  });
  return (
    <mesh position={[0, 0, -3]} scale={[v.width * 1.3, v.height * 1.3, 1]}>
      <planeGeometry />
      <shaderMaterial ref={mat} uniforms={uniforms} vertexShader={BACKDROP_VERT} fragmentShader={BACKDROP_FRAG} toneMapped={false} depthWrite={false} />
    </mesh>
  );
}

/* ---------- the scan line: a soft saffron band with a light that travels with it ---------- */
const SCAN_FRAG = /* glsl */ `
uniform vec3 uColor;
uniform float uOpacity;
varying vec2 vUv;
void main() {
  float band = exp(-pow((vUv.y - 0.5) * 9.0, 2.0));
  float edge = smoothstep(0.0, 0.12, vUv.x) * smoothstep(1.0, 0.88, vUv.x);
  gl_FragColor = vec4(uColor, band * edge * uOpacity);
  #include <colorspace_fragment>
}
`;

function Lines({ widths, refs, back }: { widths: number[]; refs?: RefObject<(THREE.Mesh | null)[]>; back?: boolean }) {
  return (
    <group position={[0, 0, SHEET_D / 2 + 0.006]}>
      {widths.map((w, i) => (
        <mesh
          key={i}
          ref={(m) => {
            if (refs?.current) refs.current[i] = m;
          }}
          position={[LINE_LEFT + w / 2, lineY(i), 0]}
        >
          <boxGeometry args={[w, lineH(i), 0.008]} />
          <meshStandardMaterial color={STAGE.ink} transparent opacity={back ? 0.22 : 0.6} roughness={0.6} emissive={STAGE.scan} emissiveIntensity={0} />
        </mesh>
      ))}
    </group>
  );
}

function Dossier({ mode, still, interactive }: { mode: SceneMode; still: boolean; interactive: boolean }) {
  const sheets = useRef<(THREE.Group | null)[]>([]);
  const tilt = useRef<THREE.Group>(null);
  const lines = useRef<(THREE.Mesh | null)[]>([]);
  const scan = useRef<THREE.Mesh>(null);
  const scanMat = useRef<THREE.ShaderMaterial>(null);
  const scanLight = useRef<THREE.PointLight>(null);
  const lens = useRef<THREE.Group>(null);
  const born = useRef<number | null>(null);
  const checkedAt = useRef(0);
  const ink = useMemo(() => new THREE.Color(STAGE.ink), []);
  const checked = useMemo(() => new THREE.Color(STAGE.checked), []);
  const scanUniforms = useMemo(() => ({ uColor: { value: new THREE.Color(STAGE.scan) }, uOpacity: { value: 0 } }), []);

  useEffect(() => {
    if (mode === "checking") checkedAt.current = -1;
  }, [mode]);

  useFrame((state, rawDt) => {
    const dt = Math.min(rawDt, 1 / 20);
    const t = state.clock.elapsedTime;
    if (born.current === null) born.current = t;
    const age = still ? 10 : t - born.current;
    const poses = mode === "saving" || mode === "checking" ? STACK : FAN;

    // sheets: rise into place once (staggered), then follow the pose of the current mode
    sheets.current.forEach((g, i) => {
      if (!g) return;
      const enter = THREE.MathUtils.clamp((age - i * 0.14) / 0.9, 0, 1);
      const ease = 1 - Math.pow(1 - enter, 3);
      const pose = poses[i];
      const y = pose.p[1] - (1 - ease) * 3.2;
      g.position.x = damp(g.position.x, pose.p[0], 5, dt);
      g.position.y = enter < 1 ? y : damp(g.position.y, pose.p[1], 5, dt);
      g.position.z = damp(g.position.z, pose.p[2], 5, dt);
      g.rotation.z = damp(g.rotation.z, pose.rz, 5, dt);
      g.rotation.x = (1 - ease) * -0.6;
    });

    // the pointer tilts the file a little (on top of whatever the drag is doing)
    if (tilt.current && interactive && !still) {
      tilt.current.rotation.y = damp(tilt.current.rotation.y, state.pointer.x * 0.22, 3, dt);
      tilt.current.rotation.x = damp(tilt.current.rotation.x, -state.pointer.y * 0.14, 3, dt);
    }

    // reading: the scan travels down the front sheet and lights the line it is on
    const reading = mode === "reading" || mode === "arrive";
    const scanOpacity = scanMat.current ? damp(scanMat.current.uniforms.uOpacity.value, reading && mode === "reading" ? 0.6 : 0, 6, dt) : 0;
    if (scanMat.current) scanMat.current.uniforms.uOpacity.value = scanOpacity;
    const span = SHEET_H * 0.94;
    const scanY = still ? 0.2 : SHEET_H * 0.47 - ((t * 0.42) % 1) * span;
    if (scan.current) scan.current.position.y = scanY;
    if (scanLight.current) {
      scanLight.current.position.y = scanY;
      scanLight.current.intensity = scanOpacity * 1.4;
    }

    // checking: the lens steps line by line; lines it has passed are checked
    const checking = mode === "checking";
    const step = still ? 4 : Math.floor(t * 1.5) % (LINES_FRONT.length + 2);
    const target = Math.min(step, LINES_FRONT.length - 1);
    if (lens.current) {
      const s = damp(lens.current.scale.x, checking ? 1 : 0.001, 6, dt);
      lens.current.scale.setScalar(s);
      lens.current.position.x = damp(lens.current.position.x, LINE_LEFT + LINES_FRONT[target] - 0.08, 7, dt);
      lens.current.position.y = damp(lens.current.position.y, lineY(target), 7, dt);
    }

    lines.current.forEach((m, i) => {
      if (!m) return;
      const mat = m.material as THREE.MeshStandardMaterial;
      const d = lineY(i) - scanY;
      const lit = mode === "reading" ? Math.exp(-(d * d) / 0.004) * scanOpacity : 0;
      mat.emissiveIntensity = damp(mat.emissiveIntensity, lit * 2.2, 14, dt);
      const isChecked = checking && i < step;
      const pulse = mode === "saving" ? 0.5 + 0.5 * Math.sin(t * 3 - i * 0.5) : 0;
      mat.color.lerp(isChecked ? checked : ink, 1 - Math.exp(-8 * dt));
      mat.opacity = damp(mat.opacity, 0.5 + 0.35 * (isChecked ? 1 : pulse), 6, dt);
    });
  });

  const front = (
    <group ref={(g) => void (sheets.current[2] = g)} position={[FAN[2].p[0], -3, FAN[2].p[2]]}>
      <RoundedBox args={[SHEET_W, SHEET_H, SHEET_D]} radius={0.05} smoothness={4}>
        <MeshTransmissionMaterial
          color={STAGE.glassFront}
          transmission={1}
          thickness={0.35}
          roughness={0.16}
          ior={1.25}
          chromaticAberration={0.05}
          anisotropicBlur={0.1}
          distortion={0.08}
          distortionScale={0.3}
          temporalDistortion={still ? 0 : 0.06}
          samples={STAGE.transmissionSamples}
          resolution={STAGE.transmissionResolution}
          backside={false}
        />
      </RoundedBox>
      <Lines widths={LINES_FRONT} refs={lines} />
      <mesh ref={scan} position={[0, 0, SHEET_D / 2 + 0.02]}>
        <planeGeometry args={[SHEET_W * 1.08, 0.34]} />
        <shaderMaterial ref={scanMat} uniforms={scanUniforms} vertexShader={BACKDROP_VERT} fragmentShader={SCAN_FRAG} transparent depthWrite={false} blending={THREE.AdditiveBlending} toneMapped={false} />
      </mesh>
      <pointLight ref={scanLight} color={STAGE.scan} distance={1.6} decay={1.4} intensity={0} position={[0, 0, 0.45]} />
      <group ref={lens} position={[0, lineY(0), SHEET_D / 2 + 0.16]} scale={0.001}>
        <mesh>
          <torusGeometry args={[0.2, 0.032, 24, 64]} />
          <meshPhysicalMaterial color={STAGE.lensRim} metalness={0.35} roughness={0.18} clearcoat={1} />
        </mesh>
        <mesh>
          <circleGeometry args={[0.19, 48]} />
          <meshPhysicalMaterial color="#ffffff" transmission={1} thickness={0.25} roughness={0.04} ior={1.45} transparent />
        </mesh>
        <mesh position={[0.2, -0.2, 0]} rotation={[0, 0, Math.PI / 4]}>
          <capsuleGeometry args={[0.03, 0.18, 6, 16]} />
          <meshPhysicalMaterial color={STAGE.lensRim} metalness={0.35} roughness={0.2} clearcoat={1} />
        </mesh>
      </group>
    </group>
  );

  const back = (i: 0 | 1, color: string) => (
    <group ref={(g) => void (sheets.current[i] = g)} position={[FAN[i].p[0], -3, FAN[i].p[2]]}>
      <RoundedBox args={[SHEET_W, SHEET_H, SHEET_D]} radius={0.05} smoothness={4}>
        <meshPhysicalMaterial color={color} emissive={color} emissiveIntensity={0.22} transparent opacity={0.6} roughness={0.22} metalness={0} iridescence={0.5} iridescenceIOR={1.3} clearcoat={1} clearcoatRoughness={0.15} depthWrite={false} />
      </RoundedBox>
      <Lines widths={LINES_BACK} back />
    </group>
  );

  return (
    <group ref={tilt} position={[0.12, 0, 0]}>
      {back(0, STAGE.glassBack)}
      {back(1, STAGE.glassMid)}
      {front}
    </group>
  );
}

export default function ClaimScene({
  mode,
  still = false,
  interactive = true,
  eventSource,
  onReady,
}: {
  mode: SceneMode;
  /** reduced motion: one composed frame, nothing moves */
  still?: boolean;
  /** fine pointer: drag to turn, pointer tilt */
  interactive?: boolean;
  /** the element whose pointer moves drive the tilt (the whole stage, not just the canvas) */
  eventSource?: RefObject<HTMLElement | null>;
  onReady?: () => void;
}) {
  return (
    <Canvas
      flat
      dpr={[STAGE.minDpr, STAGE.maxDpr]}
      camera={{ position: [0, 0, 5], fov: 32 }}
      gl={{ antialias: true, alpha: false, powerPreference: "high-performance" }}
      eventSource={eventSource as RefObject<HTMLElement> | undefined}
      eventPrefix="client"
      frameloop={still ? "demand" : "always"}
      onCreated={() => onReady?.()}
      style={{ touchAction: "pan-y" }}
    >
      <Backdrop still={still} />
      <ambientLight intensity={0.55} />
      <directionalLight position={[2, 3, 4]} intensity={1.1} />
      <Environment resolution={128} frames={1}>
        <color attach="background" args={[STAGE.skyTop]} />
        <Lightformer form="rect" intensity={2.4} color="#ffffff" position={[0, 3, 3]} scale={[8, 1.2, 1]} />
        <Lightformer form="rect" intensity={1.4} color={STAGE.glassMid} position={[-4, 0, 2]} rotation={[0, Math.PI / 2, 0]} scale={[2.5, 6, 1]} />
        <Lightformer form="ring" intensity={1.8} color={STAGE.scan} position={[3.5, -2, 2]} scale={2.2} />
      </Environment>
      <PresentationControls enabled={interactive && !still} global={false} cursor snap polar={[-0.3, 0.3]} azimuth={[-0.65, 0.65]}>
        <Float enabled={!still} speed={1.3} rotationIntensity={0.12} floatIntensity={0.35} floatingRange={[-0.05, 0.05]}>
          <Dossier mode={mode} still={still} interactive={interactive} />
        </Float>
      </PresentationControls>
    </Canvas>
  );
}
