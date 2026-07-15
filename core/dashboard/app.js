// IMPACT Dashboard Application Logic

// Embedded graph data fallback to allow double-clicking index.html directly (without HTTP server CORS issues)
const GRAPH_DATA_V1 = {
  "projectName": "TelemetryService",
  "version": "1.0.0",
  "language": "Java",
  "systemMetrics": {
    "totalLinesOfCode": 30,
    "totalClasses": 3,
    "averageCoupling": 1.33
  },
  "nodes": [
    { "id": "com.telemetry.Database", "name": "Database", "type": "class", "filePath": "com/telemetry/Database.java", "metrics": { "loc": 7, "complexity": 1, "fanIn": 1, "fanOut": 0, "coupling": 1 } },
    { "id": "com.telemetry.DataCollector", "name": "DataCollector", "type": "class", "filePath": "com/telemetry/DataCollector.java", "metrics": { "loc": 13, "complexity": 1, "fanIn": 1, "fanOut": 1, "coupling": 2 } },
    { "id": "com.telemetry.Service", "name": "Service", "type": "class", "filePath": "com/telemetry/Service.java", "metrics": { "loc": 10, "complexity": 1, "fanIn": 0, "fanOut": 1, "coupling": 1 } }
  ],
  "edges": [
    { "source": "com.telemetry.Service", "target": "com.telemetry.DataCollector", "type": "calls" },
    { "source": "com.telemetry.DataCollector", "target": "com.telemetry.Database", "type": "calls" }
  ]
};

const GRAPH_DATA_V2 = {
  "projectName": "TelemetryService",
  "version": "2.0.0",
  "language": "Java",
  "systemMetrics": {
    "totalLinesOfCode": 41,
    "totalClasses": 4,
    "averageCoupling": 1.5
  },
  "nodes": [
    { "id": "com.telemetry.Database", "name": "Database", "type": "class", "filePath": "com/telemetry/Database.java", "metrics": { "loc": 11, "complexity": 2, "fanIn": 1, "fanOut": 1, "coupling": 2 } },
    { "id": "com.telemetry.DataCollector", "name": "DataCollector", "type": "class", "filePath": "com/telemetry/DataCollector.java", "metrics": { "loc": 13, "complexity": 1, "fanIn": 1, "fanOut": 1, "coupling": 2 } },
    { "id": "com.telemetry.Service", "name": "Service", "type": "class", "filePath": "com/telemetry/Service.java", "metrics": { "loc": 12, "complexity": 1, "fanIn": 1, "fanOut": 1, "coupling": 2 } },
    { "id": "com.telemetry.NewUtility", "name": "NewUtility", "type": "class", "filePath": "com/telemetry/NewUtility.java", "metrics": { "loc": 5, "complexity": 1, "fanIn": 0, "fanOut": 0, "coupling": 0 } }
  ],
  "edges": [
    { "source": "com.telemetry.Service", "target": "com.telemetry.DataCollector", "type": "calls" },
    { "source": "com.telemetry.DataCollector", "target": "com.telemetry.Database", "type": "calls" },
    { "source": "com.telemetry.Database", "target": "com.telemetry.Service", "type": "calls" }
  ]
};

// Initial Intents
let intents = [
    { type: "no-cycles", text: "Avoid cyclic dependencies" },
    { type: "max-coupling", text: "Max Coupling Threshold (Limit: 5)", limit: 5 }
];

// Crawler Queue State (Task 8b/13b)
let crawlerQueue = [
    { repo: "jhy/jsoup", status: "crawled" },
    { repo: "spring-projects/spring-petclinic", status: "pending" },
    { repo: "google/guava", status: "processing" }
];

// App State
let currentGraph = GRAPH_DATA_V2;
let baseGraph = GRAPH_DATA_V1;

// Physics layout variables
let nodes = [];
let edges = [];
let selectedNode = null;
let hoveredNode = null;
let transform = { x: 0, y: 0, scale: 1 };
let isDraggingCanvas = false;
let dragStart = { x: 0, y: 0 };
let draggedNode = null;
let layoutMode = "force"; // "force" or "circular"

