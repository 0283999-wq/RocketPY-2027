/* Beyond UP RocketPy - 3D flight playback + live Monte Carlo viewer
 * (2026-09-27 review item 7, Mission Control redesign). Built on
 * vendored three.js (three.min.js, MIT license, next to this file) -
 * no CDN, works fully offline. Plain global functions (BUP.playback.*,
 * BUP.livemc.*) called from Python via ui.run_javascript(); all
 * per-frame animation happens client-side (the Python backend only
 * sends the full dataset once, then play/pause/speed/seek commands),
 * so a running app never has to round-trip every animation frame over
 * the websocket.
 *
 * Coordinate convention: RocketPy's own flight frame is x=East,
 * y=North, z=up (AGL, elevation already subtracted by the caller).
 * three.js is Y-up, so every point is mapped (x, z, y) -> (three X,
 * three Y, three Z) once, here, in one place.
 */
window.BUP = window.BUP || {};
BUP.playback = {};
BUP.livemc = {};

function _bupMakeView(parent, width, height, label) {
  const box = document.createElement("div");
  box.style.position = "relative";
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  canvas.style.background = "#14100d";
  canvas.style.borderRadius = "8px";
  canvas.style.maxWidth = "100%";
  box.appendChild(canvas);
  const tag = document.createElement("div");
  tag.textContent = label;
  tag.style.position = "absolute";
  tag.style.top = "4px";
  tag.style.left = "8px";
  tag.style.color = "#B79357";
  tag.style.fontSize = "11px";
  tag.style.fontFamily = "sans-serif";
  tag.style.pointerEvents = "none";
  box.appendChild(tag);
  parent.appendChild(box);
  return canvas;
}

function _bupToThree(f) {
  return new THREE.Vector3(f.x, f.z, f.y);
}

