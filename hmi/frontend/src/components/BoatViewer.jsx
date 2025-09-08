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
  liveRef.current = live;
  sensorsRef.current = sensors;

  useEffect(() => {
    const mount = mountRef.current;
    const scene = new THREE.Scene();
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    mount.appendChild(renderer.domElement);

    const camera = new THREE.PerspectiveCamera(45, mount.clientWidth / mount.clientHeight, 0.1, 1000);
    camera.position.set(0, 2, 5);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.addEventListener('start', () => setLive(false));

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
        modelRef.current.rotateY(Math.PI / 2);

        const box = new THREE.Box3().setFromObject(gltf.scene);
        const center = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());
        const maxDim = Math.max(size.x, size.y, size.z);
        const fov = (camera.fov * Math.PI) / 180;
        let cameraZ = Math.abs(maxDim / 2 / Math.tan(fov / 2));
        cameraZ *= 1.5;
        camera.position.set(center.x, center.y, cameraZ);
        controls.target.copy(center);
        controls.update();
        animate();
      },
      undefined,
      () => {
        const geometry = new THREE.BoxGeometry();
        const material = new THREE.MeshNormalMaterial();
        const cube = new THREE.Mesh(geometry, material);
        modelRef.current = cube;
        scene.add(cube);
        animate();
      }
    );

    function animate() {
      requestAnimationFrame(animate);
      if (liveRef.current && sensorsRef.current && modelRef.current) {
        const { roll = 0, pitch = 0, heading = 0 } = sensorsRef.current;
        modelRef.current.rotation.x = pitch || 0;
        modelRef.current.rotation.y = -(heading || 0);
        modelRef.current.rotation.z = -(roll || 0);
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
    };
  }, []);

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }} ref={mountRef}>
      <button
        style={{ position: 'absolute', bottom: 10, left: 10 }}
        onClick={() => setLive(true)}
        disabled={live}
      >
        Live
      </button>
    </div>
  );
}
