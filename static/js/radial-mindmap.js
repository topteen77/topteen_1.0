/**
 * Single radial mindmap component. No duplicate code - use this wherever the mindmap appears.
 * Features: text fitted in circles (SVG-measured wrap), hover zoom on nodes, viewBox zoom, click-to-drill levels.
 */
(function (global) {
  'use strict';

  const instances = {};

  function buildNodeMap(node, parent, map) {
    const nodeKey = node.topic || node.id || 'root';
    map[nodeKey] = { node: node, parent: parent, children: node.children || [] };
    if (node.children && node.children.length > 0) {
      node.children.forEach(function (child) { buildNodeMap(child, node, map); });
    }
  }

  /**
   * Wrap text into lines that fit within maxWidth using SVG text measurement.
   * @param {SVGSVGElement} svg - SVG to use for measurement
   * @param {string} text - Label text
   * @param {number} maxWidth - Max width in same units as SVG
   * @param {number} fontSize - Font size
   * @param {string} fontWeight - e.g. '600', 'bold'
   * @returns {string[]} lines
   */
  function wrapTextForCircle(svg, text, maxWidth, fontSize, fontWeight) {
    const words = (text || '').trim().split(/\s+/).filter(Boolean);
    if (words.length === 0) return [''];

    const measure = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    measure.setAttribute('font-size', fontSize);
    measure.setAttribute('font-weight', fontWeight || '600');
    measure.setAttribute('visibility', 'hidden');
    measure.setAttribute('style', 'pointer-events: none;');
    svg.appendChild(measure);

    const lines = [];
    let currentLine = '';

    for (let i = 0; i < words.length; i++) {
      const testLine = currentLine ? currentLine + ' ' + words[i] : words[i];
      measure.textContent = testLine;
      const w = measure.getComputedTextLength();
      if (w > maxWidth && currentLine) {
        lines.push(currentLine);
        currentLine = words[i];
      } else {
        currentLine = testLine;
      }
    }
    if (currentLine) lines.push(currentLine);
    svg.removeChild(measure);
    return lines;
  }

  /**
   * Calculate minimum circle radius and wrapped lines for a label.
   */
  function calculateMinRadius(svg, text, baseRadius, fontSize, fontWeight) {
    const maxTextWidth = baseRadius * 1.6;
    const lines = wrapTextForCircle(svg, text, maxTextWidth, fontSize, fontWeight);
    const lineHeight = fontSize * 1.25;
    const textHeight = lines.length * lineHeight;
    const minRadius = Math.max(baseRadius, textHeight / 2 + fontSize * 0.5, 24);
    return { radius: Math.min(minRadius, 95), lines: lines };
  }

  function bringToFront(svg, circleEl, textEl) {
    if (circleEl && svg.contains(circleEl)) svg.appendChild(circleEl);
    if (textEl && svg.contains(textEl)) svg.appendChild(textEl);
  }

  /**
   * Hover zoom: scale up node group on hover for readability.
   */
  function addHoverZoom(svg, group, circle, textEl, baseRadius, scale) {
    const scaleFactor = scale || 1.35;
    group.addEventListener('mouseenter', function () {
      bringToFront(svg, circle, textEl);
      const r = parseFloat(circle.getAttribute('r'));
      circle.setAttribute('r', r * scaleFactor);
      const sw = circle.getAttribute('stroke-width') || '3';
      circle.setAttribute('stroke-width', Math.max(4, parseFloat(sw) + 1));
    });
    group.addEventListener('mouseleave', function () {
      const r = parseFloat(circle.getAttribute('r'));
      circle.setAttribute('r', r / scaleFactor);
      circle.setAttribute('stroke-width', '3');
    });
  }

  function render(instanceId, centerNode, inst) {
    const svg = inst.svg;
    const container = inst.container;
    const nodeMap = inst.nodeMap;
    const rootNode = inst.rootNode;
    const options = inst.options;
    const isMobile = typeof window !== 'undefined' && window.innerWidth <= 768;

    const width = container.clientWidth;
    const height = container.clientHeight;
    svg.setAttribute('width', width);
    svg.setAttribute('height', height);
    svg.setAttribute('viewBox', '0 0 ' + width + ' ' + height);
    svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
    svg.style.width = '100%';
    svg.style.height = '100%';
    svg.style.display = 'block';
    svg.style.margin = 'auto';
    svg.innerHTML = '';

    const centerX = width / 2;
    const centerY = height / 2;
    const centerRadius = isMobile ? 70 : 100;
    const childDistance = isMobile ? 160 : 220;
    const siblingDistance = isMobile ? 200 : 280;

    const centerNodeKey = centerNode.topic || centerNode.id || 'root';
    const isRoot = centerNode === rootNode || centerNodeKey === (rootNode.topic || rootNode.id || 'root');
    const nodeInfo = nodeMap[centerNodeKey];
    let parentNode = null;
    let siblings = [];
    if (nodeInfo) {
      parentNode = nodeInfo.parent;
      if (!isRoot && parentNode) {
        const parentKey = parentNode.topic || parentNode.id || 'root';
        const parentInfo = nodeMap[parentKey];
        if (parentInfo && parentInfo.children) {
          siblings = parentInfo.children.filter(function (c) {
            return (c.topic || c.id) !== centerNodeKey;
          });
        }
      }
    }

    // Defs: gradient + glow
    const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
    const gradId = 'centerGradient-' + instanceId;
    const centerGradient = document.createElementNS('http://www.w3.org/2000/svg', 'linearGradient');
    centerGradient.setAttribute('id', gradId);
    centerGradient.setAttribute('x1', '0%');
    centerGradient.setAttribute('y1', '0%');
    centerGradient.setAttribute('x2', '100%');
    centerGradient.setAttribute('y2', '100%');
    const stop1 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
    stop1.setAttribute('offset', '0%');
    stop1.setAttribute('stop-color', '#667eea');
    const stop2 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
    stop2.setAttribute('offset', '100%');
    stop2.setAttribute('stop-color', '#764ba2');
    centerGradient.appendChild(stop1);
    centerGradient.appendChild(stop2);
    defs.appendChild(centerGradient);

    const filter = document.createElementNS('http://www.w3.org/2000/svg', 'filter');
    filter.setAttribute('id', 'glow-' + instanceId);
    const feBlur = document.createElementNS('http://www.w3.org/2000/svg', 'feGaussianBlur');
    feBlur.setAttribute('stdDeviation', '4');
    feBlur.setAttribute('result', 'coloredBlur');
    const feMerge = document.createElementNS('http://www.w3.org/2000/svg', 'feMerge');
    feMerge.appendChild(document.createElementNS('http://www.w3.org/2000/svg', 'feMergeNode')).setAttribute('in', 'coloredBlur');
    feMerge.appendChild(document.createElementNS('http://www.w3.org/2000/svg', 'feMergeNode')).setAttribute('in', 'SourceGraphic');
    filter.appendChild(feBlur);
    filter.appendChild(feMerge);
    defs.appendChild(filter);
    svg.appendChild(defs);

    const centerTopic = centerNode.topic || 'Root';
    const centerFontSize = 18;
    const centerCalc = calculateMinRadius(svg, centerTopic, centerRadius, centerFontSize, 'bold');
    const finalCenterRadius = Math.max(centerRadius, centerCalc.radius);
    const lineStartRadius = finalCenterRadius + 5;

    // ---- Lines ----
    if (siblings.length > 0) {
      const step = (2 * Math.PI) / siblings.length;
      siblings.forEach(function (sib, i) {
        const a = i * step;
        const x = centerX + siblingDistance * Math.cos(a);
        const y = centerY + siblingDistance * Math.sin(a);
        const l = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        l.setAttribute('x1', centerX + lineStartRadius * Math.cos(a));
        l.setAttribute('y1', centerY + lineStartRadius * Math.sin(a));
        l.setAttribute('x2', x);
        l.setAttribute('y2', y);
        l.setAttribute('stroke', '#999');
        l.setAttribute('stroke-width', '2');
        l.setAttribute('stroke-dasharray', '5,5');
        l.setAttribute('opacity', '0.4');
        svg.appendChild(l);
      });
    }
    if (centerNode.children && centerNode.children.length > 0) {
      const step = (2 * Math.PI) / centerNode.children.length;
      centerNode.children.forEach(function (_, i) {
        const a = i * step;
        const x = centerX + childDistance * Math.cos(a);
        const y = centerY + childDistance * Math.sin(a);
        const l = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        l.setAttribute('x1', centerX + lineStartRadius * Math.cos(a));
        l.setAttribute('y1', centerY + lineStartRadius * Math.sin(a));
        l.setAttribute('x2', x);
        l.setAttribute('y2', y);
        l.setAttribute('stroke', '#667eea');
        l.setAttribute('stroke-width', '3');
        l.setAttribute('opacity', '0.6');
        svg.appendChild(l);
      });
    }

    // ---- Sibling nodes ----
    if (siblings.length > 0) {
      const step = (2 * Math.PI) / siblings.length;
      siblings.forEach(function (sib, i) {
        const a = i * step;
        const x = centerX + siblingDistance * Math.cos(a);
        const y = centerY + siblingDistance * Math.sin(a);
        const topic = sib.topic || 'Node';
        const calc = calculateMinRadius(svg, topic, 50, 11, '600');
        const r = calc.radius;

        const hasChildren = sib.children && sib.children.length > 0;
        const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        g.setAttribute('class', 'radial-sibling-node' + (hasChildren ? ' radial-node-link' : ' radial-node-no-link'));

        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        circle.setAttribute('cx', x);
        circle.setAttribute('cy', y);
        circle.setAttribute('r', r);
        if (hasChildren) {
          circle.setAttribute('fill', '#b8b8d1');
          circle.setAttribute('stroke', '#667eea');
          circle.setAttribute('stroke-width', '2');
          circle.style.cursor = 'pointer';
          circle.addEventListener('click', function (e) {
            e.stopPropagation();
            if (options.onNodeClick) options.onNodeClick(sib, { type: 'sibling', hasChildren: true });
          });
        } else {
          circle.setAttribute('fill', '#e8e8e8');
          circle.setAttribute('stroke', '#999');
          circle.setAttribute('stroke-width', '1.5');
          circle.setAttribute('stroke-dasharray', '5,4');
          circle.setAttribute('opacity', '0.92');
          circle.style.cursor = 'default';
          circle.style.pointerEvents = 'none';
        }
        g.appendChild(circle);

        const textEl = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        textEl.setAttribute('x', x);
        textEl.setAttribute('y', y);
        textEl.setAttribute('text-anchor', 'middle');
        textEl.setAttribute('dominant-baseline', 'middle');
        textEl.setAttribute('fill', hasChildren ? '#444' : '#888');
        textEl.setAttribute('font-size', '11');
        textEl.setAttribute('font-weight', '600');
        textEl.setAttribute('style', 'pointer-events: none;');
        if (calc.lines.length === 1) {
          textEl.textContent = calc.lines[0];
        } else {
          const lh = 11 * 1.25;
          const startY = y - ((calc.lines.length - 1) * lh) / 2;
          calc.lines.forEach(function (line, j) {
            const tspan = document.createElementNS('http://www.w3.org/2000/svg', 'tspan');
            tspan.setAttribute('x', x);
            tspan.setAttribute('y', startY + j * lh);
            tspan.setAttribute('text-anchor', 'middle');
            tspan.textContent = line;
            textEl.appendChild(tspan);
          });
        }
        g.appendChild(textEl);
        svg.appendChild(g);
      });
    }

    // ---- Child nodes ----
    if (centerNode.children && centerNode.children.length > 0) {
      const step = (2 * Math.PI) / centerNode.children.length;
      const n = centerNode.children.length;
      centerNode.children.forEach(function (child, index) {
        const angle = index * step;
        const x = centerX + childDistance * Math.cos(angle);
        const y = centerY + childDistance * Math.sin(angle);
        const topic = child.topic || 'Node';
        const calc = calculateMinRadius(svg, topic, 65, 13, '700');
        const childRadius = calc.radius;

        const isChildLeaf = !child.children || child.children.length === 0;
        const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        g.setAttribute('class', 'radial-child-node' + (isChildLeaf ? ' radial-node-no-link' : ' radial-node-link'));

        const childCircle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        childCircle.setAttribute('cx', x);
        childCircle.setAttribute('cy', y);
        childCircle.setAttribute('r', childRadius);
        if (isChildLeaf) {
          childCircle.setAttribute('fill', 'hsl(' + (index * 360 / n) + ', 25%, 82%)');
          childCircle.setAttribute('stroke', '#aaa');
          childCircle.setAttribute('stroke-width', '2');
          childCircle.setAttribute('stroke-dasharray', '5,4');
          childCircle.setAttribute('opacity', '0.9');
          childCircle.style.cursor = 'default';
          childCircle.style.pointerEvents = 'none';
        } else {
          childCircle.setAttribute('fill', 'hsl(' + (index * 360 / n) + ', 70%, 60%)');
          childCircle.setAttribute('stroke', 'white');
          childCircle.setAttribute('stroke-width', '3');
          childCircle.style.cursor = 'pointer';
          childCircle.addEventListener('click', function (e) {
            e.stopPropagation();
            if (options.onNodeClick) options.onNodeClick(child, { type: 'child', hasChildren: true });
          });
        }
        g.appendChild(childCircle);

        const childText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        childText.setAttribute('x', x);
        childText.setAttribute('y', y);
        childText.setAttribute('text-anchor', 'middle');
        childText.setAttribute('dominant-baseline', 'middle');
        childText.setAttribute('fill', isChildLeaf ? '#666' : 'white');
        childText.setAttribute('font-size', '13');
        childText.setAttribute('font-weight', '700');
        childText.setAttribute('style', 'text-shadow: 1px 1px 2px rgba(0,0,0,0.5); pointer-events: none;');
        if (calc.lines.length === 1) {
          childText.textContent = calc.lines[0];
        } else {
          const lh = 13 * 1.25;
          const startY = y - ((calc.lines.length - 1) * lh) / 2;
          calc.lines.forEach(function (line, j) {
            const tspan = document.createElementNS('http://www.w3.org/2000/svg', 'tspan');
            tspan.setAttribute('x', x);
            tspan.setAttribute('y', startY + j * lh);
            tspan.setAttribute('text-anchor', 'middle');
            tspan.textContent = line;
            childText.appendChild(tspan);
          });
        }
        g.appendChild(childText);
        if (!isChildLeaf) addHoverZoom(svg, g, childCircle, childText, childRadius);
        svg.appendChild(g);
      });
    }

    // ---- Center (bg + circle + text) ----
    const centerBg = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    centerBg.setAttribute('cx', centerX);
    centerBg.setAttribute('cy', centerY);
    centerBg.setAttribute('r', finalCenterRadius + 2);
    centerBg.setAttribute('fill', 'url(#' + gradId + ')');
    svg.appendChild(centerBg);

    const centerCircle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    centerCircle.setAttribute('cx', centerX);
    centerCircle.setAttribute('cy', centerY);
    centerCircle.setAttribute('r', finalCenterRadius);
    centerCircle.setAttribute('fill', 'url(#' + gradId + ')');
    centerCircle.setAttribute('stroke', '#fff');
    centerCircle.setAttribute('stroke-width', '5');
    centerCircle.setAttribute('filter', 'url(#glow-' + instanceId + ')');
    centerCircle.setAttribute('class', 'radial-center-node' + (!isRoot && parentNode ? ' radial-node-link' : ' radial-node-no-link'));
    if (!isRoot && parentNode) {
      centerCircle.style.cursor = 'pointer';
      centerCircle.addEventListener('click', function (e) {
        e.stopPropagation();
        if (options.onNodeClick) options.onNodeClick(parentNode, { type: 'center', goToParent: true });
      });
      centerCircle.addEventListener('mouseenter', function () {
        bringToFront(svg, centerCircle, centerText);
        centerCircle.setAttribute('r', finalCenterRadius + 10);
        centerCircle.setAttribute('stroke-width', '6');
      });
      centerCircle.addEventListener('mouseleave', function () {
        centerCircle.setAttribute('r', finalCenterRadius);
        centerCircle.setAttribute('stroke-width', '5');
      });
    } else {
      centerCircle.style.cursor = 'default';
    }
    svg.appendChild(centerCircle);

    const centerText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    centerText.setAttribute('x', centerX);
    centerText.setAttribute('y', centerY);
    centerText.setAttribute('text-anchor', 'middle');
    centerText.setAttribute('dominant-baseline', 'middle');
    centerText.setAttribute('fill', 'white');
    centerText.setAttribute('font-size', String(centerFontSize));
    centerText.setAttribute('font-weight', 'bold');
    centerText.setAttribute('style', 'text-shadow: 2px 2px 4px rgba(0,0,0,0.5); pointer-events: none;');
    if (centerCalc.lines.length === 1) {
      centerText.textContent = centerCalc.lines[0];
    } else {
      const lh = centerFontSize * 1.25;
      const startY = centerY - ((centerCalc.lines.length - 1) * lh) / 2;
      centerCalc.lines.forEach(function (line, j) {
        const tspan = document.createElementNS('http://www.w3.org/2000/svg', 'tspan');
        tspan.setAttribute('x', centerX);
        tspan.setAttribute('y', startY + j * lh);
        tspan.setAttribute('text-anchor', 'middle');
        tspan.textContent = line;
        centerText.appendChild(tspan);
      });
    }
    svg.appendChild(centerText);

    // Parent arrow
    if (!isRoot && parentNode) {
      const arrowG = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      arrowG.setAttribute('class', 'radial-parent-link');
      arrowG.setAttribute('style', 'cursor: pointer; opacity: 0.85;');
      const arrowY = centerY + finalCenterRadius + 30;
      const arrowSize = 28;
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', centerX);
      line.setAttribute('y1', arrowY);
      line.setAttribute('x2', centerX - arrowSize);
      line.setAttribute('y2', arrowY);
      line.setAttribute('stroke', '#fff');
      line.setAttribute('stroke-width', '3');
      line.setAttribute('stroke-linecap', 'round');
      const head = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      head.setAttribute('d', 'M ' + (centerX - arrowSize) + ' ' + arrowY + ' L ' + (centerX - arrowSize + 10) + ' ' + (arrowY - 5) + ' L ' + (centerX - arrowSize + 10) + ' ' + (arrowY + 5) + ' Z');
      head.setAttribute('fill', '#fff');
      arrowG.appendChild(line);
      arrowG.appendChild(head);
      arrowG.addEventListener('click', function (e) {
        e.stopPropagation();
        if (options.onNodeClick) options.onNodeClick(parentNode, { type: 'center', goToParent: true });
      });
      svg.appendChild(arrowG);
    }

    applyZoom(instanceId);
  }

  function applyZoom(instanceId) {
    var key = String(instanceId);
    var inst = instances[key];
    if (!inst || !inst.svg || !inst.container) return;
    const svg = inst.svg;
    const zoom = inst.zoom;
    const width = parseFloat(svg.getAttribute('width'));
    const height = parseFloat(svg.getAttribute('height'));
    if (!width || !height) return;
    const isMobile = typeof window !== 'undefined' && window.innerWidth <= 768;
    if (isMobile) {
      const w = width / zoom;
      const h = height / zoom;
      const ox = Math.max(0, (width - w) / 2);
      const oy = Math.max(0, (height - h) / 2);
      svg.setAttribute('viewBox', ox + ' ' + oy + ' ' + w + ' ' + h);
    } else {
      svg.style.transformOrigin = 'center center';
      svg.style.transform = 'scale(' + zoom + ')';
      svg.setAttribute('viewBox', '0 0 ' + width + ' ' + height);
    }
    svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
  }

  /**
   * Public API
   * options: { instanceId, containerId, svgId, loadingId, controlsId, apiUrl?, data?, initialCenter?, onNodeClick? }
   * onNodeClick(node, context): context.type = 'child'|'sibling'|'center', context.hasChildren, context.goToParent
   */
  function init(options) {
    var id = String(options.instanceId);
    const container = document.getElementById(options.containerId);
    const svg = document.getElementById(options.svgId);
    const loadingEl = options.loadingId ? document.getElementById(options.loadingId) : null;
    const controlsEl = options.controlsId ? document.getElementById(options.controlsId) : null;
    if (!container || !svg) return;

    function onData(data) {
      if (!data || data.available === false) {
        if (loadingEl) loadingEl.style.display = 'none';
        return;
      }
      const rootNode = data.data;
      const nodeMap = {};
      buildNodeMap(rootNode, null, nodeMap);
      const initialCenter = options.initialCenter || rootNode;
      const isMobile = typeof window !== 'undefined' && window.innerWidth <= 768;

      instances[id] = {
        rootNode: rootNode,
        currentCenter: initialCenter,
        nodeMap: nodeMap,
        zoom: isMobile ? 0.75 : 1,
        options: options,
        container: container,
        svg: svg
      };
      if (loadingEl) loadingEl.style.display = 'none';
      if (controlsEl) controlsEl.style.display = 'block';
      svg.style.display = 'block';
      render(id, initialCenter, instances[id]);
    }

    // Load full mindmap tree once; all navigation (setCenter) uses in-memory data for smooth interaction
    if (options.apiUrl) {
      fetch(options.apiUrl)
        .then(function (r) { return r.json(); })
        .then(onData)
        .catch(function () {
          if (loadingEl) loadingEl.style.display = 'none';
        });
    } else if (options.data && options.data.data) {
      onData(options.data);
    }
  }

  function setCenter(instanceId, node) {
    var key = String(instanceId);
    const inst = instances[key];
    if (!inst || !node) return;
    inst.currentCenter = node;
    const isMobile = typeof window !== 'undefined' && window.innerWidth <= 768;
    inst.zoom = isMobile ? 0.75 : 1;
    render(key, node, inst);
    setTimeout(function () { applyZoom(key); }, 50);
  }

  function zoomIn(instanceId) {
    var key = String(instanceId);
    var inst = instances[key];
    if (!inst) return;
    const isMobile = typeof window !== 'undefined' && window.innerWidth <= 768;
    const maxZ = isMobile ? 1.5 : 2;
    inst.zoom = Math.min(inst.zoom + 0.1, maxZ);
    render(key, inst.currentCenter, inst);
    applyZoom(key);
  }

  function zoomOut(instanceId) {
    var key = String(instanceId);
    const inst = instances[key];
    if (!inst) return;
    const isMobile = typeof window !== 'undefined' && window.innerWidth <= 768;
    const minZ = isMobile ? 0.6 : 0.5;
    inst.zoom = Math.max(inst.zoom - 0.1, minZ);
    render(key, inst.currentCenter, inst);
    applyZoom(key);
  }

  function reset(instanceId) {
    var key = String(instanceId);
    const inst = instances[key];
    if (!inst) return;
    inst.currentCenter = inst.rootNode;
    const isMobile = typeof window !== 'undefined' && window.innerWidth <= 768;
    inst.zoom = isMobile ? 0.75 : 1;
    render(key, inst.rootNode, inst);
    setTimeout(function () { applyZoom(key); }, 50);
  }

  if (typeof window !== 'undefined') {
    window.addEventListener('resize', function () {
      Object.keys(instances).forEach(function (id) {
        var inst = instances[id];
        if (inst && inst.currentCenter) {
          render(id, inst.currentCenter, inst);
          applyZoom(id);
        }
      });
    });
  }

  global.RadialMindmap = {
    init: init,
    setCenter: setCenter,
    zoomIn: zoomIn,
    zoomOut: zoomOut,
    reset: reset
  };
})(typeof window !== 'undefined' ? window : this);
