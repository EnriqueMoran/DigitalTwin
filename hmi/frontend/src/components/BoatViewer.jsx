import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

const boatUrl = '/boat.glb';

export default function BoatViewer({ sensors }) {
  const mountRef = useRef(null);
  const [live, setLive] = useState(true);
  const liveRef = useRef(false);
  const sensorsRef = useRef();
  const modelRef = useRef();
  const [axisMode, setAxisMode] = useState('all'); // 'all' | 'x' | 'y' | 'z'
  const axisModeRef = useRef('all');
  const cameraRef = useRef(null);
  const controlsRef = useRef(null);
  const centerRef = useRef(new THREE.Vector3(0, 0, 0));
  const distRef = useRef(5);
  liveRef.current = live;
  sensorsRef.current = sensors;
  axisModeRef.current = axisMode;

  useEffect(() => {
    const mount = mountRef.current;
    const scene = new THREE.Scene();
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    mount.appendChild(renderer.domElement);

    const camera = new THREE.PerspectiveCamera(45, mount.clientWidth / mount.clientHeight, 0.1, 1000);
    camera.position.set(0, 2, 5);
    cameraRef.current = camera;

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;

    let wheelActive = false;
    let wheelTimer = null;
    const onWheel = () => {
      wheelActive = true;
      if (wheelTimer) clearTimeout(wheelTimer);
      wheelTimer = setTimeout(() => {
        wheelActive = false;
      }, 200);
    };
    renderer.domElement.addEventListener('wheel', onWheel, { passive: true });

    const onControlsStart = () => {
      if (!wheelActive) setLive(false);
    };
    controls.addEventListener('start', onControlsStart);
    controlsRef.current = controls;

    const light = new THREE.DirectionalLight(0xffffff, 1);
    light.position.set(5, 10, 7.5);
    scene.add(light);
    const ambient = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambient);

    const loader = new GLTFLoader();
    loader.load(
      boatUrl,
      (gltf) => {
        modelRef.current = gltf.scene;
        scene.add(modelRef.current);
        modelRef.current.rotation.order = 'ZXY';

        const box = new THREE.Box3().setFromObject(gltf.scene);
        const center = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());
        const maxDim = Math.max(size.x, size.y, size.z);
        const fov = (camera.fov * Math.PI) / 180;
        let cameraZ = Math.abs(maxDim / 2 / Math.tan(fov / 2));
        cameraZ *= 1.1;
        centerRef.current.copy(center);
        distRef.current = cameraZ;
        // Apply initial view based on current mode
        applyView(axisModeRef.current);
        animate();
      },
      undefined,
      () => {
        const geometry = new THREE.BoxGeometry();
        const material = new THREE.MeshNormalMaterial();
        const cube = new THREE.Mesh(geometry, material);
        modelRef.current = cube;
        scene.add(cube);
        centerRef.current.set(0, 0, 0);
        distRef.current = 3;
        applyView(axisModeRef.current);
        animate();
      }
    );

    // Offset so that:
    // - Heading North (0 rad) => we see the stern (bow points away from camera)
    // - Heading South (pi rad) => we see the bow (bow points towards camera)
    // This is achieved by adding 180° to the previous compass-aligned mapping.
    const HEADING_OFFSET = Math.PI / 2 + Math.PI; // +90° + 180°

    function animate() {
      requestAnimationFrame(animate);
      if (liveRef.current && sensorsRef.current && modelRef.current) {
        const { roll = 0, pitch = 0 } = sensorsRef.current;
        const hRaw = sensorsRef.current.heading ?? sensorsRef.current.cog ?? 0;
        const heading = Number.isFinite(Number(hRaw)) ? Number(hRaw) : 0;
        let rx = pitch || 0;
        // Align yaw with compass (0=N, CW positive) and model forward axis
        let ry = -(heading || 0) + HEADING_OFFSET;
        let rz = -(roll || 0);
        const mode = axisModeRef.current;
        if (mode === 'x') {
          ry = 0;
          rz = 0;
        } else if (mode === 'y') {
          rx = 0;
          rz = 0;
        } else if (mode === 'z') {
          rx = 0;
          ry = 0;
        }
        modelRef.current.rotation.x = rx;
        modelRef.current.rotation.y = ry;
        modelRef.current.rotation.z = rz;
      }
      controls.update();
      renderer.render(scene, camera);
    }

    const handleResize = () => {
      renderer.setSize(mount.clientWidth, mount.clientHeight);
      camera.aspect = mount.clientWidth / mount.clientHeight;
      camera.updateProjectionMatrix();
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      mount.removeChild(renderer.domElement);
      try {
        renderer.domElement.removeEventListener('wheel', onWheel);
      } catch {}
      try {
        controls.removeEventListener('start', onControlsStart);
      } catch {}
    };
  }, []);

  // Position the camera according to the selected axis mode
  function applyView(mode) {
    const cam = cameraRef.current;
    const ctrls = controlsRef.current;
    if (!cam || !ctrls) return;
    const c = centerRef.current;
    const d = distRef.current;
    if (mode === 'y') {
      // Yaw: top-down view (from above), rotate only by heading
      cam.position.set(c.x, c.y + d, c.z);
    } else if (mode === 'z') {
      // Roll: behind view (from stern). Approximate looking along -X
      cam.position.set(c.x - d, c.y, c.z);
    } else if (mode === 'x') {
      // Pitch: horizontal side view, look from +Z
      cam.position.set(c.x, c.y, c.z + d);
    } else {
      // Default live view: in front at +Z
      cam.position.set(c.x, c.y + d * 0.2, c.z + d);
    }
    cam.lookAt(c);
    ctrls.target.copy(c);
    ctrls.update();
  }

  // Keep camera consistent with current axis mode whenever it changes
  useEffect(() => {
    applyView(axisMode);
  }, [axisMode]);

  const btnStyle = (extra = {}) => ({
    position: 'absolute',
    bottom: 10,
    padding: '6px 10px',
    background: '#222',
    color: '#fff',
    border: '1px solid #444',
    cursor: 'pointer',
    ...extra,
  });

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }} ref={mountRef}>
      <button
        style={btnStyle({ left: 10, opacity: live && axisMode === 'all' ? 0.7 : 1 })}
        onClick={() => {
          setAxisMode('all');
          setLive(true);
        }}
        disabled={live && axisMode === 'all'}
        title="Volver a modo en vivo"
      >
        Live
      </button>
      <button
        style={btnStyle({ left: 70, opacity: axisMode === 'x' ? 1 : 0.85 })}
        onClick={() => {
          setLive(true);
          setAxisMode('x'); // Pitch view
        }}
        disabled={axisMode === 'x'}
        title="Ver solo Pitch (eje X)"
      >
        X
      </button>
      <button
        style={btnStyle({ left: 110, opacity: axisMode === 'y' ? 1 : 0.85 })}
        onClick={() => {
          setLive(true);
          setAxisMode('y'); // Yaw view (top-down)
        }}
        disabled={axisMode === 'y'}
        title="Ver solo Yaw (eje Y)"
      >
        Y
      </button>
      <button
        style={btnStyle({ left: 150, opacity: axisMode === 'z' ? 1 : 0.85 })}
        onClick={() => {
          setLive(true);
          setAxisMode('z'); // Roll view (behind)
        }}
        disabled={axisMode === 'z'}
        title="Ver solo Roll (eje Z)"
      >
        Z
      </button>
    </div>
  );
}