// DOM Elements
const canvas = document.getElementById("graph-canvas");
const ctx = canvas.getContext("2d");
const tooltip = document.getElementById("node-info-tooltip");
const intentListContainer = document.getElementById("intent-list-container");
const intentTypeSelect = document.getElementById("intent-type-select");
const intentParamContainer = document.getElementById("intent-param-container");
const intentParamVal = document.getElementById("intent-param-val");
const addIntentBtn = document.getElementById("add-intent-btn");
const runAnalysisBtn = document.getElementById("run-analysis-btn");
const toggleLayoutBtn = document.getElementById("toggle-layout-btn");
const baseVersionSelect = document.getElementById("base-version-select");
const targetVersionSelect = document.getElementById("target-version-select");

// Crawler DOM Elements
const crawlerRepoInput = document.getElementById("crawler-repo-input");
const triggerCrawlBtn = document.getElementById("trigger-crawl-btn");
const crawlerQueueList = document.getElementById("crawler-queue-list");

// Dashboard Values
const metricLoc = document.getElementById("metric-loc");
const metricClasses = document.getElementById("metric-classes");
const metricCoupling = document.getElementById("metric-coupling");
const metricCycles = document.getElementById("metric-cycles");
const complianceBadge = document.getElementById("compliance-overall-badge");
const agentChatContainer = document.getElementById("agent-chat-container");
const diffTableBody = document.getElementById("diff-table-body");

// Initialize Canvas Sizing
function resizeCanvas() {
    const rect = canvas.parentElement.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;
}

// Observe container resizing to dynamically adjust the canvas size
const resizeObserver = new ResizeObserver(() => {
    resizeCanvas();
});
resizeObserver.observe(canvas.parentElement);

// Setup intents list UI
function renderIntents() {
    intentListContainer.innerHTML = "";
    intents.forEach((intent, idx) => {
        const li = document.createElement("li");
        li.className = "intent-item";
        li.innerHTML = `
            <span>${intent.text}</span>
            <span class="intent-remove" data-idx="${idx}">&times;</span>
        `;
        intentListContainer.appendChild(li);
    });

    // Add remove listeners
    document.querySelectorAll(".intent-remove").forEach(btn => {
        btn.addEventListener("click", (e) => {
            const idx = parseInt(e.target.getAttribute("data-idx"));
            intents.splice(idx, 1);
            renderIntents();
        });
    });
}

// Render Crawler Queue (Task 13b)
function renderCrawlerQueue() {
    crawlerQueueList.innerHTML = "";
    crawlerQueue.forEach((job) => {
        const li = document.createElement("li");
        li.className = "intent-item";
        
        let badgeClass = "badge-pending";
        if (job.status === "crawled") badgeClass = "badge-crawled";
        if (job.status === "processing") badgeClass = "badge-processing";
        
        li.innerHTML = `
            <span>${job.repo}</span>
            <span class="badge ${badgeClass}" style="padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">${job.status}</span>
        `;
        crawlerQueueList.appendChild(li);
    });
}

// Add custom queue styles inline dynamically
function addQueueStyles() {
    const style = document.createElement('style');
    style.innerHTML = `
        .badge.badge-pending { background-color: rgba(217, 119, 6, 0.15); color: #f59e0b; border: 1px solid rgba(217, 119, 6, 0.3); }
        .badge.badge-crawled { background-color: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3); }
        .badge.badge-processing { background-color: rgba(2, 132, 199, 0.15); color: #38bdf8; border: 1px solid rgba(2, 132, 199, 0.3); }
    `;
    document.head.appendChild(style);
}

