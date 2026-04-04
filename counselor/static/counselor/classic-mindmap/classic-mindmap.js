/**
 * Classic mindmap: horizontal (original doc-md style) or vertical (top-down).
 * Mount: CounselorClassicMindmap.mount(container, { nodes, layout, initialExpandDepth }).
 * initialExpandDepth (default 1): show root + direct children only; deeper branches start collapsed (toggle +/−).
 */
(function (global) {
  "use strict";

  var NODE_HEIGHT = 56;
  var NODE_WIDTH = 250;
  var LEAF_VERTICAL_GAP = 16;
  var BRANCH_VERTICAL_GAP = 22;
  var LEAF_HORIZONTAL_GAP = 16;
  var BRANCH_HORIZONTAL_GAP = 22;
  var LEFT_PADDING = 120;
  var TOP_PADDING = 120;
  var LEVEL_SPACING = 360;
  var CANVAS_MIN_WIDTH = 2200;
  var CANVAS_MIN_HEIGHT = 1200;

  function mount(container, options) {
    var nodes = options && options.nodes;
    var layout = (options && options.layout) || "horizontal";
    var isVertical = layout === "vertical";
    var fillContainer = options && options.fillContainer;

    if (!container || !nodes || !nodes.length) {
      return {
        destroy: function () {},
        zoomIn: function () {},
        zoomOut: function () {},
        reset: function () {},
        expandAll: function () {},
        collapseAll: function () {},
      };
    }

    var scale = 1;
    var MIN_SCALE = 0.5;
    var MAX_SCALE = 1.8;
    var collapsedNodes = new Set();
    var initialExpandDepth =
      options && typeof options.initialExpandDepth === "number" ? options.initialExpandDepth : 1;

    function applyInitialCollapse() {
      collapsedNodes.clear();
      nodes.forEach(function (n) {
        if (hasChildren(n.id) && getDepth(n.id) >= initialExpandDepth) {
          collapsedNodes.add(n.id);
        }
      });
    }

    var wrap = document.createElement("div");
    wrap.className =
      "counselor-classic-mm w-100" +
      (isVertical ? " counselor-classic-mm--vertical" : "") +
      (fillContainer ? " counselor-classic-mm--fill-host" : "");
    wrap.innerHTML =
      '<div class="cc-viewport" data-cc-viewport>' +
      '<div class="cc-canvas" data-cc-canvas>' +
      '<svg class="cc-links" aria-hidden="true" data-cc-links></svg>' +
      '<div class="cc-mindmap" data-cc-mindmap role="application" aria-label="Mind map"></div>' +
      "</div></div>";
    container.innerHTML = "";
    container.appendChild(wrap);

    var viewport = wrap.querySelector("[data-cc-viewport]");
    var canvas = wrap.querySelector("[data-cc-canvas]");
    var mindmapEl = wrap.querySelector("[data-cc-mindmap]");
    var linksEl = wrap.querySelector("[data-cc-links]");

    function getNode(id) {
      return nodes.find(function (item) {
        return item.id === id;
      });
    }

    function getChildren(id) {
      return nodes.filter(function (item) {
        return item.parent === id;
      });
    }

    function hasChildren(id) {
      return getChildren(id).length > 0;
    }

    function getDepth(id) {
      var depth = 0;
      var current = getNode(id);
      while (current && current.parent) {
        depth += 1;
        current = getNode(current.parent);
      }
      return depth;
    }

    /* ---------- Horizontal layout (original) ---------- */
    function computeSubtreeHeight(nodeId) {
      if (collapsedNodes.has(nodeId)) return NODE_HEIGHT;
      var children = getChildren(nodeId);
      if (children.length === 0) return NODE_HEIGHT;

      var total = 0;
      children.forEach(function (child, index) {
        total += computeSubtreeHeight(child.id);
        if (index < children.length - 1) {
          total += child.level === "leaf" ? LEAF_VERTICAL_GAP : BRANCH_VERTICAL_GAP;
        }
      });
      return Math.max(NODE_HEIGHT, total);
    }

    function assignPositionsHorizontal(nodeId, startY, positions) {
      var node = getNode(nodeId);
      if (!node) return startY;

      var subtreeHeight = computeSubtreeHeight(nodeId);
      var centerY = startY + subtreeHeight / 2 - NODE_HEIGHT / 2;
      var depth = getDepth(nodeId);
      var x = LEFT_PADDING + depth * LEVEL_SPACING;
      positions.set(nodeId, { x: x, y: centerY });

      if (collapsedNodes.has(nodeId)) return startY + subtreeHeight;

      var children = getChildren(nodeId);
      var cursor = startY;
      children.forEach(function (child, index) {
        cursor = assignPositionsHorizontal(child.id, cursor, positions);
        if (index < children.length - 1) {
          cursor += child.level === "leaf" ? LEAF_VERTICAL_GAP : BRANCH_VERTICAL_GAP;
        }
      });

      return startY + subtreeHeight;
    }

    /* ---------- Vertical layout (top-down, siblings spread on X) ---------- */
    function computeSubtreeWidth(nodeId) {
      if (collapsedNodes.has(nodeId)) return NODE_WIDTH;
      var children = getChildren(nodeId);
      if (children.length === 0) return NODE_WIDTH;

      var total = 0;
      children.forEach(function (child, index) {
        total += computeSubtreeWidth(child.id);
        if (index < children.length - 1) {
          total += child.level === "leaf" ? LEAF_HORIZONTAL_GAP : BRANCH_HORIZONTAL_GAP;
        }
      });
      return Math.max(NODE_WIDTH, total);
    }

    function assignPositionsVertical(nodeId, startX, positions) {
      var node = getNode(nodeId);
      if (!node) return startX;

      var subtreeWidth = computeSubtreeWidth(nodeId);
      var half = NODE_WIDTH / 2;
      var centerX = startX + subtreeWidth / 2 - half;
      var depth = getDepth(nodeId);
      var y = TOP_PADDING + depth * LEVEL_SPACING;
      positions.set(nodeId, { x: centerX, y: y });

      if (collapsedNodes.has(nodeId)) return startX + subtreeWidth;

      var children = getChildren(nodeId);
      var cursor = startX;
      children.forEach(function (child, index) {
        cursor = assignPositionsVertical(child.id, cursor, positions);
        if (index < children.length - 1) {
          cursor += child.level === "leaf" ? LEAF_HORIZONTAL_GAP : BRANCH_HORIZONTAL_GAP;
        }
      });

      return startX + subtreeWidth;
    }

    function getVisibleNodeIds(rootId) {
      var visible = [];
      function visit(nodeId) {
        visible.push(nodeId);
        if (collapsedNodes.has(nodeId)) return;
        getChildren(nodeId).forEach(function (child) {
          visit(child.id);
        });
      }
      visit(rootId);
      return visible;
    }

    function levelClass(level) {
      if (level === "root") return "cc-root";
      if (level === "topic") return "cc-topic";
      if (level === "sub") return "cc-sub";
      return "cc-leaf";
    }

    function drawNode(node, position) {
      var el = document.createElement("div");
      el.className = "cc-node " + levelClass(node.level);
      var label = document.createElement("span");
      label.className = "cc-node-label";
      label.textContent = node.text || "—";
      el.appendChild(label);

      if (hasChildren(node.id)) {
        var toggleBtn = document.createElement("button");
        toggleBtn.className = "cc-node-toggle";
        toggleBtn.type = "button";
        toggleBtn.title = collapsedNodes.has(node.id) ? "Open child nodes" : "Close child nodes";
        toggleBtn.textContent = collapsedNodes.has(node.id) ? "+" : "−";
        toggleBtn.addEventListener("click", function (e) {
          e.stopPropagation();
          if (collapsedNodes.has(node.id)) {
            collapsedNodes.delete(node.id);
          } else {
            collapsedNodes.add(node.id);
          }
          render();
        });
        el.appendChild(toggleBtn);
      }

      el.style.left = position.x + "px";
      el.style.top = position.y + "px";
      mindmapEl.appendChild(el);
    }

    function drawLinkHorizontal(parentPos, childPos) {
      var parentWidth = NODE_WIDTH;
      var childInset = 8;
      var midY = NODE_HEIGHT / 2;
      var x1 = parentPos.x + parentWidth;
      var y1 = parentPos.y + midY;
      var x2 = childPos.x + childInset;
      var y2 = childPos.y + midY;
      var curve = Math.max(50, (x2 - x1) * 0.45);

      var path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("class", "cc-link");
      path.setAttribute(
        "d",
        "M " + x1 + " " + y1 + " C " + (x1 + curve) + " " + y1 + ", " + (x2 - curve) + " " + y2 + ", " + x2 + " " + y2
      );
      linksEl.appendChild(path);
    }

    function drawLinkVertical(parentPos, childPos) {
      var cx = NODE_WIDTH / 2;
      var x1 = parentPos.x + cx;
      var y1 = parentPos.y + NODE_HEIGHT;
      var x2 = childPos.x + cx;
      var y2 = childPos.y;
      var dy = y2 - y1;
      var curve = Math.max(36, Math.abs(dy) * 0.35);

      var path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("class", "cc-link");
      path.setAttribute(
        "d",
        "M " +
          x1 +
          " " +
          y1 +
          " C " +
          x1 +
          " " +
          (y1 + curve) +
          ", " +
          x2 +
          " " +
          (y2 - curve) +
          ", " +
          x2 +
          " " +
          y2
      );
      linksEl.appendChild(path);
    }

    function render() {
      mindmapEl.innerHTML = "";
      linksEl.innerHTML = "";

      var root = getNode("root");
      if (!root) return;

      var positions = new Map();
      if (isVertical) {
        assignPositionsVertical(root.id, LEFT_PADDING, positions);
      } else {
        assignPositionsHorizontal(root.id, TOP_PADDING, positions);
      }

      var visibleIds = new Set(getVisibleNodeIds(root.id));

      nodes.forEach(function (node) {
        if (!visibleIds.has(node.id)) return;
        var position = positions.get(node.id);
        if (position) drawNode(node, position);
      });

      nodes.forEach(function (node) {
        if (!node.parent || !visibleIds.has(node.id) || !visibleIds.has(node.parent)) return;
        var parentPos = positions.get(node.parent);
        var childPos = positions.get(node.id);
        if (parentPos && childPos) {
          if (isVertical) drawLinkVertical(parentPos, childPos);
          else drawLinkHorizontal(parentPos, childPos);
        }
      });

      var deepestDepth = Math.max.apply(
        null,
        nodes.map(function (item) {
          return getDepth(item.id);
        })
      );

      var finalWidth;
      var finalHeight;
      if (isVertical) {
        var contentWidth = computeSubtreeWidth(root.id) + LEFT_PADDING * 2;
        var contentHeight = TOP_PADDING + deepestDepth * LEVEL_SPACING + NODE_HEIGHT + 160;
        finalWidth = Math.max(CANVAS_MIN_WIDTH, contentWidth);
        finalHeight = Math.max(CANVAS_MIN_HEIGHT, contentHeight);
      } else {
        var contentHeight = computeSubtreeHeight(root.id) + TOP_PADDING * 2;
        var contentWidth = LEFT_PADDING + deepestDepth * LEVEL_SPACING + 520;
        finalWidth = Math.max(CANVAS_MIN_WIDTH, contentWidth);
        finalHeight = Math.max(CANVAS_MIN_HEIGHT, contentHeight);
      }

      canvas.style.width = finalWidth + "px";
      canvas.style.height = finalHeight + "px";
      mindmapEl.style.width = finalWidth + "px";
      mindmapEl.style.height = finalHeight + "px";
      linksEl.style.width = finalWidth + "px";
      linksEl.style.height = finalHeight + "px";
      linksEl.setAttribute("viewBox", "0 0 " + finalWidth + " " + finalHeight);
    }

    function applyZoom() {
      canvas.style.transform = "scale(" + scale + ")";
    }

    function zoom(delta) {
      scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale + delta));
      applyZoom();
    }

    function onWheel(event) {
      if (!event.ctrlKey) return;
      event.preventDefault();
      zoom(event.deltaY > 0 ? -0.05 : 0.05);
    }

    viewport.addEventListener("wheel", onWheel, { passive: false });

    var dragPanState = null;

    function isPanStartBlocked(target) {
      if (!target || !target.closest) return false;
      return !!(target.closest("button") || target.closest(".cc-node-toggle"));
    }

    function onPanPointerMove(e) {
      if (!dragPanState || e.pointerId !== dragPanState.pointerId) return;
      e.preventDefault();
      var dx = e.clientX - dragPanState.startX;
      var dy = e.clientY - dragPanState.startY;
      viewport.scrollLeft = dragPanState.scrollL - dx;
      viewport.scrollTop = dragPanState.scrollT - dy;
    }

    function onPanPointerEnd(e) {
      if (!dragPanState || (e.pointerId !== undefined && e.pointerId !== dragPanState.pointerId)) return;
      document.removeEventListener("pointermove", onPanPointerMove);
      document.removeEventListener("pointerup", onPanPointerEnd);
      document.removeEventListener("pointercancel", onPanPointerEnd);
      viewport.classList.remove("cc-viewport--dragging");
      viewport.style.userSelect = "";
      dragPanState = null;
    }

    function onViewportPointerDown(e) {
      if (e.pointerType === "mouse" && e.button !== 0) return;
      if (isPanStartBlocked(e.target)) return;
      dragPanState = {
        pointerId: e.pointerId,
        startX: e.clientX,
        startY: e.clientY,
        scrollL: viewport.scrollLeft,
        scrollT: viewport.scrollTop,
      };
      viewport.classList.add("cc-viewport--dragging");
      viewport.style.userSelect = "none";
      document.addEventListener("pointermove", onPanPointerMove, { passive: false });
      document.addEventListener("pointerup", onPanPointerEnd);
      document.addEventListener("pointercancel", onPanPointerEnd);
      e.preventDefault();
    }

    viewport.addEventListener("pointerdown", onViewportPointerDown);

    function zoomIn() {
      zoom(0.1);
    }
    function zoomOut() {
      zoom(-0.1);
    }
    function reset() {
      scale = 1;
      applyZoom();
      viewport.scrollTo({ left: 0, top: 0, behavior: "smooth" });
    }

    function expandAll() {
      collapsedNodes.clear();
      render();
      applyZoom();
    }

    function collapseAll() {
      collapsedNodes.clear();
      if (hasChildren("root")) {
        collapsedNodes.add("root");
      }
      render();
      applyZoom();
    }

    applyInitialCollapse();
    render();
    applyZoom();
    viewport.scrollTo({ left: 0, top: 0 });

    return {
      destroy: function () {
        viewport.removeEventListener("wheel", onWheel);
        viewport.removeEventListener("pointerdown", onViewportPointerDown);
        document.removeEventListener("pointermove", onPanPointerMove);
        document.removeEventListener("pointerup", onPanPointerEnd);
        document.removeEventListener("pointercancel", onPanPointerEnd);
        dragPanState = null;
        if (wrap.parentNode) wrap.parentNode.removeChild(wrap);
      },
      zoomIn: zoomIn,
      zoomOut: zoomOut,
      reset: reset,
      expandAll: expandAll,
      collapseAll: collapseAll,
    };
  }

  global.CounselorClassicMindmap = { mount: mount };
})(typeof window !== "undefined" ? window : this);
