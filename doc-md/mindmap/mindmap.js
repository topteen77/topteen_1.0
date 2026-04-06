const viewport = document.getElementById("viewport");
const canvas = document.getElementById("canvas");
const mindmapEl = document.getElementById("mindmap");
const linksEl = document.getElementById("links");

const zoomInBtn = document.getElementById("zoomInBtn");
const zoomOutBtn = document.getElementById("zoomOutBtn");
const resetViewBtn = document.getElementById("resetViewBtn");

let scale = 1;
const MIN_SCALE = 0.5;
const MAX_SCALE = 1.8;
const collapsedNodes = new Set();

const nodes = [
  { id: "root", text: "Impact of Tourism on Host Country", level: "root" },

  { id: "socio", parent: "root", text: "Socio-Cultural Impacts of Tourism", level: "topic" },
  { id: "env", parent: "root", text: "Environmental Impacts of Tourism", level: "topic" },
  { id: "eco", parent: "root", text: "Economic Impacts of Tourism", level: "topic" },

  { id: "s1", parent: "socio", text: "Cultural Exchange", level: "sub" },
  { id: "s2", parent: "socio", text: "Commercialization of Culture", level: "sub" },
  { id: "s3", parent: "socio", text: "Changes in Social Structures", level: "sub" },
  { id: "s4", parent: "socio", text: "Language & Communication", level: "sub" },
  { id: "s5", parent: "socio", text: "Preservation of Heritage", level: "sub" },

  { id: "s21", parent: "s2", text: "Traditional arts sold as products", level: "leaf" },
  { id: "s22", parent: "s2", text: "Festivals adapted for visitors", level: "leaf" },
  { id: "s31", parent: "s3", text: "Lifestyle changes in local youth", level: "leaf" },

  { id: "e1", parent: "env", text: "Pollution", level: "sub" },
  { id: "e2", parent: "env", text: "Habitat Destruction", level: "sub" },
  { id: "e3", parent: "env", text: "Resource Depletion", level: "sub" },
  { id: "e4", parent: "env", text: "Conservation Efforts", level: "sub" },
  { id: "e5", parent: "env", text: "Climate Stress", level: "sub" },

  { id: "e11", parent: "e1", text: "Air pollution from transport", level: "leaf" },
  { id: "e12", parent: "e1", text: "Water pollution in beaches", level: "leaf" },
  { id: "e21", parent: "e2", text: "Construction of hotels and resorts", level: "leaf" },
  { id: "e22", parent: "e2", text: "Deforestation for tourism development", level: "leaf" },
  { id: "e23", parent: "e2", text: "Displacement of local species", level: "leaf" },
  { id: "e31", parent: "e3", text: "High freshwater consumption", level: "leaf" },
  { id: "e32", parent: "e3", text: "Energy demand in peak seasons", level: "leaf" },
  { id: "e41", parent: "e4", text: "Protected area funding", level: "leaf" },
  { id: "e51", parent: "e5", text: "Heat stress in destinations", level: "leaf" },

  { id: "ec1", parent: "eco", text: "Government Regulations", level: "sub" },
  { id: "ec2", parent: "eco", text: "Community Involvement", level: "sub" },
  { id: "ec3", parent: "eco", text: "Education & Awareness", level: "sub" },
  { id: "ec4", parent: "eco", text: "Employment Generation", level: "sub" },
  { id: "ec5", parent: "eco", text: "Infrastructure Development", level: "sub" },

  { id: "ec11", parent: "ec1", text: "Licensing and zoning policy", level: "leaf" },
  { id: "ec12", parent: "ec1", text: "Sustainable tax incentives", level: "leaf" },
  { id: "ec21", parent: "ec2", text: "Local entrepreneurship support", level: "leaf" },
  { id: "ec22", parent: "ec2", text: "Resident feedback forums", level: "leaf" },
  { id: "ec41", parent: "ec4", text: "Direct jobs in hospitality", level: "leaf" },
  { id: "ec42", parent: "ec4", text: "Indirect jobs in supply chains", level: "leaf" },
  { id: "ec51", parent: "ec5", text: "Roads and public transport", level: "leaf" },
  { id: "ec52", parent: "ec5", text: "Digital and health facilities", level: "leaf" },
];

const NODE_HEIGHT = 34;
const LEAF_VERTICAL_GAP = 16;
const BRANCH_VERTICAL_GAP = 22;
const LEFT_PADDING = 120;
const TOP_PADDING = 120;
const LEVEL_SPACING = 360;
const CANVAS_MIN_WIDTH = 2200;
const CANVAS_MIN_HEIGHT = 1200;

function getNode(id) {
  return nodes.find((item) => item.id === id);
}

function getChildren(id) {
  return nodes.filter((item) => item.parent === id);
}

function hasChildren(id) {
  return getChildren(id).length > 0;
}

function getDepth(id) {
  let depth = 0;
  let current = getNode(id);
  while (current && current.parent) {
    depth += 1;
    current = getNode(current.parent);
  }
  return depth;
}

function computeSubtreeHeight(nodeId) {
  if (collapsedNodes.has(nodeId)) return NODE_HEIGHT;
  const children = getChildren(nodeId);
  if (children.length === 0) return NODE_HEIGHT;

  let total = 0;
  children.forEach((child, index) => {
    total += computeSubtreeHeight(child.id);
    if (index < children.length - 1) {
      total += child.level === "leaf" ? LEAF_VERTICAL_GAP : BRANCH_VERTICAL_GAP;
    }
  });
  return Math.max(NODE_HEIGHT, total);
}

