import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
// The boat model is expected at `hmi/frontend/public/boat.glb` but is not tracked in git.
// The file should be supplied separately and served from the frontend's public directory.
const boatUrl = '/boat.glb';

export default function BoatViewer({ sensors }) {
  const mountRef = useRef(null);
  const [live, setLive] = useState(false);

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

    const light = new THREE.DirectionalLight(0xffffff, 1);
    light.position.set(5, 10, 7.5);
    scene.add(light);

    const loader = new GLTFLoader();
    loader.load(boatUrl, (gltf) => {
      scene.add(gltf.scene);
      animate();
    }, undefined, () => {
      // fallback cube
      const geometry = new THREE.BoxGeometry();
      const material = new THREE.MeshNormalMaterial();
      const cube = new THREE.Mesh(geometry, material);
      scene.add(cube);
      animate();
    });

    function animate() {
      requestAnimationFrame(animate);
      if (live && sensors) {
        const { roll = 0, pitch = 0, heading = 0 } = sensors;
        scene.rotation.set(pitch || 0, heading || 0, roll || 0);
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
  }, [live, sensors]);

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }} ref={mountRef}>
      <button
        style={{ position: 'absolute', bottom: 10, left: 10 }}
        onClick={() => setLive(!live)}
      >
        {live ? 'Stop' : 'Live'}
      </button>
    </div>
  );
}