BUP.playback.create = function (containerId, data) {
  const container = document.getElementById(containerId);
  if (!container || !data || !data.frames || !data.frames.length) return null;
  container.innerHTML = "";

  const wrap = document.createElement("div");
  wrap.style.display = "flex";
  wrap.style.flexDirection = "column";
  wrap.style.gap = "10px";
  container.appendChild(wrap);

  const mainRow = document.createElement("div");
  mainRow.style.display = "flex";
  mainRow.style.gap = "8px";
  mainRow.style.flexWrap = "wrap";
  wrap.appendChild(mainRow);

  const perspCanvas = _bupMakeView(mainRow, 480, 380, "3D (drag to rotate, scroll to zoom)");
  const xzCanvas = _bupMakeView(mainRow, 220, 190, "Side view (X-Z)");
  const yzCanvas = _bupMakeView(mainRow, 220, 190, "Side view (Y-Z)");
  const xyCanvas = _bupMakeView(mainRow, 220, 190, "Top view (X-Y)");

  const readout = document.createElement("div");
  readout.style.display = "grid";
  readout.style.gridTemplateColumns = "repeat(auto-fit, minmax(110px, 1fr))";
  readout.style.gap = "6px";
  readout.style.fontFamily = "sans-serif";
  wrap.appendChild(readout);
  const fieldLabels = { t: "Time (s)", alt: "Altitude AGL (m)", speed: "Speed (m/s)", mach: "Mach", accel: "Accel (m/s²)" };
  const readoutEls = {};
  Object.keys(fieldLabels).forEach((f) => {
    const card = document.createElement("div");
    card.style.background = "#F2EFEA";
    card.style.borderRadius = "6px";
    card.style.padding = "6px 10px";
    const l = document.createElement("div");
    l.textContent = fieldLabels[f];
    l.style.fontSize = "10px";
    l.style.color = "#6b6259";
    const v = document.createElement("div");
    v.textContent = "-";
    v.style.fontSize = "18px";
    v.style.fontWeight = "700";
    v.style.color = "#211A16";
    card.appendChild(l);
    card.appendChild(v);
    readout.appendChild(card);
    readoutEls[f] = v;
  });

  const controls = document.createElement("div");
  controls.style.display = "flex";
  controls.style.alignItems = "center";
  controls.style.gap = "10px";
  controls.style.flexWrap = "wrap";
  wrap.appendChild(controls);

  const playBtn = document.createElement("button");
  playBtn.textContent = "Play";
  playBtn.style.cssText = "background:#8A1538;color:white;border:none;border-radius:4px;padding:6px 16px;cursor:pointer;font-family:sans-serif;font-weight:600";
  controls.appendChild(playBtn);

  const speedSel = document.createElement("select");
  speedSel.style.cssText = "border-radius:4px;padding:5px;font-family:sans-serif";
  [0.25, 0.5, 1, 2, 4].forEach((v) => {
    const o = document.createElement("option");
    o.value = v;
    o.textContent = v + "x";
    if (v === 1) o.selected = true;
    speedSel.appendChild(o);
  });
  controls.appendChild(speedSel);

  const slider = document.createElement("input");
  slider.type = "range";
  slider.min = 0;
  slider.max = data.frames.length - 1;
  slider.value = 0;
  slider.style.flex = "1";
  slider.style.minWidth = "150px";
  controls.appendChild(slider);

  const eventLabel = document.createElement("div");
  eventLabel.style.cssText = "font-size:12px;color:#8A1538;font-family:sans-serif;min-width:160px";
  controls.appendChild(eventLabel);

  const bounds = data.bounds;
  const cx = (bounds.x_min + bounds.x_max) / 2;
  const cy = (bounds.y_min + bounds.y_max) / 2;
  const span = Math.max(20, bounds.x_max - bounds.x_min, bounds.y_max - bounds.y_min, bounds.z_max - bounds.z_min) * 1.15;
  const midZ = bounds.z_max / 2;

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x14100d);
  const grid = new THREE.GridHelper(span * 2, 20, 0x8a1538, 0x3a322c);
  grid.position.set(cx, 0, cy);
  scene.add(grid);

  const fullPoints = data.frames.map(_bupToThree);
  const fullLine = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(fullPoints),
    new THREE.LineBasicMaterial({ color: 0x6b6259, transparent: true, opacity: 0.5 })
  );
  scene.add(fullLine);

  const traveledGeom = new THREE.BufferGeometry().setFromPoints([fullPoints[0]]);
  const traveledLine = new THREE.Line(traveledGeom, new THREE.LineBasicMaterial({ color: 0xb79357 }));
  scene.add(traveledLine);

  const rocketMesh = new THREE.Mesh(
    new THREE.ConeGeometry(Math.max(span * 0.012, 0.3), Math.max(span * 0.05, 1.2), 8),
    new THREE.MeshBasicMaterial({ color: 0xffffff })
  );
  scene.add(rocketMesh);

  (data.events || []).forEach((ev) => {
    const marker = new THREE.Mesh(
      new THREE.SphereGeometry(Math.max(span * 0.01, 0.25), 8, 8),
      new THREE.MeshBasicMaterial({ color: 0x8a1538 })
    );
    marker.position.copy(_bupToThree(ev));
    scene.add(marker);
  });

  const perspCam = new THREE.PerspectiveCamera(45, perspCanvas.width / perspCanvas.height, 0.1, span * 30);
  let azimuth = Math.PI / 4;
  let camElevation = Math.PI / 6;
  let dist = span * 1.6;
  function updatePerspCam() {
    perspCam.position.set(
      cx + dist * Math.cos(camElevation) * Math.sin(azimuth),
      dist * Math.sin(camElevation),
      cy + dist * Math.cos(camElevation) * Math.cos(azimuth)
    );
    perspCam.lookAt(cx, midZ, cy);
  }
  updatePerspCam();

  const xzCam = new THREE.OrthographicCamera(-span, span, span, -span, 0.1, span * 30);
  xzCam.position.set(cx, midZ, cy + span * 8);
  xzCam.lookAt(cx, midZ, cy);

  const yzCam = new THREE.OrthographicCamera(-span, span, span, -span, 0.1, span * 30);
  yzCam.position.set(cx + span * 8, midZ, cy);
  yzCam.lookAt(cx, midZ, cy);

  const xyCam = new THREE.OrthographicCamera(-span, span, span, -span, 0.1, span * 30);
  xyCam.position.set(cx, bounds.z_max + span * 8, cy);
  xyCam.up.set(0, 0, -1);
  xyCam.lookAt(cx, 0, cy);

  const renderers = [
    [perspCanvas, perspCam],
    [xzCanvas, xzCam],
    [yzCanvas, yzCam],
    [xyCanvas, xyCam],
  ].map(([canvas, cam]) => {
    const r = new THREE.WebGLRenderer({ canvas: canvas, antialias: true });
    r.setSize(canvas.width, canvas.height, false);
    return [r, cam];
  });

  let dragging = false;
  let lastX = 0;
  let lastY = 0;
  perspCanvas.addEventListener("mousedown", (e) => {
    dragging = true;
    lastX = e.clientX;
    lastY = e.clientY;
  });
  window.addEventListener("mouseup", () => {
    dragging = false;
  });
  window.addEventListener("mousemove", (e) => {
    if (!dragging) return;
    azimuth -= (e.clientX - lastX) * 0.008;
    camElevation = Math.max(0.05, Math.min(Math.PI / 2 - 0.05, camElevation + (e.clientY - lastY) * 0.008));
    lastX = e.clientX;
    lastY = e.clientY;
    updatePerspCam();
  });
  perspCanvas.addEventListener(
    "wheel",
    (e) => {
      e.preventDefault();
      dist = Math.max(span * 0.2, Math.min(span * 8, dist * (1 + e.deltaY * 0.001)));
      updatePerspCam();
    },
    { passive: false }
  );

  const anim = { frameIndexF: 0, playing: false, speed: 1, lastTs: null };

  function renderFrame() {
    const idx = Math.round(anim.frameIndexF);
    const f = data.frames[idx];
    const pos = _bupToThree(f);
    rocketMesh.position.copy(pos);
    traveledGeom.setFromPoints(fullPoints.slice(0, idx + 1));

    readoutEls.t.textContent = f.t.toFixed(1);
    readoutEls.alt.textContent = f.z.toFixed(1);
    readoutEls.speed.textContent = f.speed.toFixed(1);
    readoutEls.mach.textContent = f.mach.toFixed(3);
    readoutEls.accel.textContent = f.accel.toFixed(1);
    slider.value = idx;

    let nearest = null;
    (data.events || []).forEach((ev) => {
      if (ev.t <= f.t) nearest = ev;
    });
    eventLabel.textContent = nearest ? "Last event: " + nearest.name + " @ " + nearest.t.toFixed(1) + "s" : "";

    renderers.forEach(([r, cam]) => r.render(scene, cam));
  }
  renderFrame();

  function tick(ts) {
    if (anim.playing) {
      if (anim.lastTs == null) anim.lastTs = ts;
      const dt = (ts - anim.lastTs) / 1000;
      anim.lastTs = ts;
      const totalT = data.frames[data.frames.length - 1].t - data.frames[0].t;
      const frameDt = totalT / Math.max(1, data.frames.length - 1);
      anim.frameIndexF = Math.min(data.frames.length - 1, anim.frameIndexF + (dt * anim.speed) / Math.max(frameDt, 1e-6));
      if (anim.frameIndexF >= data.frames.length - 1) {
        anim.frameIndexF = data.frames.length - 1;
        anim.playing = false;
        playBtn.textContent = "Play";
      }
      renderFrame();
    } else {
      anim.lastTs = null;
    }
    viewer._raf = requestAnimationFrame(tick);
  }

  playBtn.onclick = () => {
    anim.playing = !anim.playing;
    playBtn.textContent = anim.playing ? "Pause" : "Play";
  };
  speedSel.onchange = () => {
    anim.speed = parseFloat(speedSel.value);
  };
  slider.oninput = () => {
    anim.frameIndexF = parseFloat(slider.value);
    anim.playing = false;
    playBtn.textContent = "Play";
    renderFrame();
  };

  const viewer = {
    play: () => {
      anim.playing = true;
    },
    pause: () => {
      anim.playing = false;
      playBtn.textContent = "Play";
    },
    setFrame: (i) => {
      anim.frameIndexF = i;
      renderFrame();
    },
    destroy: () => {
      if (viewer._raf) cancelAnimationFrame(viewer._raf);
    },
    _raf: null,
  };
  viewer._raf = requestAnimationFrame(tick);
  window.BUP._viewers = window.BUP._viewers || {};
  if (window.BUP._viewers[containerId]) window.BUP._viewers[containerId].destroy();
  window.BUP._viewers[containerId] = viewer;
  return viewer;
};