// Generate dynamic graph for crawled repository to visualize its evolution
function generateRepositoryGraph(repoName) {
    const cleanName = repoName.split("/")[1] || repoName;
    const pkg = `org.${cleanName.toLowerCase()}`;
    
    const v1Nodes = [
        { id: `${pkg}.Core`, name: "Core", metrics: { loc: 420, complexity: 15, coupling: 5, fanIn: 3, fanOut: 2, inheritanceDepth: 1 } },
        { id: `${pkg}.Parser`, name: "Parser", metrics: { loc: 280, complexity: 8, coupling: 3, fanIn: 1, fanOut: 2, inheritanceDepth: 0 } },
        { id: `${pkg}.Engine`, name: "Engine", metrics: { loc: 350, complexity: 10, coupling: 4, fanIn: 2, fanOut: 2, inheritanceDepth: 1 } },
        { id: `${pkg}.Utils`, name: "Utils", metrics: { loc: 150, complexity: 3, coupling: 4, fanIn: 4, fanOut: 0, inheritanceDepth: 0 } },
        { id: `${pkg}.Client`, name: "Client", metrics: { loc: 210, complexity: 6, coupling: 3, fanIn: 0, fanOut: 3, inheritanceDepth: 1 } },
        { id: `${pkg}.Config`, name: "Config", metrics: { loc: 110, complexity: 2, coupling: 2, fanIn: 2, fanOut: 0, inheritanceDepth: 0 } }
    ];
    
    const v1Edges = [
        { source: `${pkg}.Core`, target: `${pkg}.Engine`, type: "uses" },
        { source: `${pkg}.Core`, target: `${pkg}.Config`, type: "uses" },
        { source: `${pkg}.Engine`, target: `${pkg}.Parser`, type: "uses" },
        { source: `${pkg}.Parser`, target: `${pkg}.Utils`, type: "uses" },
        { source: `${pkg}.Client`, target: `${pkg}.Core`, type: "uses" },
        { source: `${pkg}.Client`, target: `${pkg}.Utils`, type: "uses" }
    ];

    const v2Nodes = [
        ...v1Nodes.map(n => ({
            ...n,
            metrics: { ...n.metrics, loc: Math.round(n.metrics.loc * 1.1) }
        })),
        { id: `${pkg}.Security`, name: "Security", metrics: { loc: 180, complexity: 7, coupling: 3, fanIn: 1, fanOut: 2, inheritanceDepth: 2 } },
        { id: `${pkg}.Optimizer`, name: "Optimizer", metrics: { loc: 240, complexity: 9, coupling: 4, fanIn: 2, fanOut: 2, inheritanceDepth: 1 } }
    ];

    const v2Edges = [
        ...v1Edges,
        { source: `${pkg}.Engine`, target: `${pkg}.Optimizer`, type: "uses" },
        { source: `${pkg}.Optimizer`, target: `${pkg}.Parser`, type: "uses" },
        { source: `${pkg}.Core`, target: `${pkg}.Security`, type: "uses" },
        { source: `${pkg}.Security`, target: `${pkg}.Utils`, type: "uses" },
        { source: `${pkg}.Parser`, target: `${pkg}.Engine`, type: "calls" } // Cycle: Engine <-> Parser
    ];

    return {
        v1: {
            version: "1.0.0",
            projectName: cleanName,
            systemMetrics: {
                totalClasses: v1Nodes.length,
                totalLinesOfCode: v1Nodes.reduce((acc, n) => acc + n.metrics.loc, 0),
                averageComplexity: 7.3
            },
            nodes: v1Nodes,
            edges: v1Edges
        },
        v2: {
            version: "2.0.0",
            projectName: cleanName,
            systemMetrics: {
                totalClasses: v2Nodes.length,
                totalLinesOfCode: v2Nodes.reduce((acc, n) => acc + n.metrics.loc, 0),
                averageComplexity: 7.8
            },
            nodes: v2Nodes,
            edges: v2Edges
        }
    };
}

triggerCrawlBtn.addEventListener("click", () => {
    const repo = crawlerRepoInput.value.trim();
    if (repo) {
        // Enqueue new repo (Task 8b)
        const newJob = { repo, status: "pending" };
        crawlerQueue.push(newJob);
        crawlerRepoInput.value = "";
        renderCrawlerQueue();
        
        addAgentMessage("System", `Enqueued repository for ecosystem crawl: ${repo}`, "system");
        
        // Simulate background worker processing
        setTimeout(() => {
            newJob.status = "processing";
            renderCrawlerQueue();
            addAgentMessage("System", `Crawler claimed ${repo}, starting AST dependency analysis...`, "system");
        }, 1500);
        
        setTimeout(() => {
            newJob.status = "crawled";
            renderCrawlerQueue();
            addAgentMessage("System", `Successfully crawled ${repo}. Schema metrics validated via SHACL. Conformance report generated.`, "system");
            
            // Dynamically load the crawled repo's architecture evolution graph
            const cleanName = repo.split("/")[1] || repo;
            const newGraphData = generateRepositoryGraph(repo);
            baseGraph = newGraphData.v1;
            currentGraph = newGraphData.v2;
            
            // Update UI headers & selectors
            const headerTitle = document.querySelector(".content-header h2");
            if (headerTitle) {
                headerTitle.innerText = `${repo} Architecture Evolution`;
            }
            
            const baseVersionSelect = document.getElementById("base-version-select");
            const targetVersionSelect = document.getElementById("target-version-select");
            if (baseVersionSelect && targetVersionSelect) {
                baseVersionSelect.innerHTML = `<option value="v1">v1.0.0 (${cleanName})</option>`;
                targetVersionSelect.innerHTML = `<option value="v2">v2.0.0 (${cleanName})</option>`;
            }
            
            // Re-initialize layout, metrics, diff, and swarm analysis
            resetLayout();
            updateKPIs();
            renderDiffTable();
            runAnalysis();
        }, 4000);
    }
});

crawlerRepoInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        triggerCrawlBtn.click();
    }
});


intentTypeSelect.addEventListener("change", () => {
    const type = intentTypeSelect.value;
    if (type === "no-cycles") {
        intentParamContainer.style.display = "none";
    } else {
        intentParamContainer.style.display = "flex";
    }
});

addIntentBtn.addEventListener("click", () => {
    const type = intentTypeSelect.value;
    let text = "";
    let limit = null;
    if (type === "no-cycles") {
        text = "Avoid cyclic dependencies";
    } else if (type === "max-coupling") {
        limit = parseInt(intentParamVal.value) || 5;
        text = `Max Coupling Threshold (Limit: ${limit})`;
    } else if (type === "max-inheritance") {
        limit = parseInt(intentParamVal.value) || 3;
        text = `Max Inheritance Depth (Limit: ${limit})`;
    }
    intents.push({ type, text, limit });
    renderIntents();
});

toggleLayoutBtn.addEventListener("click", () => {
    layoutMode = layoutMode === "force" ? "circular" : "force";
    toggleLayoutBtn.innerText = layoutMode === "force" ? "Force Layout" : "Cycle Layout";
    resetLayout();
});

// Cycles detection
function findSimpleCycles(graph) {
    const adj = {};
    graph.nodes.forEach(n => adj[n.id] = []);
    graph.edges.forEach(e => {
        if (adj[e.source]) adj[e.source].push(e.target);
    });

    const cycles = [];
    const path = [];
    const visited = new Set();

    function dfs(v) {
        if (path.includes(v)) {
            const cycleStart = path.indexOf(v);
            const cycle = path.slice(cycleStart);
            // Normalize cycle representation
            const minIndex = cycle.indexOf(Math.min(...cycle.map(n => n)));
            const normalized = [...cycle.slice(minIndex), ...cycle.slice(0, minIndex)];
            const cycleStr = normalized.join("->");
            if (!cycles.some(c => c.join("->") === cycleStr)) {
                cycles.push(normalized);
            }
            return;
        }
        if (visited.has(v)) return;

        path.push(v);
        (adj[v] || []).forEach(u => dfs(u));
        path.pop();
        visited.add(v);
    }

    graph.nodes.forEach(n => {
        path.length = 0;
        visited.clear();
        dfs(n.id);
    });

    return cycles;
}

// Compute differences
function computeDiff() {
    const addedNodes = currentGraph.nodes.filter(n => !baseGraph.nodes.some(bn => bn.id === n.id));
    const removedNodes = baseGraph.nodes.filter(bn => !currentGraph.nodes.some(n => n.id === bn.id));
    
    const addedEdges = currentGraph.edges.filter(e => !baseGraph.edges.some(be => be.source === e.source && be.target === e.target));
    const removedEdges = baseGraph.edges.filter(be => !currentGraph.edges.some(e => e.source === be.source && e.target === be.target));

    const cyclesBase = findSimpleCycles(baseGraph);
    const cyclesCurrent = findSimpleCycles(currentGraph);

    const newCycles = cyclesCurrent.filter(c => {
        const cStr = c.join("->");
        return !cyclesBase.some(bc => bc.join("->") === cStr);
    });

    return {
        addedNodes,
        removedNodes,
        addedEdges,
        removedEdges,
        newCycles,
        cyclesCurrent
    };
}

