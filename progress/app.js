/* Dependency-free, read-only snapshot viewer. */
(function () {
  "use strict";
  const statuses = {
    done: "Done",
    active: "In progress",
    blocked: "Blocked",
    todo: "Remaining",
  };
  function layoutGraph(nodes) {
    const byId = new Map(nodes.map((n) => [n.id, n]));
    if (byId.size !== nodes.length)
      throw new Error("Snapshot contains duplicate task IDs.");
    const depths = new Map(),
      visiting = new Set();
    function depth(id) {
      if (depths.has(id)) return depths.get(id);
      if (visiting.has(id))
        throw new Error(
          "Snapshot contains a dependency cycle. Use the task list to inspect it.",
        );
      const node = byId.get(id);
      if (!node)
        throw new Error("Snapshot references an unknown dependency: " + id);
      visiting.add(id);
      const value = Math.max(
        0,
        ...(node.depends_on || []).map((d) => depth(d) + 1),
      );
      visiting.delete(id);
      depths.set(id, value);
      return value;
    }
    nodes.forEach((n) => depth(n.id));
    const rows = new Map();
    const positions = nodes.map((n) => {
      const tier = depths.get(n.id),
        row = rows.get(tier) || 0;
      rows.set(tier, row + 1);
      return { ...n, tier, x: 26 + tier * 298, y: 56 + row * 168 };
    });
    return {
      positions,
      width: Math.max(640, rows.size * 298 + 20),
      height: Math.max(300, ...Array.from(rows.values(), (r) => r * 168 + 63)),
      tiers: rows.size,
    };
  }
  function safeURL(value) {
    try {
      const url = new URL(value);
      return ["http:", "https:"].includes(url.protocol) ? url.href : null;
    } catch {
      return null;
    }
  }
  if (typeof module !== "undefined") module.exports = { layoutGraph, safeURL };
  if (typeof document === "undefined") return;
  const $ = (id) => document.getElementById(id);
  let snapshot = null,
    status = "all",
    query = "",
    view = window.innerWidth <= 720 ? "list" : "graph";
  const element = (tag, className, content) => {
    const e = document.createElement(tag);
    if (className) e.className = className;
    if (content !== undefined) e.textContent = content;
    return e;
  };
  function link(label, url, cls) {
    const safe = safeURL(url),
      a = element(safe ? "a" : "span", cls, label);
    if (safe) {
      a.href = safe;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
    }
    return a;
  }
  function date(value) {
    const d = new Date(value);
    return Number.isNaN(d.getTime())
      ? value || "Not recorded"
      : d.toLocaleString([], {
          month: "short",
          day: "numeric",
          hour: "numeric",
          minute: "2-digit",
        });
  }
  function badge(value) {
    return element(
      "span",
      "badge " + (statuses[value] ? value : "todo"),
      statuses[value] || "Unclassified",
    );
  }
  function showDetails(node, alreadyOpen = false) {
    const content = $("detail-content");
    content.replaceChildren(
      badge(node.status),
      element("h2", "", node.title),
      element(
        "div",
        "detail-owner",
        (node.stream || "Workstream") +
          " / " +
          (node.owner || "Owner not recorded"),
      ),
      element("p", "", node.summary || ""),
    );
    if (node.detail)
      content.append(
        element("h3", "", "Recorded evidence"),
        element(
          "p",
          "",
          typeof node.detail === "string"
            ? node.detail
            : JSON.stringify(node.detail, null, 2),
        ),
      );
    if (node.next_action) {
      content.append(
        element(
          "h3",
          "",
          node.status === "blocked" ? "Blocker / next action" : "Next action",
        ),
        element("p", "next-action", node.next_action),
      );
    }
    content.append(element("h3", "", "Depends on"));
    const deps = node.depends_on || [];
    if (!deps.length)
      content.append(element("p", "", "No prerequisites recorded."));
    deps.forEach((id) => {
      const target = snapshot.nodes.find((n) => n.id === id);
      const b = element(
        "button",
        "dependency-button",
        target
          ? target.title + " — " + (statuses[target.status] || target.status)
          : id,
      );
      if (target) b.onclick = () => showDetails(target, true);
      content.append(b);
    });
    const following = snapshot.nodes.filter((n) =>
      (n.depends_on || []).includes(node.id),
    );
    if (following.length) {
      content.append(element("h3", "", "Enables"));
      following.forEach((n) => {
        const b = element("button", "dependency-button", n.title);
        b.onclick = () => showDetails(n, true);
        content.append(b);
      });
    }
    if ((node.links || []).length) {
      content.append(element("h3", "", "Source links"));
      const links = element("div", "detail-links");
      node.links.forEach((l) => links.append(link(l.label, l.url)));
      content.append(links);
    }
    if (!alreadyOpen) $("detail").showModal();
  }
  function matches(n) {
    return (
      (status === "all" || n.status === status) &&
      [n.title, n.summary, n.stream, n.owner, n.detail, n.next_action]
        .join(" ")
        .toLowerCase()
        .includes(query)
    );
  }
  function render() {
    if (!snapshot) return;
    const nodes = snapshot.nodes,
      visible = nodes.filter(matches);
    $("filters").replaceChildren();
    Object.entries({ all: "All work", ...statuses }).forEach(([key, label]) => {
      const count =
        key === "all"
          ? nodes.length
          : nodes.filter((n) => n.status === key).length;
      const b = element("button", "", label);
      b.append(element("b", "", count));
      b.setAttribute("aria-pressed", String(status === key));
      b.onclick = () => {
        status = key;
        render();
      };
      $("filters").append(b);
    });
    $("visible-count").textContent =
      `${visible.length} of ${nodes.length} tasks`;
    $("graph-scroll").hidden = view !== "graph";
    $("task-list").hidden = view !== "list";
    $("graph-view").setAttribute("aria-pressed", String(view === "graph"));
    $("list-view").setAttribute("aria-pressed", String(view === "list"));
    const graph = $("graph");
    graph.replaceChildren();
    try {
      const layout = layoutGraph(nodes),
        selected = new Set(visible.map((n) => n.id));
      graph.style.width = layout.width + "px";
      graph.style.height = layout.height + "px";
      for (let tier = 0; tier < layout.tiers; tier++) {
        const label = element(
          "div",
          "tier-label",
          tier === 0 ? "Foundation" : `Dependency level ${tier}`,
        );
        label.style.left = 26 + tier * 298 + "px";
        graph.append(label);
      }
      const ns = "http://www.w3.org/2000/svg",
        svg = document.createElementNS(ns, "svg");
      svg.classList.add("edges");
      svg.setAttribute("width", layout.width);
      svg.setAttribute("height", layout.height);
      svg.setAttribute("aria-hidden", "true");
      const defs = document.createElementNS(ns, "defs"),
        marker = document.createElementNS(ns, "marker");
      marker.id = "arrow";
      marker.setAttribute("viewBox", "0 0 10 10");
      marker.setAttribute("refX", "9");
      marker.setAttribute("refY", "5");
      marker.setAttribute("markerWidth", "6");
      marker.setAttribute("markerHeight", "6");
      marker.setAttribute("orient", "auto");
      const arrow = document.createElementNS(ns, "path");
      arrow.setAttribute("d", "M 0 0 L 10 5 L 0 10 z");
      arrow.setAttribute("fill", "#a8b18e");
      marker.append(arrow);
      defs.append(marker);
      svg.append(defs);
      const positions = new Map(layout.positions.map((n) => [n.id, n]));
      layout.positions.forEach((n) =>
        (n.depends_on || []).forEach((id) => {
          if (!selected.has(id) || !selected.has(n.id)) return;
          const from = positions.get(id),
            x = from.x + 238,
            y = from.y + 69,
            endX = n.x,
            endY = n.y + 69;
          const path = document.createElementNS(ns, "path");
          path.setAttribute(
            "d",
            `M ${x} ${y} C ${x + 40} ${y}, ${endX - 40} ${endY}, ${endX - 5} ${endY}`,
          );
          path.setAttribute("fill", "none");
          path.setAttribute("stroke", "#b1b99d");
          path.setAttribute("stroke-width", "1.5");
          path.setAttribute("marker-end", "url(#arrow)");
          svg.append(path);
        }),
      );
      graph.append(svg);
      layout.positions
        .filter((n) => selected.has(n.id))
        .forEach((n) => {
          const b = element("button", "graph-node");
          b.style.left = n.x + "px";
          b.style.top = n.y + "px";
          b.setAttribute(
            "aria-label",
            `${n.title}, ${statuses[n.status] || n.status}. Open details`,
          );
          const top = element("div", "node-top");
          top.append(
            element("span", "stream", n.stream || ""),
            badge(n.status),
          );
          b.append(
            top,
            element("h3", "", n.title),
            element("p", "", n.summary || ""),
          );
          b.onclick = () => showDetails(n);
          graph.append(b);
        });
      if (!visible.length)
        graph.append(
          element(
            "p",
            "empty",
            "No tasks match these filters. Clear the search or select All work.",
          ),
        );
    } catch (error) {
      graph.append(element("p", "empty", error.message));
    }
    const table = element("table", "task-table"),
      head = element("thead"),
      hr = element("tr");
    ["Task / workstream", "Status", "Dependencies", "Owner"].forEach((t) =>
      hr.append(element("th", "", t)),
    );
    head.append(hr);
    table.append(head);
    const body = element("tbody");
    visible.forEach((n) => {
      const row = element("tr"),
        name = element("td"),
        b = element("button", "", n.title);
      b.onclick = () => showDetails(n);
      name.append(b, element("small", "", n.stream || ""));
      const state = element("td");
      state.append(badge(n.status));
      row.append(
        name,
        state,
        element("td", "", (n.depends_on || []).length),
        element("td", "", n.owner || "—"),
      );
      body.append(row);
    });
    table.append(body);
    $("task-list").replaceChildren(
      visible.length
        ? table
        : element("p", "empty", "No tasks match these filters."),
    );
  }
  async function refresh() {
    $("refresh").disabled = true;
    try {
      const response = await fetch("data.json?t=" + Date.now(), {
        cache: "no-store",
      });
      if (!response.ok)
        throw new Error(`Snapshot unavailable (HTTP ${response.status}).`);
      const data = await response.json();
      if (!Array.isArray(data.nodes))
        throw new Error("Snapshot must contain a nodes array.");
      snapshot = data;
      $("headline").textContent = data.headline || "The path to delivery.";
      $("summary").textContent = data.summary || "";
      $("updated").textContent = date(data.updated_at);
      $("read-at").textContent =
        "Read locally " + date(new Date().toISOString());
      for (const [id, url] of [
        ["repo-link", data.repository_url],
        ["app-link", data.application_url],
      ]) {
        const safe = safeURL(url);
        if (safe) $(id).href = safe;
      }
      $("evidence").replaceChildren();
      (data.evidence || []).forEach((e) => {
        const item = link("", e.url, "evidence-item");
        item.append(
          element("span", "", e.label),
          element("strong", "", e.value),
          element("small", "", e.detail || ""),
        );
        $("evidence").append(item);
      });
      $("activity").replaceChildren();
      (data.activity || []).forEach((a) => {
        const row = element("div", "activity-row"),
          copy = element("div");
        copy.append(link(a.title, a.url), element("p", "", a.detail || ""));
        row.append(element("time", "", date(a.at)), copy);
        $("activity").append(row);
      });
      $("notice").textContent = "";
      render();
    } catch (error) {
      $("notice").textContent =
        error.message +
        " " +
        (snapshot
          ? "The previous snapshot remains visible."
          : "Place the evidence snapshot at progress/data.json and refresh.");
    } finally {
      $("refresh").disabled = false;
    }
  }
  $("expand-graph").onclick = () => {
    const expanded = document.body.classList.toggle("graph-expanded");
    $("expand-graph").setAttribute("aria-pressed", String(expanded));
    $("expand-graph").textContent = expanded
      ? "Exit expanded view"
      : "Expand graph";
  };
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !$("detail").open) {
      document.body.classList.remove("graph-expanded");
      $("expand-graph").setAttribute("aria-pressed", "false");
      $("expand-graph").textContent = "Expand graph";
    }
  });
  $("refresh").onclick = refresh;
  $("search").oninput = (e) => {
    query = e.target.value.toLowerCase().trim();
    render();
  };
  $("graph-view").onclick = () => {
    view = "graph";
    render();
  };
  $("list-view").onclick = () => {
    view = "list";
    render();
  };
  $("close-detail").onclick = () => $("detail").close();
  $("detail").addEventListener("click", (e) => {
    if (
      e.target === $("detail") &&
      e.clientX < $("detail").getBoundingClientRect().left
    )
      $("detail").close();
  });
  refresh();
})();
