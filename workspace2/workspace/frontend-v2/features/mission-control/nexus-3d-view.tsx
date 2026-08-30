"use client";

import { useEffect, useRef } from "react";
import type { NexusSnapshot } from "./types";

export function Nexus3DView({ snapshot }: { snapshot: NexusSnapshot }) {
  const host = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let disposed = false;
    let cleanup = () => undefined;

    const init = async () => {
      const THREE = await import("three");
      let OrbitControlsClass: any = null;
      try {
        const mod = await import("three/examples/jsm/controls/OrbitControls.js");
        OrbitControlsClass = mod.OrbitControls;
      } catch {
        try {
          const mod = await import("three/addons/controls/OrbitControls.js");
          OrbitControlsClass = mod.OrbitControls;
        } catch {
          OrbitControlsClass = null;
        }
      }

      const element = host.current;
      if (!element || disposed) return;

      const width = element.clientWidth || 600;
      const height = element.clientHeight || 450;

      const scene = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(50, width / height, 0.1, 1000);
      camera.position.z = 12;

      const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
      renderer.setSize(width, height);
      element.replaceChildren(renderer.domElement);

      let orbit: any = null;
      if (OrbitControlsClass) {
        orbit = new OrbitControlsClass(camera, renderer.domElement);
        orbit.enableDamping = true;
      }

      const points = snapshot.nodes.map((_, index) => {
        const angle = (index / Math.max(snapshot.nodes.length, 1)) * Math.PI * 2;
        return new THREE.Vector3(Math.cos(angle) * 4.5, Math.sin(angle) * 3.5, (index % 3) - 1);
      });

      const material = new THREE.MeshBasicMaterial({ color: 0x86a8ff });
      points.forEach((point) => {
        const mesh = new THREE.Mesh(new THREE.SphereGeometry(0.22, 16, 16), material);
        mesh.position.copy(point);
        scene.add(mesh);
      });

      snapshot.edges.forEach((edge) => {
        const from = snapshot.nodes.findIndex((node) => node.node_id === edge.source_id);
        const to = snapshot.nodes.findIndex((node) => node.node_id === edge.target_id);
        if (from >= 0 && to >= 0) {
          scene.add(
            new THREE.Line(
              new THREE.BufferGeometry().setFromPoints([points[from], points[to]]),
              new THREE.LineBasicMaterial({ color: 0x4966a0 })
            )
          );
        }
      });

      let frame = 0;
      const render = () => {
        if (orbit) orbit.update();
        else scene.rotation.y += 0.005;
        renderer.render(scene, camera);
        frame = requestAnimationFrame(render);
      };
      render();

      const resize = () => {
        if (!element) return;
        const w = element.clientWidth || 600;
        const h = element.clientHeight || 450;
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
        renderer.setSize(w, h);
      };

      window.addEventListener("resize", resize);
      cleanup = () => {
        cancelAnimationFrame(frame);
        window.removeEventListener("resize", resize);
        if (orbit) orbit.dispose();
        renderer.dispose();
        element.replaceChildren();
      };
    };

    void init();

    return () => {
      disposed = true;
      cleanup();
    };
  }, [snapshot]);

  return <div className="nexus-3d" ref={host} aria-label="Three-dimensional Neural Nexus graph" />;
}