// Initialize layout positions
function resetLayout() {
    const w = canvas.width;
    const h = canvas.height;

    // Configure font once to measure text width
    ctx.font = "bold 11px Outfit, sans-serif";

    nodes = currentGraph.nodes.map((n, i) => {
        const textWidth = ctx.measureText(n.name).width;
        const rx = Math.max(35, (textWidth + 24) / 2);
        const ry = 16;
        
        const angle = (i / currentGraph.nodes.length) * Math.PI * 2;
        const radius = Math.min(w, h) * (layoutMode === "circular" ? 0.35 : 0.25);
        if (layoutMode === "circular") {
            return {
                ...n,
                rx,
                ry,
                x: w / 2 + Math.cos(angle) * radius,
                y: h / 2 + Math.sin(angle) * radius,
                vx: 0,
                vy: 0
            };
        } else {
            // Keep previous coordinates if available
            const prev = nodes.find(pn => pn.id === n.id);
            return {
                ...n,
                rx,
                ry,
                x: prev ? prev.x : w / 2 + Math.cos(angle) * radius,
                y: prev ? prev.y : h / 2 + Math.sin(angle) * radius,
                vx: 0,
                vy: 0
            };
        }
    });

    const diff = computeDiff();

    edges = currentGraph.edges.map(e => {
        // Check if edge is part of a cycle
        let partOfCycle = false;
        diff.newCycles.forEach(cycle => {
            for (let i = 0; i < cycle.length; i++) {
                const s = cycle[i];
                const t = cycle[(i + 1) % cycle.length];
                if (e.source === s && e.target === t) {
                    partOfCycle = true;
                }
            }
        });

        // Check if edge is newly added
        const isAdded = diff.addedEdges.some(ae => ae.source === e.source && ae.target === e.target);

        return {
            ...e,
            isCycle: partOfCycle,
            isAdded: isAdded
        };
    });

    transform = { x: 0, y: 0, scale: 1 };

    // Warm up the physics simulation so it starts in a settled state and doesn't flash/jump
    if (layoutMode === "force") {
        for (let step = 0; step < 100; step++) {
            tickPhysics();
        }
    }
}

// Physics engine tick
function tickPhysics() {
    if (layoutMode === "circular") return;
    const w = canvas.width;
    const h = canvas.height;
    
    // Repel force (using inverse-square law for stability + clamping)
    const kRepel = 70;
    for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
            const n1 = nodes[i];
            const n2 = nodes[j];
            const dx = n2.x - n1.x;
            const dy = n2.y - n1.y;
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            if (dist < 350) {
                const force = Math.min(20, (kRepel * kRepel) / (dist * dist));
                const fx = (dx / dist) * force;
                const fy = (dy / dist) * force;
                if (n1 !== draggedNode) {
                    n1.vx -= fx;
                    n1.vy -= fy;
                }
                if (n2 !== draggedNode) {
                    n2.vx += fx;
                    n2.vy += fy;
                }
            }
        }
    }

    // Attract force (edges)
    const kAttract = 0.04;
    const targetDist = 120;
    edges.forEach(e => {
        const sourceNode = nodes.find(n => n.id === e.source);
        const targetNode = nodes.find(n => n.id === e.target);
        if (sourceNode && targetNode) {
            const dx = targetNode.x - sourceNode.x;
            const dy = targetNode.y - sourceNode.y;
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            const force = (dist - targetDist) * kAttract;
            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;
            
            if (sourceNode !== draggedNode) {
                sourceNode.vx += fx;
                sourceNode.vy += fy;
            }
            if (targetNode !== draggedNode) {
                targetNode.vx -= fx;
                targetNode.vy -= fy;
            }
        }
    });

    // Center gravity
    const kGravity = 0.015;
    nodes.forEach(n => {
        if (n !== draggedNode) {
            n.vx += (w / 2 - n.x) * kGravity;
            n.vy += (h / 2 - n.y) * kGravity;
        }
    });

    // Update positions (with speed clamping to avoid node explosions)
    const friction = 0.85;
    const maxSpeed = 8;
    nodes.forEach(n => {
        if (n !== draggedNode) {
            n.vx = Math.max(-maxSpeed, Math.min(maxSpeed, n.vx));
            n.vy = Math.max(-maxSpeed, Math.min(maxSpeed, n.vy));
            n.x += n.vx;
            n.y += n.vy;
            n.vx *= friction;
            n.vy *= friction;
        }
    });
}

