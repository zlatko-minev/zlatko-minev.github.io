// ---------- the chip stack: from a package to a logical qubit ----------
// An isometric drawing of the layers of a superconducting quantum processor. Scrolling
// pulls the layers apart (package, qubit chip, couplers and readout, surface code,
// logical qubit) and labels them; while the drawing is on screen, stabilizer checks on
// the surface-code layer light up now and then, like detection events, and the logical
// qubit glows softly. Reduced-motion users get the exploded view, still.
(() => {
  const svg = document.getElementById("chip-stack");
  if (!svg) return;
  const NS = "http://www.w3.org/2000/svg", k = 18, C = Math.cos(Math.PI / 6), ox = 190, oy = 340, N = 6;
  const P = (x, y, z = 0) => [ox + (x - y) * C * k, oy + (x + y) * 0.5 * k - z * k];
  const pts = (arr) => arr.map((p) => P(...p).map((v) => v.toFixed(1)).join(",")).join(" ");
  const el = (tag, attrs, parent = svg) => {
    const e = document.createElementNS(NS, tag);
    for (const [a, v] of Object.entries(attrs)) e.setAttribute(a, v);
    parent.appendChild(e);
    return e;
  };
  const plane = (g, x0, x1, y0, y1, cls, z = 0) =>
    el("polygon", { class: cls, points: pts([[x0, y0, z], [x1, y0, z], [x1, y1, z], [x0, y1, z]]) }, g);
  const slab = (g, x0, x1, y0, y1, h, cls) => {
    el("polygon", { class: cls + " f-l", points: pts([[x0, y1, -h], [x1, y1, -h], [x1, y1, 0], [x0, y1, 0]]) }, g);
    el("polygon", { class: cls + " f-r", points: pts([[x1, y0, -h], [x1, y1, -h], [x1, y1, 0], [x1, y0, 0]]) }, g);
    return plane(g, x0, x1, y0, y1, cls + " f-t");
  };
  svg.innerHTML = "";
  const layers = [];
  const layer = (name, rest, open) => {
    const g = el("g", { class: "layer" });
    const [lx, ly] = P(N + 0.4, 0, 0);
    const label = el("text", { class: "lbl", x: (lx + 18).toFixed(1), y: (ly - 4).toFixed(1) }, g);
    label.textContent = name;
    el("line", { class: "lead", x1: (lx + 2).toFixed(1), y1: (ly - 8).toFixed(1), x2: (lx + 14).toFixed(1), y2: (ly - 8).toFixed(1) }, g);
    layers.push({ g, label, rest, open });
    return g;
  };
  const q = (i) => 0.75 + i * 1.125;   // qubit centers on a 5 × 5 grid

  // 1. package
  const pkg = layer("Package and wiring", 0, 0);
  slab(pkg, -0.4, N + 0.4, -0.4, N + 0.4, 0.7, "pkg");
  for (let i = 0; i < 7; i++) el("polygon", { class: "pin", points: pts([[i * 1.0 - 0.05, N + 0.4, -0.25], [i * 1.0 + 0.35, N + 0.4, -0.25], [i * 1.0 + 0.35, N + 0.4, -0.45], [i * 1.0 - 0.05, N + 0.4, -0.45]]) }, pkg);

  // 2. qubit chip: 25 transmons as small crosses
  const chip = layer("Qubit chip", 0.25, 2.9);
  slab(chip, 0, N, 0, N, 0.18, "sub");
  for (let i = 0; i < 5; i++) for (let j = 0; j < 5; j++) {
    const x = q(i), y = q(j), a = 0.28, b = 0.08;
    el("polygon", { class: "qb", points: pts([[x - a, y - b], [x + a, y - b], [x + a, y + b], [x - a, y + b]]) }, chip);
    el("polygon", { class: "qb", points: pts([[x - b, y - a], [x + b, y - a], [x + b, y + a], [x - b, y + a]]) }, chip);
  }

  // 3. couplers and readout
  const cpl = layer("Couplers and readout", 0.4, 5.8);
  plane(cpl, 0, N, 0, N, "glass");
  for (let i = 0; i < 5; i++) for (let j = 0; j < 5; j++) {
    if (i < 4) el("polyline", { class: "cpl", points: pts([[q(i) + 0.3, q(j)], [q(i + 1) - 0.3, q(j)]]) }, cpl);
    if (j < 4) el("polyline", { class: "cpl", points: pts([[q(i), q(j) + 0.3], [q(i), q(j + 1) - 0.3]]) }, cpl);
  }
  const mz = [];
  for (let s = 0; s < 9; s++) mz.push([N - 0.25 - (s % 2) * 0.3, 0.3 + s * 0.6]);
  el("polyline", { class: "rdo", points: pts(mz) }, cpl);

  // 4. surface code: plaquettes between the qubits, X and Z in a checkerboard
  const code = layer("Surface code", 0.55, 8.7);
  plane(code, 0, N, 0, N, "glass");
  const checks = [];
  for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++)
    checks.push(plane(code, q(i), q(i + 1), q(j), q(j + 1), (i + j) % 2 ? "chk x" : "chk z"));
  for (let i = 0; i < 5; i++) for (let j = 0; j < 5; j++) {
    const [cx, cy] = P(q(i), q(j));
    el("circle", { class: "dq", cx: cx.toFixed(1), cy: cy.toFixed(1), r: 2.4 }, code);
  }

  // 5. one logical qubit
  const lq = layer("Logical qubit", 0.7, 11.6);
  const glow = plane(lq, q(0) - 0.35, q(4) + 0.35, q(0) - 0.35, q(4) + 0.35, "logical");
  const [tx, ty] = P(N / 2, N / 2);
  const psi = el("text", { class: "psi", x: tx.toFixed(1), y: (ty + 5).toFixed(1) }, lq);
  psi.textContent = "|ψ⟩";

  const motionQuery = matchMedia("(prefers-reduced-motion: reduce)");
  let still = motionQuery.matches, userPaused = false;
  const toggle = document.querySelector("[data-chip-toggle]");
  let spread = still ? 1 : 0, clock = 0, prev = performance.now(), running = false, visible = true, lastFlash = 0;
  const target = () => {
    if (still) return 1;
    const r = svg.getBoundingClientRect(), h = innerHeight || 800;
    return Math.min(1, Math.max(0, (h - r.top) / (h + r.height) * 2.4 - 0.35));
  };
  const draw = () => {
    for (const L of layers) {
      const z = L.rest + (L.open - L.rest) * spread;
      L.g.setAttribute("transform", `translate(0 ${(-z * k).toFixed(1)})`);
      L.label.parentNode.querySelector(".lead").style.opacity = L.label.style.opacity = Math.max(0, spread * 1.4 - 0.3).toFixed(2);
    }
    glow.style.opacity = (0.55 + 0.2 * Math.sin(clock / 900)).toFixed(2);
  };
  const frame = (now) => {
    if (!visible || document.hidden || still || userPaused) { running = false; return; }
    clock += Math.min(100, now - prev); prev = now;
    spread += (target() - spread) * 0.12;          // ease toward the scroll position
    if (clock - lastFlash > 420) {                  // a detection event now and then
      lastFlash = clock;
      const c = checks[Math.floor(Math.random() * checks.length)];
      c.classList.add("hit");
      setTimeout(() => c.classList.remove("hit"), 650);
    }
    draw();
    requestAnimationFrame(frame);
  };
  const kick = () => { if (!running && visible && !still && !userPaused && !document.hidden) { running = true; prev = performance.now(); requestAnimationFrame(frame); } };
  if ("IntersectionObserver" in window) new IntersectionObserver(([e]) => { visible = e.isIntersecting; kick(); }).observe(svg);
  document.addEventListener("visibilitychange", kick);
  const updateMotion = () => {
    still = motionQuery.matches;
    if (toggle) {
      toggle.hidden = still;
      toggle.textContent = userPaused ? 'Play diagram' : 'Pause diagram';
      toggle.setAttribute('aria-pressed', String(userPaused));
    }
    if (still || userPaused) {
      spread = 1; clock = 0;
      checks.forEach(check => check.classList.remove('hit'));
      draw();
    }
    kick();
  };
  toggle?.addEventListener('click', () => { userPaused = !userPaused; updateMotion(); });
  motionQuery.addEventListener('change', updateMotion);
  draw();
  updateMotion();
})();