/* Live Monte Carlo view: a ground grid that fills in with one faint
 * trajectory line per completed sample and a growing landing-point
 * cloud, called incrementally from Python as each sample finishes
 * (2026-09-27 review item 7's "each finished trajectory appears in 3D
 * as it completes"). setEllipses() draws the final 1/2/3-sigma
 * ellipses once the whole batch is done, reusing the same numbers the
 * static matplotlib plot uses (monte_carlo.landing_ellipses) - not a
 * separate, potentially-disagreeing computation.
 */
BUP.livemc.create = function (containerId, options) {
  const container = document.getElementById(containerId);
  if (!container) return null;
  container.innerHTML = "";
  options = options || {};

  const wrap = document.createElement("div");
  wrap.style.display = "flex";
  wrap.style.flexDirection = "column";
  wrap.style.gap = "6px";
  container.appendChild(wrap);

  const statusLine = document.createElement("div");
  statusLine.style.cssText = "font-family:sans-serif;font-size:12px;color:#B79357";
  statusLine.textContent = "Waiting for the first completed trajectory...";
  wrap.appendChild(statusLine);

  const canvas = _bupMakeView(wrap, 520, 420, "Live Monte Carlo (fills in as each trajectory completes)");

  const span = Math.max(20, options.span || 200);
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x14100d);
  const grid = new THREE.GridHelper(span * 2, 20, 0x8a1538, 0x3a322c);
  scene.add(grid);

  const cam = new THREE.PerspectiveCamera(45, canvas.width / canvas.height, 0.1, span * 30);
  let azimuth = Math.PI / 4;
  let camElevation = Math.PI / 5;
  let dist = span * 1.4;
  function updateCam() {
    cam.position.set(dist * Math.cos(camElevation) * Math.sin(azimuth), dist * Math.sin(camElevation), dist * Math.cos(camElevation) * Math.cos(azimuth));
    cam.lookAt(0, 0, 0);
  }
  updateCam();
  const renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true });
  renderer.setSize(canvas.width, canvas.height, false);

  let dragging = false,
    lastX = 0,
    lastY = 0;
  canvas.addEventListener("mousedown", (e) => {
    dragging = true;
    lastX = e.clientX;
    lastY = e.clientY;
  });
  window.addEventListener("mouseup", () => {
    dragging = false;
  });
  window.addEventListener("mousemove", (e) => {
    if (!dragging) return;
    azimuth -= (e.clientX - lastX) * 0.008;
    camElevation = Math.max(0.05, Math.min(Math.PI / 2 - 0.05, camElevation + (e.clientY - lastY) * 0.008));
    lastX = e.clientX;
    lastY = e.clientY;
    updateCam();
  });
  canvas.addEventListener(
    "wheel",
    (e) => {
      e.preventDefault();
      dist = Math.max(span * 0.2, Math.min(span * 8, dist * (1 + e.deltaY * 0.001)));
      updateCam();
    },
    { passive: false }
  );

  const landingPositions = [];
  const landingGeom = new THREE.BufferGeometry();
  const landingPoints = new THREE.Points(landingGeom, new THREE.PointsMaterial({ color: 0x211a16, size: Math.max(span * 0.01, 1.5) }));
  scene.add(landingPoints);

  let nCompleted = 0;

  function render() {
    renderer.render(scene, cam);
  }
  render();

  const viewer = {
    addSample: (points) => {
      if (points && points.length > 1) {
        const pts = points.map((p) => new THREE.Vector3(p[0], p[2], p[1]));
        const line = new THREE.Line(
          new THREE.BufferGeometry().setFromPoints(pts),
          new THREE.LineBasicMaterial({ color: 0xb79357, transparent: true, opacity: 0.35 })
        );
        scene.add(line);
      }
      nCompleted += 1;
      statusLine.textContent = nCompleted + " trajectory(ies) completed";
      render();
    },
    addLanding: (x, y) => {
      landingPositions.push(x, 0, y);
      landingGeom.setAttribute("position", new THREE.Float32BufferAttribute(landingPositions, 3));
      landingGeom.computeBoundingSphere();
      render();
    },
    setEllipses: (ellipses) => {
      (ellipses || []).forEach((e) => {
        const curve = new THREE.EllipseCurve(e.center_x, e.center_y, e.width / 2, e.height / 2, 0, 2 * Math.PI, false, (-e.angle_deg * Math.PI) / 180);
        const pts2 = curve.getPoints(64).map((p) => new THREE.Vector3(p.x, 0.05, p.y));
        const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts2), new THREE.LineBasicMaterial({ color: e.color || 0x8a1538 }));
        scene.add(line);
      });
      render();
    },
    destroy: () => {},
  };
  window.BUP._mcViewers = window.BUP._mcViewers || {};
  window.BUP._mcViewers[containerId] = viewer;
  return viewer;
};