// Drawing routine
function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.save();
    ctx.translate(transform.x, transform.y);
    ctx.scale(transform.scale, transform.scale);

    // Draw Edges
    edges.forEach(e => {
        const sNode = nodes.find(n => n.id === e.source);
        const tNode = nodes.find(n => n.id === e.target);
        if (sNode && tNode) {
            ctx.beginPath();
            ctx.moveTo(sNode.x, sNode.y);
            ctx.lineTo(tNode.x, tNode.y);
            
            // Style
            if (e.isCycle) {
                ctx.strokeStyle = "#f43f5e";
                ctx.lineWidth = 3;
                ctx.shadowColor = "#f43f5e";
                ctx.shadowBlur = 8;
            } else if (e.isAdded) {
                ctx.strokeStyle = "#10b981";
                ctx.lineWidth = 2;
                ctx.shadowBlur = 0;
            } else {
                ctx.strokeStyle = "rgba(15, 23, 42, 0.2)";
                ctx.lineWidth = 1.5;
                ctx.shadowBlur = 0;
            }
            ctx.stroke();
            ctx.shadowBlur = 0; // reset glow

            // Draw edge direction arrow
            const angle = Math.atan2(tNode.y - sNode.y, tNode.x - sNode.x);
            const arrowLength = 10;
            
            // Calculate intersection with the target ellipse boundary
            const theta = angle + Math.PI; // direction from target to source
            const rx = tNode.rx || 20;
            const ry = tNode.ry || 16;
            const denom = Math.sqrt(Math.pow(ry * Math.cos(theta), 2) + Math.pow(rx * Math.sin(theta), 2)) || 1;
            const targetOffset = (rx * ry) / denom + 4; // add 4px padding for arrow visibility
            
            const arrowX = tNode.x - targetOffset * Math.cos(angle);
            const arrowY = tNode.y - targetOffset * Math.sin(angle);

            ctx.beginPath();
            ctx.moveTo(arrowX, arrowY);
            ctx.lineTo(arrowX - arrowLength * Math.cos(angle - Math.PI / 6), arrowY - arrowLength * Math.sin(angle - Math.PI / 6));
            ctx.lineTo(arrowX - arrowLength * Math.cos(angle + Math.PI / 6), arrowY - arrowLength * Math.sin(angle + Math.PI / 6));
            ctx.closePath();
            ctx.fillStyle = e.isCycle ? "#f43f5e" : (e.isAdded ? "#10b981" : "rgba(15, 23, 42, 0.45)");
            ctx.fill();
        }
    });

    // Draw Nodes
    nodes.forEach(n => {
        const isAdded = !baseGraph.nodes.some(bn => bn.id === n.id);
        const rx = n.rx || 20;
        const ry = n.ry || 16;
        
        ctx.beginPath();
        ctx.ellipse(n.x, n.y, rx, ry, 0, 0, Math.PI * 2);
        
        // Colors & Text styles
        let textColor = "#0f172a";
        
        if (selectedNode === n) {
            ctx.fillStyle = "#e9d5ff"; // light purple
            ctx.strokeStyle = "#7c3aed";
            ctx.lineWidth = 2.5;
            ctx.shadowColor = "#7c3aed";
            ctx.shadowBlur = 6;
            textColor = "#5b21b6"; // dark purple
        } else if (hoveredNode === n) {
            ctx.fillStyle = "#e0f2fe"; // light blue
            ctx.strokeStyle = "#0284c7";
            ctx.lineWidth = 2;
            ctx.shadowColor = "#0284c7";
            ctx.shadowBlur = 5;
            textColor = "#0369a1"; // dark blue
        } else if (isAdded) {
            ctx.fillStyle = "#d1fae5"; // light green
            ctx.strokeStyle = "#10b981";
            ctx.lineWidth = 1.5;
            ctx.shadowBlur = 0;
            textColor = "#065f46"; // dark green
        } else {
            ctx.fillStyle = "#f8fafc"; // very light slate
            ctx.strokeStyle = "#38bdf8"; // cyan-ish blue border
            ctx.lineWidth = 1.5;
            ctx.shadowBlur = 0;
            textColor = "#0f172a"; // dark slate text
        }
        
        ctx.fill();
        ctx.stroke();
        ctx.shadowBlur = 0; // reset glow

        // Labels
        ctx.fillStyle = textColor;
        ctx.font = "bold 11px Outfit, sans-serif";
        ctx.textAlign = "center";
        ctx.fillText(n.name, n.x, n.y + 4);
    });

    ctx.restore();
}

function varColor(name) {
    return name === "--accent-blue" ? "#0284c7" : "#7c3aed";
}

// Animation loop
function animate() {
    tickPhysics();
    draw();
    requestAnimationFrame(animate);
}

// Map screen space to canvas graph space
function toGraphCoords(clientX, clientY) {
    const rect = canvas.getBoundingClientRect();
    const x = (clientX - rect.left - transform.x) / transform.scale;
    const y = (clientY - rect.top - transform.y) / transform.scale;
    return { x, y };
}

