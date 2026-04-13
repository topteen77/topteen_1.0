/**
 * Classic mindmap: default "pill" (counselor widget) or "ribbon" (colored branches — career embed).
 * Counselor course widget calls mount() without visualStyle → pills. Career passes visualStyle: 'ribbon'.
 */
(function (global) {
  'use strict';

  var HGAP = 52;
  var VGAP = 22;

  var RIBBON_PALETTE = [
    '#22c55e', '#ef4444', '#a855f7', '#b45309', '#ec4899', '#64748b',
    '#ca8a04', '#38bdf8', '#1d4ed8', '#f97316', '#14b8a6', '#8b5cf6',
  ];

  function ribbonHubColor(parent, child) {
    if (!parent) return '#0a81cf';
    var idx = parent.children.indexOf(child);
    return RIBBON_PALETTE[(idx >= 0 ? idx : 0) % RIBBON_PALETTE.length];
  }

  function textDims(text, level) {
    var t = String(text || '—');
    var w0 = { root: 200, topic: 184, sub: 172, leaf: 160 };
    var h0 = { root: 52, topic: 46, sub: 42, leaf: 40 };
    var bw = w0[level] || 160;
    var bh = h0[level] || 40;
    var extraLines = Math.max(0, Math.ceil(t.length / 36) - 1);
    var w = Math.min(300, bw + Math.max(0, t.length - 32) * 4.2);
    return { w: Math.round(w), h: bh + extraLines * 16 };
  }

  function ribbonDims(n) {
    var t = String((n && n.text) || '—');
    var kids = (n && n.children) || [];
    if (kids.length > 0) {
      return { w: Math.round(Math.min(300, 28 + Math.min(t.length, 44) * 7.6 + 20)), h: 40 };
    }
    return { w: Math.round(Math.min(340, 20 + Math.min(t.length, 52) * 8)), h: 52 };
  }

  function flatToTree(flat) {
    if (!flat || !flat.length) return null;
    var byId = Object.create(null);
    flat.forEach(function (n) {
      if (!n || !n.id) return;
      byId[n.id] = { id: n.id, text: n.text || '—', level: n.level || 'leaf', children: [] };
    });
    var root = null;
    flat.forEach(function (n) {
      if (!n || !n.id) return;
      var node = byId[n.id];
      if (!node) return;
      if (!n.parent) root = node;
      else if (byId[n.parent]) byId[n.parent].children.push(node);
    });
    if (!root) {
      var k = Object.keys(byId);
      if (k.length) root = byId[k[0]];
    }
    return root;
  }

  function initExpandedSet(root, depthLimit) {
    var expanded = new Set();
    function walk(n, d) {
      if (!n) return;
      if (d < depthLimit) expanded.add(n.id);
      (n.children || []).forEach(function (c) {
        walk(c, d + 1);
      });
    }
    walk(root, 0);
    return expanded;
  }

  function collectExpandableIds(n, acc) {
    if (!n) return;
    if (n.children && n.children.length) acc.push(n.id);
    (n.children || []).forEach(function (c) {
      collectExpandableIds(c, acc);
    });
  }

  function layoutBounds(root, expanded) {
    var minX = Infinity;
    var minY = Infinity;
    var maxX = -Infinity;
    var maxY = -Infinity;
    function walk(n) {
      if (n._x == null) return;
      minX = Math.min(minX, n._x);
      minY = Math.min(minY, n._y);
      maxX = Math.max(maxX, n._x + n._w);
      maxY = Math.max(maxY, n._y + n._h);
      if (expanded.has(n.id)) (n.children || []).forEach(walk);
    }
    walk(root);
    if (minX === Infinity) return { x: 0, y: 0, width: 400, height: 280 };
    return { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
  }

  function layoutHorizontalCore(n, expanded, depth, y0, dimFn, depthXPitch) {
    if (!n) return y0;
    var xp = depthXPitch == null ? 240 : depthXPitch;
    var dim = dimFn(n);
    n._w = dim.w;
    n._h = dim.h;
    n._x = depth * xp + HGAP;
    var kids = n.children || [];
    var open = expanded.has(n.id) && kids.length > 0;
    if (!open) {
      n._y = y0;
      return y0 + n._h + VGAP;
    }
    var y = y0;
    kids.forEach(function (c) {
      y = layoutHorizontalCore(c, expanded, depth + 1, y, dimFn, xp);
    });
    var first = kids[0];
    var last = kids[kids.length - 1];
    var mid = (first._y + first._h / 2 + last._y + last._h / 2) / 2;
    n._y = mid - n._h / 2;
    return y;
  }

  function layoutVerticalCore(n, expanded, depth, x0, dimFn) {
    if (!n) return x0;
    var dim = dimFn(n);
    n._w = dim.w;
    n._h = dim.h;
    n._y = depth * (dim.h + VGAP + 8) + VGAP;
    var kids = n.children || [];
    var open = expanded.has(n.id) && kids.length > 0;
    if (!open) {
      n._x = x0;
      return x0 + n._w + HGAP;
    }
    var x = x0;
    kids.forEach(function (c) {
      x = layoutVerticalCore(c, expanded, depth + 1, x, dimFn);
    });
    var first = kids[0];
    var last = kids[kids.length - 1];
    var mid = (first._x + first._w / 2 + last._x + last._w / 2) / 2;
    n._x = mid - n._w / 2;
    return x;
  }

  function pillDimFn(n) {
    return textDims(n.text, n.level);
  }

  function linkPathH(p, c) {
    var x1 = p._x + p._w;
    var y1 = p._y + p._h / 2;
    var x2 = c._x;
    var y2 = c._y + c._h / 2;
    var m = (x1 + x2) / 2;
    return 'M' + x1 + ',' + y1 + ' C' + m + ',' + y1 + ' ' + m + ',' + y2 + ' ' + x2 + ',' + y2;
  }

  function linkPathV(p, c) {
    var x1 = p._x + p._w / 2;
    var y1 = p._y + p._h;
    var x2 = c._x + c._w / 2;
    var y2 = c._y;
    var m = (y1 + y2) / 2;
    return 'M' + x1 + ',' + y1 + ' C' + x1 + ',' + m + ' ' + x2 + ',' + m + ' ' + x2 + ',' + y2;
  }

  function edgeIsCollapsedLeaf(c, expanded) {
    return !c.children || !c.children.length || !expanded.has(c.id);
  }

  function linkPathRibbonInternalH(p, c) {
    var px = p._x + p._w - 9;
    var py = p._y + p._h / 2;
    var cx = c._x + 9;
    var cy = c._y + c._h / 2;
    var mid = (px + cx) / 2;
    return 'M' + px + ',' + py + ' C' + mid + ',' + py + ' ' + mid + ',' + cy + ' ' + cx + ',' + cy;
  }

  function linkPathRibbonLeafH(p, c) {
    var px = p._x + p._w - 9;
    var py = p._y + p._h / 2;
    var uy = c._y + c._h - 11;
    var x1 = c._x + 4;
    var x2 = c._x + c._w - 4;
    var mid = (px + x1) / 2;
    return 'M' + px + ',' + py + ' C' + mid + ',' + py + ' ' + mid + ',' + uy + ' ' + x1 + ',' + uy + ' L' + x2 + ',' + uy;
  }

  function linkPathRibbonInternalV(p, c) {
    var px = p._x + p._w / 2;
    var py = p._y + p._h - 9;
    var cx = c._x + c._w / 2;
    var cy = c._y + 9;
    var mid = (py + cy) / 2;
    return 'M' + px + ',' + py + ' C' + px + ',' + mid + ' ' + cx + ',' + mid + ' ' + cx + ',' + cy;
  }

  function linkPathRibbonLeafV(p, c) {
    var px = p._x + p._w / 2;
    var py = p._y + p._h - 9;
    var vx = c._x + 10;
    var yTop = c._y + 26;
    var yBot = c._y + c._h - 7;
    var mid = (py + yTop) / 2;
    return 'M' + px + ',' + py + ' C' + px + ',' + mid + ' ' + vx + ',' + mid + ' ' + vx + ',' + yTop + ' L' + vx + ',' + yBot;
  }

  function drawLinks(root, expanded, g, linkFn) {
    function walk(p) {
      if (!expanded.has(p.id) || !p.children || !p.children.length) return;
      p.children.forEach(function (c) {
        if (c._x == null) return;
        var path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('class', 'cc-link');
        path.setAttribute('d', linkFn(p, c));
        g.appendChild(path);
        walk(c);
      });
    }
    walk(root);
  }

  function drawLinksRibbon(root, expanded, layout, g) {
    function walk(p) {
      if (!expanded.has(p.id) || !p.children || !p.children.length) return;
      p.children.forEach(function (c) {
        if (c._x == null) return;
        var col = ribbonHubColor(p, c);
        var leaf = edgeIsCollapsedLeaf(c, expanded);
        var d =
          layout === 'vertical'
            ? leaf
              ? linkPathRibbonLeafV(p, c)
              : linkPathRibbonInternalV(p, c)
            : leaf
              ? linkPathRibbonLeafH(p, c)
              : linkPathRibbonInternalH(p, c);
        var path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('class', 'cc-link cc-ribbon-link');
        path.setAttribute('d', d);
        path.setAttribute('stroke', col);
        path.setAttribute('fill', 'none');
        path.setAttribute('stroke-width', '2.5');
        path.setAttribute('stroke-linecap', 'round');
        path.setAttribute('stroke-linejoin', 'round');
        g.appendChild(path);
        walk(c);
      });
    }
    walk(root);
  }

  function drawHubsRibbon(parent, n, expanded, layout, gHubs) {
    if (n._x == null) return;
    var hasKids = n.children && n.children.length;
    if (hasKids) {
      var col = ribbonHubColor(parent, n);
      var cx;
      var cy;
      if (layout === 'vertical') {
        cx = n._x + n._w / 2;
        cy = n._y + n._h - 9;
      } else {
        cx = n._x + n._w - 9;
        cy = n._y + n._h / 2;
      }
      var circ = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      circ.setAttribute('cx', String(cx));
      circ.setAttribute('cy', String(cy));
      circ.setAttribute('r', '6');
      if (expanded.has(n.id)) {
        circ.setAttribute('fill', '#ffffff');
        circ.setAttribute('stroke', col);
        circ.setAttribute('class', 'cc-ribbon-hub cc-ribbon-hub--expanded');
      } else {
        circ.setAttribute('fill', col);
        circ.setAttribute('stroke', col);
        circ.setAttribute('class', 'cc-ribbon-hub cc-ribbon-hub--collapsed');
      }
      circ.setAttribute('stroke-width', '2');
      gHubs.appendChild(circ);
    }
    if (expanded.has(n.id)) (n.children || []).forEach(function (c) {
      drawHubsRibbon(n, c, expanded, layout, gHubs);
    });
  }

  function drawNodes(root, expanded, gNodes, onToggle) {
    function walk(n) {
      if (n._x == null) return;
      var hasKids = n.children && n.children.length > 0;
      var wrap = document.createElementNS('http://www.w3.org/2000/svg', 'foreignObject');
      wrap.setAttribute('x', n._x);
      wrap.setAttribute('y', n._y);
      wrap.setAttribute('width', n._w);
      wrap.setAttribute('height', n._h);
      wrap.setAttribute('class', 'cc-node-wrap' + (hasKids ? ' cc-has-children' : ''));
      if (hasKids) {
        wrap.setAttribute('tabindex', '0');
        wrap.setAttribute('role', 'button');
        wrap.setAttribute('aria-expanded', expanded.has(n.id) ? 'true' : 'false');
      }
      var div = document.createElementNS('http://www.w3.org/1999/xhtml', 'div');
      div.className = 'cc-pill cc-' + (n.level || 'leaf');
      div.textContent = n.text;
      wrap.appendChild(div);
      if (hasKids) {
        wrap.addEventListener('click', function (e) {
          e.stopPropagation();
          onToggle(n.id);
        });
        wrap.addEventListener('keydown', function (e) {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onToggle(n.id);
          }
        });
      }
      gNodes.appendChild(wrap);
      if (expanded.has(n.id)) n.children.forEach(walk);
    }
    walk(root);
  }

  function drawNodesRibbon(root, expanded, layout, gNodes, onToggle) {
    function walk(n) {
      if (n._x == null) return;
      var hasKids = n.children && n.children.length > 0;
      var wrap = document.createElementNS('http://www.w3.org/2000/svg', 'foreignObject');
      wrap.setAttribute('x', n._x);
      wrap.setAttribute('y', n._y);
      wrap.setAttribute('width', n._w);
      wrap.setAttribute('height', n._h);
      wrap.setAttribute(
        'class',
        'cc-node-wrap cc-ribbon-node' + (hasKids ? ' cc-ribbon-branch-wrap cc-has-children' : ' cc-ribbon-leaf-wrap')
      );
      if (hasKids) {
        wrap.setAttribute('tabindex', '0');
        wrap.setAttribute('role', 'button');
        wrap.setAttribute('aria-expanded', expanded.has(n.id) ? 'true' : 'false');
      }
      var div = document.createElementNS('http://www.w3.org/1999/xhtml', 'div');
      if (!hasKids) {
        div.className = 'cc-ribbon-leaf' + (layout === 'vertical' ? ' cc-ribbon-leaf--vertical' : '');
        var span = document.createElementNS('http://www.w3.org/1999/xhtml', 'span');
        span.className = 'cc-ribbon-leaf-txt';
        span.textContent = n.text;
        div.appendChild(span);
      } else {
        div.className =
          'cc-ribbon-branch' + (layout === 'vertical' ? ' cc-ribbon-branch--vertical' : ' cc-ribbon-branch--horizontal');
        var t = document.createElementNS('http://www.w3.org/1999/xhtml', 'span');
        t.className = 'cc-ribbon-branch-txt';
        t.textContent = n.text;
        div.appendChild(t);
      }
      wrap.appendChild(div);
      if (hasKids) {
        wrap.addEventListener('click', function (e) {
          e.stopPropagation();
          onToggle(n.id);
        });
        wrap.addEventListener('keydown', function (e) {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onToggle(n.id);
          }
        });
      }
      gNodes.appendChild(wrap);
      if (expanded.has(n.id)) n.children.forEach(walk);
    }
    walk(root);
  }

  function mount(hostEl, options) {
    options = options || {};
    var flatNodes = options.nodes;
    var layout = options.layout === 'vertical' ? 'vertical' : 'horizontal';
    var fillContainer = options.fillContainer !== false;
    var depth0 = options.initialExpandDepth != null ? options.initialExpandDepth : 1;
    var visualStyle = options.visualStyle === 'ribbon' ? 'ribbon' : 'pill';

    var rootTree = flatToTree(flatNodes);
    if (!rootTree) {
      hostEl.innerHTML = '<p class="text-muted small p-2">No mind map data.</p>';
      return {
        zoomIn: function () {},
        zoomOut: function () {},
        reset: function () {},
        expandAll: function () {},
        collapseAll: function () {},
        destroy: function () {},
      };
    }

    var expanded = initExpandedSet(rootTree, depth0);
    var scale = 1;
    var tx = 0;
    var ty = 0;
    var userTunedView = false;
    var ZOOM_MIN = 0.08;
    var ZOOM_MAX = 12;
    var dragging = false;
    var dragSX = 0;
    var dragSY = 0;
    var dragTX = 0;
    var dragTY = 0;

    var wrap = document.createElement('div');
    wrap.className =
      'counselor-classic-mm' +
      (fillContainer ? ' counselor-classic-mm--fill-host' : '') +
      (visualStyle === 'ribbon' ? ' cc-career-ribbon-root' : '');
    var viewport = document.createElement('div');
    viewport.className = 'cc-viewport' + (visualStyle === 'ribbon' ? ' cc-career-ribbon-viewport' : '');
    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', 'cc-svg');
    svg.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    var gPan = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    gPan.setAttribute('class', 'cc-pan');
    var gLinks = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    gLinks.setAttribute('class', 'cc-links');
    var gHubs = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    gHubs.setAttribute('class', 'cc-ribbon-hubs');
    var gNodes = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    gNodes.setAttribute('class', 'cc-nodes');
    gPan.appendChild(gLinks);
    gPan.appendChild(gNodes);
    if (visualStyle === 'ribbon') gPan.appendChild(gHubs);
    svg.appendChild(gPan);
    viewport.appendChild(svg);
    wrap.appendChild(viewport);
    hostEl.innerHTML = '';
    hostEl.appendChild(wrap);

    function applyPanZoom() {
      gPan.setAttribute('transform', 'translate(' + tx + ',' + ty + ') scale(' + scale + ')');
      if (visualStyle === 'ribbon') {
        var bb = layoutBounds(rootTree, expanded);
        var vw = viewport.clientWidth || 400;
        var vh = viewport.clientHeight || 300;
        var pad = 32;
        var needW = Math.max(vw, Math.ceil(tx + (bb.x + bb.width) * scale + pad));
        var needH = Math.max(vh, Math.ceil(ty + (bb.y + bb.height) * scale + pad));
        svg.style.width = needW + 'px';
        svg.style.height = needH + 'px';
      }
    }

    /** Content coords inside scrollable viewport (matches tx/ty / scale space). */
    function contentPointFromClient(clientX, clientY) {
      var vrect = viewport.getBoundingClientRect();
      return {
        x: clientX - vrect.left + viewport.scrollLeft,
        y: clientY - vrect.top + viewport.scrollTop,
      };
    }

    function zoomToward(mx, my, factor) {
      userTunedView = true;
      var ns = Math.min(Math.max(scale * factor, ZOOM_MIN), ZOOM_MAX);
      var wx = (mx - tx) / scale;
      var wy = (my - ty) / scale;
      scale = ns;
      tx = mx - wx * scale;
      ty = my - wy * scale;
      applyPanZoom();
    }

    function dimFn(n) {
      return visualStyle === 'ribbon' ? ribbonDims(n) : pillDimFn(n);
    }

    function relayout() {
      (function clear(n) {
        if (!n) return;
        delete n._x;
        delete n._y;
        delete n._w;
        delete n._h;
        (n.children || []).forEach(clear);
      })(rootTree);
      if (layout === 'vertical') layoutVerticalCore(rootTree, expanded, 0, HGAP, dimFn);
      else {
        var depthXPitch = visualStyle === 'ribbon' ? 276 : 240;
        layoutHorizontalCore(rootTree, expanded, 0, VGAP, dimFn, depthXPitch);
      }
    }

    function redraw() {
      relayout();
      gLinks.innerHTML = '';
      gNodes.innerHTML = '';
      if (visualStyle === 'ribbon') gHubs.innerHTML = '';

      var onToggle = function (id) {
        if (expanded.has(id)) expanded.delete(id);
        else expanded.add(id);
        redraw();
        if (userTunedView) applyPanZoom();
        else fit();
      };

      if (visualStyle === 'ribbon') {
        drawLinksRibbon(rootTree, expanded, layout, gLinks);
        drawNodesRibbon(rootTree, expanded, layout, gNodes, onToggle);
        drawHubsRibbon(null, rootTree, expanded, layout, gHubs);
      } else {
        drawLinks(rootTree, expanded, gLinks, layout === 'vertical' ? linkPathV : linkPathH);
        drawNodes(rootTree, expanded, gNodes, onToggle);
      }
      applyPanZoom();
    }

    function fit() {
      var pad = 32;
      var bb = layoutBounds(rootTree, expanded);
      var vw = viewport.clientWidth || 400;
      var vh = viewport.clientHeight || 300;
      if (vw < 2 || vh < 2) return;
      var bw = Math.max(bb.width, 80);
      var bh = Math.max(bb.height, 60);
      var sUnclamped = Math.min(vw / (bw + pad * 2), vh / (bh + pad * 2), 1.35) * 0.94;
      var s = sUnclamped;
      var ribbonMinScale = 0.22;
      var forcedRibbonFloor = false;
      if (visualStyle === 'ribbon' && s < ribbonMinScale) {
        s = ribbonMinScale;
        forcedRibbonFloor = true;
      }
      scale = s;
      if (visualStyle === 'ribbon') {
        if (forcedRibbonFloor) {
          tx = pad - bb.x * s;
          ty = pad - bb.y * s;
        } else {
          tx = (vw - bw * s) / 2 - bb.x * s;
          ty = (vh - bh * s) / 2 - bb.y * s;
        }
      } else {
        tx = (vw - bw * s) / 2 - bb.x * s;
        ty = (vh - bh * s) / 2 - bb.y * s;
        svg.style.width = '';
        svg.style.height = '';
      }
      applyPanZoom();
    }

    function zoomIn() {
      var mx = viewport.scrollLeft + (viewport.clientWidth || 400) / 2;
      var my = viewport.scrollTop + (viewport.clientHeight || 300) / 2;
      zoomToward(mx, my, 1.2);
    }

    function zoomOut() {
      var mx = viewport.scrollLeft + (viewport.clientWidth || 400) / 2;
      var my = viewport.scrollTop + (viewport.clientHeight || 300) / 2;
      zoomToward(mx, my, 1 / 1.2);
    }

    function reset() {
      userTunedView = false;
      fit();
    }

    function expandAll() {
      userTunedView = false;
      var acc = [];
      collectExpandableIds(rootTree, acc);
      acc.forEach(function (id) {
        expanded.add(id);
      });
      redraw();
      fit();
    }

    function collapseAll() {
      userTunedView = false;
      expanded.clear();
      if (rootTree && rootTree.id) expanded.add(rootTree.id);
      redraw();
      fit();
    }

    function onWheel(e) {
      e.preventDefault();
      var pt = contentPointFromClient(e.clientX, e.clientY);
      var factor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
      zoomToward(pt.x, pt.y, factor);
    }

    function onDown(e) {
      if (e.button !== 0) return;
      userTunedView = true;
      dragging = true;
      dragSX = e.clientX;
      dragSY = e.clientY;
      dragTX = tx;
      dragTY = ty;
    }

    function onMove(e) {
      if (!dragging) return;
      tx = dragTX + (e.clientX - dragSX);
      ty = dragTY + (e.clientY - dragSY);
      applyPanZoom();
    }

    function onUp() {
      dragging = false;
    }

    viewport.addEventListener('wheel', onWheel, { passive: false });
    svg.addEventListener('mousedown', onDown);
    global.addEventListener('mousemove', onMove);
    global.addEventListener('mouseup', onUp);

    var roRaf = null;
    var ro =
      typeof ResizeObserver !== 'undefined'
        ? new ResizeObserver(function () {
            if (roRaf) cancelAnimationFrame(roRaf);
            roRaf = requestAnimationFrame(function () {
              roRaf = null;
              if (userTunedView) applyPanZoom();
              else fit();
            });
          })
        : null;
    if (ro) ro.observe(viewport);

    redraw();
    requestAnimationFrame(function () {
      fit();
    });

    return {
      zoomIn: zoomIn,
      zoomOut: zoomOut,
      reset: reset,
      expandAll: expandAll,
      collapseAll: collapseAll,
      destroy: function () {
        viewport.removeEventListener('wheel', onWheel);
        svg.removeEventListener('mousedown', onDown);
        global.removeEventListener('mousemove', onMove);
        global.removeEventListener('mouseup', onUp);
        if (roRaf) cancelAnimationFrame(roRaf);
        if (ro) ro.disconnect();
        if (wrap.parentNode) wrap.parentNode.removeChild(wrap);
      },
    };
  }

  global.CounselorClassicMindmap = {
    mount: mount,
  };
})(typeof window !== 'undefined' ? window : this);