function assignPositions(nodeId, startY, positions) {
  const node = getNode(nodeId);
  if (!node) return startY;

  const subtreeHeight = computeSubtreeHeight(nodeId);
  const centerY = startY + subtreeHeight / 2 - NODE_HEIGHT / 2;
  const depth = getDepth(nodeId);
  const x = LEFT_PADDING + depth * LEVEL_SPACING;
  positions.set(nodeId, { x, y: centerY });

  if (collapsedNodes.has(nodeId)) return startY + subtreeHeight;

  const children = getChildren(nodeId);
  let cursor = startY;
  children.forEach((child, index) => {
    cursor = assignPositions(child.id, cursor, positions);
    if (index < children.length - 1) {
      cursor += child.level === "leaf" ? LEAF_VERTICAL_GAP : BRANCH_VERTICAL_GAP;
    }
  });

  return startY + subtreeHeight;
}

function getVisibleNodeIds(rootId) {
  const visible = [];
  function visit(nodeId) {
    visible.push(nodeId);
    if (collapsedNodes.has(nodeId)) return;
    getChildren(nodeId).forEach((child) => visit(child.id));
  }
  visit(rootId);
  return visible;
}

function drawNode(node, position) {
  const el = document.createElement("div");
  el.className = `node ${node.level}`;
  const label = document.createElement("span");
  label.className = "node-label";
  label.textContent = node.text;
  el.appendChild(label);

  if (hasChildren(node.id)) {
    const toggleBtn = document.createElement("button");
    toggleBtn.className = "node-toggle";
    toggleBtn.type = "button";
    toggleBtn.title = collapsedNodes.has(node.id) ? "Open child nodes" : "Close child nodes";
    toggleBtn.textContent = collapsedNodes.has(node.id) ? "+" : "-";
    toggleBtn.addEventListener("click", () => {
      if (collapsedNodes.has(node.id)) {
        collapsedNodes.delete(node.id);
      } else {
        collapsedNodes.add(node.id);
      }
      render();
    });
    el.appendChild(toggleBtn);
  }

  el.style.left = `${position.x}px`;
  el.style.top = `${position.y}px`;
  mindmapEl.appendChild(el);
}

function drawLink(parentPos, childPos) {
  const parentWidth = 250;
  const childInset = 8;
  const x1 = parentPos.x + parentWidth;
  const y1 = parentPos.y + 17;
  const x2 = childPos.x + childInset;
  const y2 = childPos.y + 17;
  const curve = Math.max(50, (x2 - x1) * 0.45);

  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("class", "link");
  path.setAttribute("d", `M ${x1} ${y1} C ${x1 + curve} ${y1}, ${x2 - curve} ${y2}, ${x2} ${y2}`);
  linksEl.appendChild(path);
}

function render() {
  mindmapEl.innerHTML = "";
  linksEl.innerHTML = "";

  const root = getNode("root");
  if (!root) return;

  const positions = new Map();
  assignPositions(root.id, TOP_PADDING, positions);
  const visibleIds = new Set(getVisibleNodeIds(root.id));

  nodes.forEach((node) => {
    if (!visibleIds.has(node.id)) return;
    const position = positions.get(node.id);
    if (position) drawNode(node, position);
  });

  nodes.forEach((node) => {
    if (!node.parent || !visibleIds.has(node.id) || !visibleIds.has(node.parent)) return;
    const parentPos = positions.get(node.parent);
    const childPos = positions.get(node.id);
    if (parentPos && childPos) drawLink(parentPos, childPos);
  });

  const contentHeight = computeSubtreeHeight(root.id) + TOP_PADDING * 2;
  const deepestDepth = Math.max(...nodes.map((item) => getDepth(item.id)));
  const contentWidth = LEFT_PADDING + deepestDepth * LEVEL_SPACING + 520;

  const finalWidth = Math.max(CANVAS_MIN_WIDTH, contentWidth);
  const finalHeight = Math.max(CANVAS_MIN_HEIGHT, contentHeight);

  canvas.style.width = `${finalWidth}px`;
  canvas.style.height = `${finalHeight}px`;
  mindmapEl.style.width = `${finalWidth}px`;
  mindmapEl.style.height = `${finalHeight}px`;
  linksEl.style.width = `${finalWidth}px`;
  linksEl.style.height = `${finalHeight}px`;
  linksEl.setAttribute("viewBox", `0 0 ${finalWidth} ${finalHeight}`);
}

function applyZoom() {
  canvas.style.transform = `scale(${scale})`;
}

function zoom(delta) {
  scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale + delta));
  applyZoom();
}

zoomInBtn.addEventListener("click", () => zoom(0.1));
zoomOutBtn.addEventListener("click", () => zoom(-0.1));
resetViewBtn.addEventListener("click", () => {
  scale = 1;
  applyZoom();
  viewport.scrollTo({ left: 0, top: 0, behavior: "smooth" });
});

viewport.addEventListener("wheel", (event) => {
  if (!event.ctrlKey) return;
  event.preventDefault();
  zoom(event.deltaY > 0 ? -0.05 : 0.05);
}, { passive: false });

render();
viewport.scrollTo({ left: 0, top: 0 });