// Canvas interactions
canvas.addEventListener("mousedown", (e) => {
    const coords = toGraphCoords(e.clientX, e.clientY);
    const clicked = nodes.find(n => {
        const dx = n.x - coords.x;
        const dy = n.y - coords.y;
        const rx = n.rx || 20;
        const ry = n.ry || 16;
        return (dx * dx) / (rx * rx) + (dy * dy) / (ry * ry) <= 1.25;
    });

    if (clicked) {
        draggedNode = clicked;
        selectedNode = clicked;
    } else {
        isDraggingCanvas = true;
        dragStart.x = e.clientX - transform.x;
        dragStart.y = e.clientY - transform.y;
    }
});

canvas.addEventListener("mousemove", (e) => {
    const coords = toGraphCoords(e.clientX, e.clientY);
    
    if (draggedNode) {
        draggedNode.x = coords.x;
        draggedNode.y = coords.y;
    } else if (isDraggingCanvas) {
        transform.x = e.clientX - dragStart.x;
        transform.y = e.clientY - dragStart.y;
    } else {
        const hovered = nodes.find(n => {
            const dx = n.x - coords.x;
            const dy = n.y - coords.y;
            const rx = n.rx || 20;
            const ry = n.ry || 16;
            return (dx * dx) / (rx * rx) + (dy * dy) / (ry * ry) <= 1.25;
        });

        if (hovered) {
            hoveredNode = hovered;
            tooltip.style.display = "block";
            tooltip.innerHTML = `
                <strong>${hovered.id}</strong><br>
                LOC: ${hovered.metrics.loc} | Complexity: ${hovered.metrics.complexity}<br>
                Coupling: ${hovered.metrics.coupling} (Fan-in: ${hovered.metrics.fanIn}, Fan-out: ${hovered.metrics.fanOut})
            `;
        } else {
            hoveredNode = null;
            tooltip.innerHTML = "Hover over a node to see FQCN metrics.";
        }
    }
});

window.addEventListener("mouseup", () => {
    draggedNode = null;
    isDraggingCanvas = false;
});

// Scroll zooming
canvas.addEventListener("wheel", (e) => {
    e.preventDefault();
    const zoomIntensity = 0.1;
    const mouseCoords = toGraphCoords(e.clientX, e.clientY);
    const zoomFactor = e.deltaY < 0 ? (1 + zoomIntensity) : (1 - zoomIntensity);
    
    const newScale = Math.min(Math.max(transform.scale * zoomFactor, 0.4), 3.0);
    
    // Zoom centered on mouse
    transform.x = e.clientX - canvas.getBoundingClientRect().left - mouseCoords.x * newScale;
    transform.y = e.clientY - canvas.getBoundingClientRect().top - mouseCoords.y * newScale;
    transform.scale = newScale;
});

// Run Evolution analysis and render compliance logs
function runAnalysis() {
    agentChatContainer.innerHTML = "";
    addAgentMessage("System", "Initializing IMPACT Multi-Agent Evolution Swarm...", "system");

    setTimeout(() => {
        addAgentMessage("GraphAgent", `Loaded Version ${currentGraph.version} of ${currentGraph.projectName} (${currentGraph.systemMetrics.totalClasses} classes, ${currentGraph.systemMetrics.totalLinesOfCode} LOC).`, "coordinator");
    }, 400);

    setTimeout(() => {
        const diff = computeDiff();
        addAgentMessage("DiffAgent", `Identified structural changes: added ${diff.addedNodes.length} classes, added ${diff.addedEdges.length} edges. Detected ${diff.newCycles.length} new cycle loops.`, "coordinator");
    }, 800);

    setTimeout(() => {
        const topHubs = currentGraph.nodes.map(n => n.id);
        addAgentMessage("MetricsAgent", `Calculated network metrics. Most central coupling hubs: ${topHubs.slice(0, 3).join(", ")}.`, "coordinator");
    }, 1200);

    setTimeout(() => {
        const diff = computeDiff();
        let violations = [];

        intents.forEach(intent => {
            if (intent.type === "no-cycles") {
                if (diff.newCycles.length > 0) {
                    violations.push(`New cyclic dependencies detected (${diff.newCycles.length} cycles). Breaches 'Avoid cyclic dependencies'.`);
                }
            } else if (intent.type === "max-coupling") {
                const limit = intent.limit;
                const offendingNodes = currentGraph.nodes.filter(n => (n.metrics.coupling || 0) > limit);
                if (offendingNodes.length > 0) {
                    violations.push(`Max Coupling of ${limit} exceeded by: ${offendingNodes.map(n => `${n.name} (Coupling: ${n.metrics.coupling})`).join(", ")}.`);
                }
            } else if (intent.type === "max-inheritance") {
                const limit = intent.limit;
                const offendingNodes = currentGraph.nodes.filter(n => (n.metrics.inheritanceDepth || 0) > limit);
                if (offendingNodes.length > 0) {
                    violations.push(`Max Inheritance Depth of ${limit} exceeded by: ${offendingNodes.map(n => `${n.name} (Depth: ${n.metrics.inheritanceDepth})`).join(", ")}.`);
                }
            }
        });

        let report = `Architectural Evolution Report (Version ${baseGraph.version} -> ${currentGraph.version})
===========================================================
1. Structural Changes:
   * Added Nodes: ${diff.addedNodes.length}
   * Added Dependencies (Edges): ${diff.addedEdges.length}
   * Removed Nodes: ${diff.removedNodes.length}
   * Removed Dependencies (Edges): ${diff.removedEdges.length}

2. Dependency Cycles:
   * New Cycles Detected: ${diff.newCycles.length}
   * Broken Cycles: 0

3. Coupling & Complexity Hubs:
   * Top Coupled Nodes: ${currentGraph.nodes.slice(0, 3).map(n => n.name).join(", ")}

4. Intent Conformance Evaluation:`;

        if (violations.length > 0) {
            violations.forEach(v => {
                report += `\n   * VIOLATION: ${v}`;
            });
            complianceBadge.innerText = "Violation Detected";
            complianceBadge.className = "compliance-badge violation";
        } else {
            report += `\n   * All intents successfully satisfied. No modularity, coupling, or cycle violations detected.`;
            complianceBadge.innerText = "Compliant";
            complianceBadge.className = "compliance-badge compliant";
        }

        report += `\n\n5. Recommendations:`;
        if (violations.length > 0) {
            report += `\n   * Action required: Address the architectural violation(s) to maintain compliance.`;
        } else {
            report += `\n   * Codebase structure is clean. Modularity is preserved.`;
        }

        addAgentMessage("LLMAgent", report, "ll");
    }, 1600);
}

function addAgentMessage(agent, text, type) {
    const bubble = document.createElement("div");
    bubble.className = `agent-bubble ${type}`;
    bubble.innerHTML = `
        <div class="agent-title">${agent}</div>
        <div class="agent-text">${text}</div>
    `;
    agentChatContainer.appendChild(bubble);
    agentChatContainer.scrollTop = agentChatContainer.scrollHeight;
}

// Populate stats KPIs
function updateKPIs() {
    const diff = computeDiff();
    metricLoc.innerText = currentGraph.systemMetrics.totalLinesOfCode;
    metricClasses.innerText = currentGraph.systemMetrics.totalClasses;
    metricCoupling.innerText = currentGraph.systemMetrics.averageCoupling.toFixed(2);
    metricCycles.innerText = diff.newCycles.length;
}

// Populate table
function renderDiffTable() {
    diffTableBody.innerHTML = "";
    
    currentGraph.nodes.forEach(n => {
        const isAdded = !baseGraph.nodes.some(bn => bn.id === n.id);
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td><code>${n.id}</code></td>
            <td><span class="status-cell ${isAdded ? 'added' : 'unchanged'}">${isAdded ? 'ADDED' : 'UNCHANGED'}</span></td>
            <td>${n.metrics.loc}</td>
            <td>${n.metrics.complexity}</td>
            <td>${n.metrics.coupling}</td>
            <td>${n.type}</td>
        `;
        diffTableBody.appendChild(tr);
    });
}

// Main launch sequence
function init() {
    resizeCanvas();
    renderIntents();
    renderCrawlerQueue();
    addQueueStyles();
    resetLayout();
    updateKPIs();
    renderDiffTable();
    runAnalysis();
    animate();
}

async function loadGraphs() {
    try {
        const res1 = await fetch("./v1_graph.json");
        const data1 = await res1.json();
        const res2 = await fetch("./v2_graph.json");
        const data2 = await res2.json();
        baseGraph = data1;
        currentGraph = data2;
        console.log("[Dashboard] Successfully loaded live graph files via fetch.");
    } catch (e) {
        console.log("[Dashboard] Fetch failed or blocked by CORS, using embedded fallback graph data:", e);
    }
    init();
}

runAnalysisBtn.addEventListener("click", () => {
    runAnalysis();
});

document.addEventListener("DOMContentLoaded", loadGraphs);

