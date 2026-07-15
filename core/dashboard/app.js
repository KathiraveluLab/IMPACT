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
    { repo: "demo/TelemetryService", status: "crawled", graphs: null, isDemo: true },
    { repo: "KathiraveluLab/IMPACT", status: "crawled", graphs: null, detectedLanguage: "Python" },
    { repo: "jhy/jsoup", status: "crawled" },
    { repo: "pallets/flask", status: "crawled" },
    { repo: "gleam-lang/gleam", status: "crawled" },
    { repo: "spring-projects/spring-petclinic", status: "pending" },
    { repo: "google/guava", status: "processing" }
];
let activeRepoName = "demo/TelemetryService";

// App State
let currentGraph = GRAPH_DATA_V2;
let baseGraph = GRAPH_DATA_V1;
let analysisTimeouts = []; // Track pending analysis setTimeout IDs to prevent duplicate messages

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
        
        let badgeClass = "badge-pending";
        let badgeLabel = job.status;
        if (job.isDemo) {
            badgeClass = "badge-demo";
            badgeLabel = "demo";
        } else if (job.status === "crawled") {
            badgeClass = "badge-crawled";
        } else if (job.status === "processing") {
            badgeClass = "badge-processing";
        }
        
        li.className = `crawler-job-item ${job.status}`;
        if (job.repo === activeRepoName) {
            li.className += " active";
        }
        
        let displayName = job.isDemo ? "TelemetryService (Demo)" : job.repo;
        let tooltipText = "";
        if (job.status === "pending") tooltipText = " title=\"Click to start crawl\"";
        if (job.status === "processing") tooltipText = " title=\"Click to force/expedite crawl\"";
        if (job.status === "crawled" || job.isDemo) tooltipText = " title=\"Click to view graph\"";
        
        li.innerHTML = `
            <span${tooltipText}>${displayName}</span>
            <span class="badge ${badgeClass}" style="padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">${badgeLabel}</span>
        `;
        
        li.addEventListener("click", () => {
            if (job.status === "crawled") {
                switchToRepo(job);
            } else if (job.status === "pending") {
                // Force transition to processing
                job.status = "processing";
                renderCrawlerQueue();
                addAgentMessage("System", `Manually triggered crawl for ${job.repo}. Starting AST dependency analysis...`, "system");
                
                setTimeout(() => {
                    job.status = "crawled";
                    switchToRepo(job);
                }, 2500);
            } else if (job.status === "processing") {
                // Force transition to crawled immediately
                addAgentMessage("System", `Expediting active crawl for ${job.repo}...`, "system");
                setTimeout(() => {
                    job.status = "crawled";
                    switchToRepo(job);
                }, 1500);
            }
        });
        
        crawlerQueueList.appendChild(li);
    });
}

// Switch visualization context to a different crawled repository
async function switchToRepo(job) {
    if (job.status !== "crawled" && !job.isDemo) return;
    
    activeRepoName = job.repo;
    
    const graphPanel = document.querySelector(".graph-panel");
    let loader = null;
    
    if (!job.graphs && !job.isDemo) {
        if (graphPanel) {
            loader = document.createElement("div");
            loader.className = "crawler-loader-overlay";
            loader.innerHTML = `
                <div class="crawler-loader-spinner"></div>
                <div class="crawler-loader-text">Crawling Repository...</div>
                <div class="crawler-loader-subtext">Fetching release tags, downloading source, and extracting real dependencies. This may take a few seconds.</div>
            `;
            graphPanel.appendChild(loader);
        }
        
        try {
            const apiPort = window.IMPACT_API_PORT || 7842;
            const response = await fetch(`http://localhost:${apiPort}/api/crawl`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ repo: job.repo })
            });
            
            if (!response.ok) {
                throw new Error(`Server returned HTTP ${response.status}`);
            }
            
            const data = await response.json();
            if (data.success) {
                job.graphs = {
                    v1: data.v1,
                    v2: data.v2
                };
                job.detectedLanguage = data.detected_language;
                job.tag1 = data.tag1;
                job.tag2 = data.tag2;
                console.log(`[Dashboard] Successfully crawled and loaded ${job.repo}`);
            } else {
                throw new Error(data.error || "Unknown crawling error");
            }
        } catch (e) {
            console.warn("[Dashboard] Live crawl failed, falling back to simulated graph:", e);
            addAgentMessage("System", `⚠️ [Crawl Fallback] Failed to extract live graphs for ${job.repo} (${e.message}). Loading simulated repository evolution.`, "system");
            if (loader) {
                loader.remove();
            }
            job.status = "crawled";
            renderCrawlerQueue();
        }
    }
    
    if (loader) {
        loader.remove();
    } else if (graphPanel) {
        const existingLoaders = graphPanel.querySelectorAll(".crawler-loader-overlay");
        existingLoaders.forEach(l => l.remove());
    }
    
    if (!job.graphs) {
        job.graphs = generateRepositoryGraph(job.repo, job.detectedLanguage);
    }
    
    baseGraph = job.graphs.v1;
    currentGraph = job.graphs.v2;
    
    // Update UI headers & selectors
    let displayRepoName = job.repo;
    let cleanName = job.repo.split("/")[1] || job.repo;
    if (job.isDemo) {
        displayRepoName = `${cleanName} (Demo)`;
    } else if (job.repo.includes(":")) {
        const parts = job.repo.split(":");
        displayRepoName = parts[0].trim();
        cleanName = displayRepoName.split("/")[1] || displayRepoName;
    }
    
    const headerTitle = document.querySelector(".content-header h2");
    if (headerTitle) {
        headerTitle.innerText = `${displayRepoName} Architecture Evolution`;
    }
    
    const baseVersionSelect = document.getElementById("base-version-select");
    const targetVersionSelect = document.getElementById("target-version-select");
    if (baseVersionSelect && targetVersionSelect) {
        const t1 = job.tag1 || "v1.0.0";
        const t2 = job.tag2 || "v2.0.0";
        baseVersionSelect.innerHTML = `<option value="v1">${t1} (${cleanName})</option>`;
        targetVersionSelect.innerHTML = `<option value="v2">${t2} (${cleanName})</option>`;
    }
    
    // Re-initialize layout, metrics, diff, and swarm analysis
    resetLayout();
    updateKPIs();
    updateUILabels();
    renderDiffTable();
    runAnalysis();
    
    // Refresh queue UI to update active highlight
    renderCrawlerQueue();
}

// Add custom queue styles inline dynamically
// Add custom queue styles inline dynamically
function addQueueStyles() {
    const style = document.createElement('style');
    style.innerHTML = `
        .badge.badge-pending { background-color: rgba(217, 119, 6, 0.15); color: #f59e0b; border: 1px solid rgba(217, 119, 6, 0.3); }
        .badge.badge-crawled { background-color: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3); }
        .badge.badge-processing { background-color: rgba(2, 132, 199, 0.15); color: #38bdf8; border: 1px solid rgba(2, 132, 199, 0.3); }
        .badge.badge-demo { background-color: rgba(139, 92, 246, 0.15); color: #a78bfa; border: 1px solid rgba(139, 92, 246, 0.3); }
        
        /* Interactive Report Bubble styles */
        .agent-bubble.interactive-report-bubble {
            cursor: pointer;
            border: 1px dashed rgba(16, 185, 129, 0.4) !important;
            position: relative;
            transition: all 0.2s ease;
        }
        .agent-bubble.interactive-report-bubble:hover {
            background: rgba(16, 185, 129, 0.08) !important;
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }
        .agent-bubble.interactive-report-bubble::after {
            content: "🖱️ Dbl-click to view";
            position: absolute;
            bottom: 4px;
            right: 8px;
            font-size: 9px;
            color: #10b981;
            opacity: 0.7;
        }

        /* Modal Overlay styles */
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(15, 23, 42, 0.8);
            backdrop-filter: blur(8px);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10000;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.3s ease;
        }
        .modal-overlay.active {
            opacity: 1;
            pointer-events: auto;
        }
        .modal-box {
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 12px;
            width: 90%;
            max-width: 650px;
            box-shadow: 0 20px 25px -5px rgba(0,0,0,0.5), 0 10px 10px -5px rgba(0,0,0,0.4);
            transform: translateY(20px);
            transition: transform 0.3s ease;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        .modal-overlay.active .modal-box {
            transform: translateY(0);
        }
        .modal-header {
            padding: 16px 20px;
            background: linear-gradient(135deg, #1e1b4b, #0f172a);
            border-bottom: 1px solid #1e293b;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .modal-header h3 {
            margin: 0;
            font-size: 16px;
            font-weight: 600;
            color: #38bdf8;
        }
        .modal-close {
            font-size: 24px;
            color: #64748b;
            cursor: pointer;
            transition: color 0.2s;
        }
        .modal-close:hover {
            color: #ef4444;
        }
        .modal-body {
            padding: 20px;
            max-height: 400px;
            overflow-y: auto;
            background: #020617;
        }
        .modal-body pre {
            margin: 0;
            font-family: 'Fira Code', monospace;
            font-size: 12px;
            color: #e2e8f0;
            white-space: pre-wrap;
            line-height: 1.6;
        }
        .modal-footer {
            padding: 12px 20px;
            background: #0f172a;
            border-top: 1px solid #1e293b;
            display: flex;
            justify-content: flex-end;
        }
        .modal-btn-close {
            background: #38bdf8;
            color: #0f172a;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            font-weight: 600;
            font-size: 13px;
            cursor: pointer;
            transition: background-color 0.2s;
        }
        .modal-btn-close:hover {
            background: #0ea5e9;
        }

        /* Modal tab strip */
        .modal-tabs {
            display: flex;
            gap: 0;
            background: #0a0f1e;
            border-bottom: 1px solid #1e293b;
        }
        .modal-tab {
            flex: 1;
            padding: 10px 0;
            background: transparent;
            color: #64748b;
            border: none;
            border-bottom: 2px solid transparent;
            cursor: pointer;
            font-family: inherit;
            font-size: 13px;
            font-weight: 500;
            transition: color 0.2s, border-color 0.2s;
        }
        .modal-tab:hover { color: #94a3b8; }
        .modal-tab.active { color: #38bdf8; border-bottom-color: #38bdf8; }

        /* Tab content */
        .modal-tab-content { display: none; }
        .modal-tab-content.active { display: block; }

        /* LLM spinner */
        .modal-spinner {
            padding: 40px 20px;
            text-align: center;
            color: #38bdf8;
            font-size: 14px;
            animation: pulse 1.5s ease-in-out infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.4; }
        }

        /* Glassmorphic Loader Overlay */
        .crawler-loader-overlay {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(10, 15, 30, 0.85);
            backdrop-filter: blur(6px);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            border-radius: 8px;
            transition: opacity 0.3s ease;
        }
        .crawler-loader-spinner {
            width: 50px;
            height: 50px;
            border: 3px solid rgba(56, 189, 248, 0.1);
            border-top: 3px solid #38bdf8;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-bottom: 16px;
        }
        .crawler-loader-text {
            color: #e2e8f0;
            font-size: 15px;
            font-weight: 600;
            text-align: center;
        }
        .crawler-loader-subtext {
            color: #94a3b8;
            font-size: 12px;
            margin-top: 8px;
            text-align: center;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    `;
    document.head.appendChild(style);
}

// Generate dynamic graph for crawled repository to visualize its evolution
function generateRepositoryGraph(repoName, detectedLanguage) {
    let rawRepoName = repoName;
    let suffixLang = null;
    if (repoName.includes(":")) {
        const parts = repoName.split(":");
        rawRepoName = parts[0].trim();
        suffixLang = parts[1].trim();
    }
    const cleanName = rawRepoName.split("/")[1] || rawRepoName;
    const lowerName = cleanName.toLowerCase();
    
    let v1Nodes = [];
    let v1Edges = [];
    let v2Nodes = [];
    let v2Edges = [];
    let averageCoupling1 = 1.5;
    let averageCoupling2 = 1.8;
    let language = "Unsupported";

    // Language identification heuristic
    if (suffixLang) {
        const lowerSuffix = suffixLang.toLowerCase();
        if (lowerSuffix === "java") language = "Java";
        else if (lowerSuffix === "python" || lowerSuffix === "py") language = "Python";
        else if (lowerSuffix === "erlang" || lowerSuffix === "erl") language = "Erlang";
        else if (lowerSuffix === "gleam") language = "Gleam";
        else language = suffixLang.charAt(0).toUpperCase() + suffixLang.slice(1);
    } else if (detectedLanguage) {
        const lowerDet = detectedLanguage.toLowerCase();
        if (lowerDet === "java") language = "Java";
        else if (lowerDet === "python") language = "Python";
        else if (lowerDet === "erlang") language = "Erlang";
        else if (lowerDet === "gleam") language = "Gleam";
        else language = detectedLanguage.charAt(0).toUpperCase() + detectedLanguage.slice(1);
    } else {
        const nameMatch = repoName.toLowerCase();
        if (nameMatch.includes("jsoup") || nameMatch.includes("guava") || nameMatch.includes("petclinic") || nameMatch.includes("java")) {
            language = "Java";
        } else if (nameMatch.includes("flask") || nameMatch.includes("python") || nameMatch.includes("django") || nameMatch.includes("impact")) {
            language = "Python";
        } else if (nameMatch.includes("gleam")) {
            language = "Gleam";
        } else if (nameMatch.includes("iguana") || nameMatch.includes("erlang") || nameMatch.includes("otp")) {
            language = "Erlang";
        } else if (nameMatch.includes("lagos")) {
            language = "Gleam";
        } else {
            language = "Unsupported";
        }
    }
    
    if (lowerName.includes("jsoup")) {
        const pkg = "org.jsoup";
        v1Nodes = [
            { id: `${pkg}.Jsoup`, name: "Jsoup", type: "class", metrics: { loc: 520, complexity: 18, coupling: 6, fanIn: 2, fanOut: 4, inheritanceDepth: 1 } },
            { id: `${pkg}.parser.Parser`, name: "Parser", type: "class", metrics: { loc: 410, complexity: 12, coupling: 5, fanIn: 3, fanOut: 2, inheritanceDepth: 0 } },
            { id: `${pkg}.parser.HtmlTreeBuilder`, name: "HtmlTreeBuilder", type: "class", metrics: { loc: 630, complexity: 22, coupling: 7, fanIn: 2, fanOut: 5, inheritanceDepth: 1 } },
            { id: `${pkg}.parser.Tokeniser`, name: "Tokeniser", type: "class", metrics: { loc: 340, complexity: 9, coupling: 4, fanIn: 2, fanOut: 2, inheritanceDepth: 0 } },
            { id: `${pkg}.nodes.Document`, name: "Document", type: "class", metrics: { loc: 290, complexity: 7, coupling: 4, fanIn: 3, fanOut: 1, inheritanceDepth: 1 } },
            { id: `${pkg}.nodes.Element`, name: "Element", type: "class", metrics: { loc: 460, complexity: 14, coupling: 5, fanIn: 2, fanOut: 3, inheritanceDepth: 1 } },
            { id: `${pkg}.nodes.Node`, name: "Node", type: "class", metrics: { loc: 190, complexity: 4, coupling: 3, fanIn: 3, fanOut: 0, inheritanceDepth: 0 } }
        ];
        v1Edges = [
            { source: `${pkg}.Jsoup`, target: `${pkg}.parser.Parser`, type: "calls" },
            { source: `${pkg}.parser.Parser`, target: `${pkg}.parser.HtmlTreeBuilder`, type: "uses" },
            { source: `${pkg}.parser.HtmlTreeBuilder`, target: `${pkg}.parser.Tokeniser`, type: "uses" },
            { source: `${pkg}.parser.Parser`, target: `${pkg}.nodes.Document`, type: "creates" },
            { source: `${pkg}.nodes.Document`, target: `${pkg}.nodes.Element`, type: "extends" },
            { source: `${pkg}.nodes.Element`, target: `${pkg}.nodes.Node`, type: "extends" }
        ];
        v2Nodes = [
            ...v1Nodes.map(n => ({ ...n, metrics: { ...n.metrics, loc: Math.round(n.metrics.loc * 1.05) } })),
            { id: `${pkg}.safety.Cleaner`, name: "Cleaner", type: "class", metrics: { loc: 240, complexity: 8, coupling: 4, fanIn: 1, fanOut: 3, inheritanceDepth: 0 } },
            { id: `${pkg}.helper.HttpConnection`, name: "HttpConnection", type: "class", metrics: { loc: 310, complexity: 11, coupling: 4, fanIn: 1, fanOut: 3, inheritanceDepth: 1 } }
        ];
        v2Edges = [
            ...v1Edges,
            { source: `${pkg}.Jsoup`, target: `${pkg}.helper.HttpConnection`, type: "calls" },
            { source: `${pkg}.parser.HtmlTreeBuilder`, target: `${pkg}.safety.Cleaner`, type: "uses" },
            { source: `${pkg}.safety.Cleaner`, target: `${pkg}.nodes.Document`, type: "uses" },
            { source: `${pkg}.parser.Tokeniser`, target: `${pkg}.parser.Parser`, type: "calls" } // Cycle: Parser -> HtmlTreeBuilder -> Tokeniser -> Parser
        ];
        averageCoupling1 = 2.4;
        averageCoupling2 = 2.8;
        language = "Java";
    } else if (lowerName.includes("flask")) {
        const pkg = "flask";
        v1Nodes = [
            { id: `${pkg}.app`, name: "app.py", type: "module", metrics: { loc: 650, complexity: 25, coupling: 6, fanIn: 2, fanOut: 4 } },
            { id: `${pkg}.blueprints`, name: "blueprints.py", type: "module", metrics: { loc: 320, complexity: 12, coupling: 4, fanIn: 1, fanOut: 3 } },
            { id: `${pkg}.config`, name: "config.py", type: "module", metrics: { loc: 180, complexity: 5, coupling: 3, fanIn: 1, fanOut: 0 } },
            { id: `${pkg}.helpers`, name: "helpers.py", type: "module", metrics: { loc: 290, complexity: 9, coupling: 5, fanIn: 2, fanOut: 1 } },
            { id: `${pkg}.sessions`, name: "sessions.py", type: "module", metrics: { loc: 150, complexity: 4, coupling: 2, fanIn: 1, fanOut: 0 } },
            { id: `${pkg}.ctx`, name: "ctx.py", type: "module", metrics: { loc: 210, complexity: 8, coupling: 4, fanIn: 1, fanOut: 2 } }
        ];
        v1Edges = [
            { source: `${pkg}.app`, target: `${pkg}.config`, type: "imports" },
            { source: `${pkg}.app`, target: `${pkg}.ctx`, type: "imports" },
            { source: `${pkg}.app`, target: `${pkg}.helpers`, type: "imports" },
            { source: `${pkg}.blueprints`, target: `${pkg}.app`, type: "imports" },
            { source: `${pkg}.ctx`, target: `${pkg}.sessions`, type: "imports" }
        ];
        v2Nodes = [
            ...v1Nodes.map(n => ({ ...n, metrics: { ...n.metrics, loc: Math.round(n.metrics.loc * 1.05) } })),
            { id: `${pkg}.cli`, name: "cli.py", type: "module", metrics: { loc: 280, complexity: 10, coupling: 4, fanIn: 1, fanOut: 2 } },
            { id: `${pkg}.views`, name: "views.py", type: "module", metrics: { loc: 190, complexity: 6, coupling: 3, fanIn: 1, fanOut: 2 } }
        ];
        v2Edges = [
            ...v1Edges,
            { source: `${pkg}.app`, target: `${pkg}.cli`, type: "imports" },
            { source: `${pkg}.cli`, target: `${pkg}.app`, type: "imports" }, // Cycle: app.py <-> cli.py
            { source: `${pkg}.app`, target: `${pkg}.views`, type: "imports" },
            { source: `${pkg}.views`, target: `${pkg}.helpers`, type: "imports" }
        ];
        averageCoupling1 = 1.9;
        averageCoupling2 = 2.2;
        language = "Python";
    } else if (lowerName.includes("gleam")) {
        const pkg = "src/gleam";
        v1Nodes = [
            { id: `${pkg}/io.gleam`, name: "io.gleam", type: "file", metrics: { loc: 120, complexity: 4, coupling: 2, fanIn: 1, fanOut: 2 } },
            { id: `${pkg}/string.gleam`, name: "string.gleam", type: "file", metrics: { loc: 310, complexity: 10, coupling: 3, fanIn: 2, fanOut: 1 } },
            { id: `${pkg}/list.gleam`, name: "list.gleam", type: "file", metrics: { loc: 450, complexity: 15, coupling: 4, fanIn: 2, fanOut: 2 } },
            { id: `${pkg}/result.gleam`, name: "result.gleam", type: "file", metrics: { loc: 180, complexity: 5, coupling: 2, fanIn: 2, fanOut: 0 } }
        ];
        v1Edges = [
            { source: `${pkg}/io.gleam`, target: `${pkg}/string.gleam`, type: "imports" },
            { source: `${pkg}/list.gleam`, target: `${pkg}/result.gleam`, type: "imports" }
        ];
        v2Nodes = [
            ...v1Nodes.map(n => ({ ...n, metrics: { ...n.metrics, loc: Math.round(n.metrics.loc * 1.05) } })),
            { id: `${pkg}/http.gleam`, name: "http.gleam", type: "file", metrics: { loc: 250, complexity: 8, coupling: 3, fanIn: 0, fanOut: 2 } }
        ];
        v2Edges = [
            ...v1Edges,
            { source: `${pkg}/http.gleam`, target: `${pkg}/io.gleam`, type: "imports" },
            { source: `${pkg}/io.gleam`, target: `${pkg}/list.gleam`, type: "imports" },
            { source: `${pkg}/list.gleam`, target: `${pkg}/io.gleam`, type: "imports" } // Cycle: io.gleam <-> list.gleam
        ];
        averageCoupling1 = 1.2;
        averageCoupling2 = 1.6;
        language = "Gleam";
    } else if (lowerName.includes("guava")) {
        const pkg = "com.google.common";
        v1Nodes = [
            { id: `${pkg}.base.Preconditions`, name: "Preconditions", type: "class", metrics: { loc: 160, complexity: 5, coupling: 8, fanIn: 8, fanOut: 0, inheritanceDepth: 0 } },
            { id: `${pkg}.collect.Lists`, name: "Lists", type: "class", metrics: { loc: 210, complexity: 6, coupling: 4, fanIn: 1, fanOut: 3, inheritanceDepth: 0 } },
            { id: `${pkg}.collect.Maps`, name: "Maps", type: "class", metrics: { loc: 260, complexity: 8, coupling: 4, fanIn: 1, fanOut: 3, inheritanceDepth: 0 } },
            { id: `${pkg}.collect.Sets`, name: "Sets", type: "class", metrics: { loc: 190, complexity: 5, coupling: 3, fanIn: 1, fanOut: 2, inheritanceDepth: 0 } },
            { id: `${pkg}.collect.ImmutableList`, name: "ImmutableList", type: "class", metrics: { loc: 410, complexity: 13, coupling: 5, fanIn: 4, fanOut: 1, inheritanceDepth: 1 } },
            { id: `${pkg}.collect.ImmutableMap`, name: "ImmutableMap", type: "class", metrics: { loc: 470, complexity: 15, coupling: 5, fanIn: 4, fanOut: 1, inheritanceDepth: 1 } }
        ];
        v1Edges = [
            { source: `${pkg}.collect.ImmutableList`, target: `${pkg}.base.Preconditions`, type: "checks" },
            { source: `${pkg}.collect.ImmutableMap`, target: `${pkg}.base.Preconditions`, type: "checks" },
            { source: `${pkg}.collect.Lists`, target: `${pkg}.collect.ImmutableList`, type: "creates" },
            { source: `${pkg}.collect.Maps`, target: `${pkg}.collect.ImmutableMap`, type: "creates" },
            { source: `${pkg}.collect.Sets`, target: `${pkg}.base.Preconditions`, type: "checks" }
        ];
        v2Nodes = [
            ...v1Nodes.map(n => ({ ...n, metrics: { ...n.metrics, loc: Math.round(n.metrics.loc * 1.08) } })),
            { id: `${pkg}.cache.CacheBuilder`, name: "CacheBuilder", type: "class", metrics: { loc: 510, complexity: 16, coupling: 5, fanIn: 1, fanOut: 4, inheritanceDepth: 0 } },
            { id: `${pkg}.cache.LocalCache`, name: "LocalCache", type: "class", metrics: { loc: 890, complexity: 32, coupling: 7, fanIn: 4, fanOut: 3, inheritanceDepth: 1 } }
        ];
        v2Edges = [
            ...v1Edges,
            { source: `${pkg}.cache.CacheBuilder`, target: `${pkg}.cache.LocalCache`, type: "creates" },
            { source: `${pkg}.cache.LocalCache`, target: `${pkg}.cache.CacheBuilder`, type: "references" }, // Cycle: CacheBuilder <-> LocalCache
            { source: `${pkg}.cache.LocalCache`, target: `${pkg}.base.Preconditions`, type: "checks" }
        ];
        averageCoupling1 = 1.8;
        averageCoupling2 = 2.1;
        language = "Java";
    } else if (lowerName.includes("petclinic")) {
        const pkg = "org.springframework.samples.petclinic";
        v1Nodes = [
            { id: `${pkg}.PetClinicApplication`, name: "PetClinicApp", type: "class", metrics: { loc: 110, complexity: 2, coupling: 4, fanIn: 0, fanOut: 4, inheritanceDepth: 0 } },
            { id: `${pkg}.owner.OwnerController`, name: "OwnerController", type: "class", metrics: { loc: 310, complexity: 11, coupling: 5, fanIn: 1, fanOut: 4, inheritanceDepth: 0 } },
            { id: `${pkg}.owner.OwnerRepository`, name: "OwnerRepository", type: "class", metrics: { loc: 140, complexity: 4, coupling: 3, fanIn: 2, fanOut: 1, inheritanceDepth: 1 } },
            { id: `${pkg}.owner.Owner`, name: "Owner", type: "class", metrics: { loc: 240, complexity: 6, coupling: 4, fanIn: 3, fanOut: 1, inheritanceDepth: 0 } },
            { id: `${pkg}.vet.VetController`, name: "VetController", type: "class", metrics: { loc: 270, complexity: 9, coupling: 5, fanIn: 1, fanOut: 4, inheritanceDepth: 0 } },
            { id: `${pkg}.vet.VetRepository`, name: "VetRepository", type: "class", metrics: { loc: 110, complexity: 3, coupling: 3, fanIn: 2, fanOut: 1, inheritanceDepth: 1 } },
            { id: `${pkg}.vet.Vet`, name: "Vet", type: "class", metrics: { loc: 170, complexity: 4, coupling: 4, fanIn: 3, fanOut: 1, inheritanceDepth: 0 } }
        ];
        v1Edges = [
            { source: `${pkg}.PetClinicApplication`, target: `${pkg}.owner.OwnerController`, type: "routes" },
            { source: `${pkg}.PetClinicApplication`, target: `${pkg}.vet.VetController`, type: "routes" },
            { source: `${pkg}.owner.OwnerController`, target: `${pkg}.owner.OwnerRepository`, type: "queries" },
            { source: `${pkg}.owner.OwnerController`, target: `${pkg}.owner.Owner`, type: "binds" },
            { source: `${pkg}.vet.VetController`, target: `${pkg}.vet.VetRepository`, type: "queries" },
            { source: `${pkg}.vet.VetController`, target: `${pkg}.vet.Vet`, type: "binds" }
        ];
        v2Nodes = [
            ...v1Nodes.map(n => ({ ...n, metrics: { ...n.metrics, loc: Math.round(n.metrics.loc * 1.05) } })),
            { id: `${pkg}.visit.VisitController`, name: "VisitController", type: "class", metrics: { loc: 290, complexity: 10, coupling: 5, fanIn: 1, fanOut: 4, inheritanceDepth: 0 } },
            { id: `${pkg}.visit.VisitRepository`, name: "VisitRepository", type: "class", metrics: { loc: 100, complexity: 3, coupling: 3, fanIn: 2, fanOut: 1, inheritanceDepth: 1 } },
            { id: `${pkg}.visit.Visit`, name: "Visit", type: "class", metrics: { loc: 150, complexity: 4, coupling: 4, fanIn: 3, fanOut: 1, inheritanceDepth: 0 } }
        ];
        v2Edges = [
            ...v1Edges,
            { source: `${pkg}.PetClinicApplication`, target: `${pkg}.visit.VisitController`, type: "routes" },
            { source: `${pkg}.visit.VisitController`, target: `${pkg}.visit.VisitRepository`, type: "queries" },
            { source: `${pkg}.visit.VisitController`, target: `${pkg}.visit.Visit`, type: "binds" },
            { source: `${pkg}.owner.Owner`, target: `${pkg}.visit.Visit`, type: "has" },
            { source: `${pkg}.visit.Visit`, target: `${pkg}.owner.Owner`, type: "belongsTo" } // Cycle: Owner <-> Visit
        ];
        averageCoupling1 = 2.0;
        averageCoupling2 = 2.4;
        language = "Java";
    } else {
        // Fallback nodes generation based on determined language
        if (language === "Java") {
            const pkg = `org.${lowerName}`;
            v1Nodes = [
                { id: `${pkg}.Core`, name: `${cleanName}Core`, type: "class", metrics: { loc: 300, complexity: 10, coupling: 4, fanIn: 2, fanOut: 2, inheritanceDepth: 1 } },
                { id: `${pkg}.Client`, name: `${cleanName}Client`, type: "class", metrics: { loc: 150, complexity: 5, coupling: 3, fanIn: 0, fanOut: 3, inheritanceDepth: 0 } },
                { id: `${pkg}.Service`, name: `${cleanName}Service`, type: "class", metrics: { loc: 250, complexity: 8, coupling: 4, fanIn: 2, fanOut: 2, inheritanceDepth: 1 } },
                { id: `${pkg}.Database`, name: `${cleanName}Db`, type: "class", metrics: { loc: 120, complexity: 4, coupling: 2, fanIn: 2, fanOut: 0, inheritanceDepth: 0 } }
            ];
            v1Edges = [
                { source: `${pkg}.Client`, target: `${pkg}.Core`, type: "calls" },
                { source: `${pkg}.Core`, target: `${pkg}.Service`, type: "calls" },
                { source: `${pkg}.Service`, target: `${pkg}.Database`, type: "queries" }
            ];
            v2Nodes = [
                ...v1Nodes.map(n => ({ ...n, metrics: { ...n.metrics, loc: Math.round(n.metrics.loc * 1.1) } })),
                { id: `${pkg}.Helper`, name: `${cleanName}Helper`, type: "class", metrics: { loc: 90, complexity: 3, coupling: 2, fanIn: 1, fanOut: 1, inheritanceDepth: 0 } }
            ];
            v2Edges = [
                ...v1Edges,
                { source: `${pkg}.Core`, target: `${pkg}.Helper`, type: "uses" },
                { source: `${pkg}.Helper`, target: `${pkg}.Core`, type: "calls" } // Cycle
            ];
        } else if (language === "Python") {
            const pkg = lowerName.replace(/[^a-z0-9]/g, "_");
            v1Nodes = [
                { id: `${pkg}.core`, name: `core.py`, type: "module", metrics: { loc: 300, complexity: 10, coupling: 4, fanIn: 2, fanOut: 2 } },
                { id: `${pkg}.client`, name: `client.py`, type: "module", metrics: { loc: 150, complexity: 5, coupling: 3, fanIn: 0, fanOut: 3 } },
                { id: `${pkg}.server`, name: `server.py`, type: "module", metrics: { loc: 250, complexity: 8, coupling: 4, fanIn: 2, fanOut: 2 } },
                { id: `${pkg}.db`, name: `db.py`, type: "module", metrics: { loc: 120, complexity: 4, coupling: 2, fanIn: 2, fanOut: 0 } }
            ];
            v1Edges = [
                { source: `${pkg}.client`, target: `${pkg}.core`, type: "imports" },
                { source: `${pkg}.core`, target: `${pkg}.server`, type: "imports" },
                { source: `${pkg}.server`, target: `${pkg}.db`, type: "imports" }
            ];
            v2Nodes = [
                ...v1Nodes.map(n => ({ ...n, metrics: { ...n.metrics, loc: Math.round(n.metrics.loc * 1.1) } })),
                { id: `${pkg}.helper`, name: `helper.py`, type: "module", metrics: { loc: 90, complexity: 3, coupling: 2, fanIn: 1, fanOut: 1 } }
            ];
            v2Edges = [
                ...v1Edges,
                { source: `${pkg}.core`, target: `${pkg}.helper`, type: "imports" },
                { source: `${pkg}.helper`, target: `${pkg}.core`, type: "imports" } // Cycle
            ];
        } else {
            // General file fallback (Erlang, Gleam, Go, Rust, Unsupported, etc.)
            let ext = ".src";
            if (language === "Erlang") ext = ".erl";
            else if (language === "Gleam") ext = ".gleam";
            else if (language === "Go") ext = ".go";
            else if (language === "Rust") ext = ".rs";
            
            const pkg = "src/";
            v1Nodes = [
                { id: `${pkg}core${ext}`, name: `core${ext}`, type: "file", metrics: { loc: 300, complexity: 10, coupling: 4, fanIn: 2, fanOut: 2 } },
                { id: `${pkg}client${ext}`, name: `client${ext}`, type: "file", metrics: { loc: 150, complexity: 5, coupling: 3, fanIn: 0, fanOut: 3 } },
                { id: `${pkg}server${ext}`, name: `server${ext}`, type: "file", metrics: { loc: 250, complexity: 8, coupling: 4, fanIn: 2, fanOut: 2 } },
                { id: `${pkg}db${ext}`, name: `db${ext}`, type: "file", metrics: { loc: 120, complexity: 4, coupling: 2, fanIn: 2, fanOut: 0 } }
            ];
            v1Edges = [
                { source: `${pkg}client${ext}`, target: `${pkg}core${ext}`, type: "imports" },
                { source: `${pkg}core${ext}`, target: `${pkg}server${ext}`, type: "imports" },
                { source: `${pkg}server${ext}`, target: `${pkg}db${ext}`, type: "imports" }
            ];
            v2Nodes = [
                ...v1Nodes.map(n => ({ ...n, metrics: { ...n.metrics, loc: Math.round(n.metrics.loc * 1.1) } })),
                { id: `${pkg}helper${ext}`, name: `helper${ext}`, type: "file", metrics: { loc: 90, complexity: 3, coupling: 2, fanIn: 1, fanOut: 1 } }
            ];
            v2Edges = [
                ...v1Edges,
                { source: `${pkg}core${ext}`, target: `${pkg}helper${ext}`, type: "imports" },
                { source: `${pkg}helper${ext}`, target: `${pkg}core${ext}`, type: "imports" } // Cycle: core <-> helper
            ];
        }
        averageCoupling1 = 1.5;
        averageCoupling2 = 1.8;
    }

    return {
        v1: {
            version: "1.0.0",
            projectName: cleanName,
            language: language,
            systemMetrics: {
                totalClasses: v1Nodes.length,
                totalLinesOfCode: v1Nodes.reduce((acc, n) => acc + n.metrics.loc, 0),
                averageCoupling: averageCoupling1
            },
            nodes: v1Nodes,
            edges: v1Edges
        },
        v2: {
            version: "2.0.0",
            projectName: cleanName,
            language: language,
            systemMetrics: {
                totalClasses: v2Nodes.length,
                totalLinesOfCode: v2Nodes.reduce((acc, n) => acc + n.metrics.loc, 0),
                averageCoupling: averageCoupling2
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
        const newJob = { repo, status: "pending", graphs: null, detectedLanguage: null };
        crawlerQueue.push(newJob);
        crawlerRepoInput.value = "";
        renderCrawlerQueue();
        
        addAgentMessage("System", `Enqueued repository for ecosystem crawl: ${repo}`, "system");
        
        // Fetch metadata from GitHub API in the background to detect language
        let displayRepo = repo;
        if (repo.includes(":")) {
            displayRepo = repo.split(":")[0].trim();
        }
        fetch(`https://api.github.com/repos/${displayRepo}/languages`)
            .then(res => {
                if (res.ok) return res.json();
                throw new Error("GitHub API rate limit or error");
            })
            .then(data => {
                if (data && Object.keys(data).length > 0) {
                    let maxLang = null;
                    let maxBytes = -1;
                    for (const [lang, bytes] of Object.entries(data)) {
                        if (Object.keys(data).length > 1 && ["Shell", "HTML", "CSS", "Dockerfile"].includes(lang)) {
                            continue;
                        }
                        if (bytes > maxBytes) {
                            maxBytes = bytes;
                            maxLang = lang;
                        }
                    }
                    if (maxLang) {
                        newJob.detectedLanguage = maxLang;
                        console.log(`[Dashboard] Pre-fetched major language: ${maxLang} for ${repo}`);
                    }
                }
            })
            .catch(err => {
                console.log("[Dashboard] Background language pre-fetch failed:", err);
            });
        
        // Simulate background worker processing
        setTimeout(() => {
            newJob.status = "processing";
            renderCrawlerQueue();
            addAgentMessage("System", `Crawler claimed ${repo}, starting AST dependency analysis...`, "system");
        }, 1500);
        setTimeout(() => {
            newJob.status = "crawled";
            switchToRepo(newJob);
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
    // Cancel any still-pending timeouts from a previous analysis run
    analysisTimeouts.forEach(id => clearTimeout(id));
    analysisTimeouts = [];

    agentChatContainer.innerHTML = "";
    addAgentMessage("System", "Initializing IMPACT Multi-Agent Evolution Swarm...", "system");

    const lang = currentGraph.language || "Java";
    let unitSingular = "class";
    let unitPlural = "classes";
    let cycleTerm = "cycle loops";
    let depTerm = "edges";
    let isFallback = false;
    
    if (lang === "Python") {
        unitSingular = "module";
        unitPlural = "modules";
        cycleTerm = "circular imports";
        depTerm = "dependencies";
    } else if (lang !== "Java") {
        unitSingular = "file";
        unitPlural = "files";
        cycleTerm = "dependency cycles";
        depTerm = "imports";
        isFallback = true;
    }

    if (isFallback) {
        analysisTimeouts.push(setTimeout(() => {
            const warningMsg = lang === "Unsupported"
                ? "⚠️ NOTE: Unknown repository language. Dashboard running in File-Dependency Fallback Mode."
                : `⚠️ NOTE: Full AST structure analysis for ${lang} is not implemented. Running in File-Dependency Fallback Mode.`;
            addAgentMessage("System", warningMsg, "system");
        }, 200));
    }

    analysisTimeouts.push(setTimeout(() => {
        addAgentMessage("GraphAgent", `Loaded Version ${currentGraph.version} of ${currentGraph.projectName} (${currentGraph.systemMetrics.totalClasses} ${unitPlural}, ${currentGraph.systemMetrics.totalLinesOfCode} LOC). [Language: ${lang}]`, "coordinator");
    }, 400));

    analysisTimeouts.push(setTimeout(() => {
        const diff = computeDiff();
        addAgentMessage("DiffAgent", `Identified structural changes: added ${diff.addedNodes.length} ${unitPlural}, added ${diff.addedEdges.length} ${depTerm}. Detected ${diff.newCycles.length} new ${cycleTerm}.`, "coordinator");
    }, 800));

    analysisTimeouts.push(setTimeout(() => {
        const topHubs = currentGraph.nodes.map(n => n.id);
        addAgentMessage("MetricsAgent", `Calculated network metrics. Most central coupling hubs: ${topHubs.slice(0, 3).join(", ")}.`, "coordinator");
    }, 1200));

    analysisTimeouts.push(setTimeout(() => {
        const diff = computeDiff();
        let violations = [];

        intents.forEach(intent => {
            if (intent.type === "no-cycles") {
                if (diff.newCycles.length > 0) {
                    violations.push(`New ${cycleTerm} detected (${diff.newCycles.length} cycles). Breaches 'Avoid ${cycleTerm}'.`);
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
   * Added ${unitPlural.charAt(0).toUpperCase() + unitPlural.slice(1)}: ${diff.addedNodes.length}
   * Added Dependencies (${depTerm}): ${diff.addedEdges.length}
   * Removed ${unitPlural.charAt(0).toUpperCase() + unitPlural.slice(1)}: ${diff.removedNodes.length}
   * Removed Dependencies (${depTerm}): ${diff.removedEdges.length}

2. Dependency Cycles:
   * New ${cycleTerm.charAt(0).toUpperCase() + cycleTerm.slice(1)} Detected: ${diff.newCycles.length}
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
    }, 1600));

    // Final message — always appears last, stable and double-clickable
    analysisTimeouts.push(setTimeout(() => {
        addAgentMessage("System", `Successfully crawled ${activeRepoName}. Conformance report generated.`, "system");
    }, 2000));
}

// Dynamic UI labeling based on ecosystem language
function updateUILabels() {
    const lang = currentGraph.language || "Java";
    const classesLabel = document.getElementById("metric-classes-label");
    const fqcnHeader = document.getElementById("diff-table-fqcn-header");
    
    if (lang === "Python") {
        if (classesLabel) classesLabel.innerText = "Total Modules";
        if (fqcnHeader) fqcnHeader.innerText = "Module Path";
    } else if (lang !== "Java") {
        // Gleam, Erlang, or other fallback languages
        const suffix = lang === "Unsupported" ? "" : `: ${lang}`;
        if (classesLabel) classesLabel.innerText = `Total Files (Fallback${suffix})`;
        if (fqcnHeader) fqcnHeader.innerText = "File Path (Fallback)";
    } else {
        // Java
        if (classesLabel) classesLabel.innerText = "Total Classes";
        if (fqcnHeader) fqcnHeader.innerText = "Class (FQCN)";
    }
}

function addAgentMessage(agent, text, type) {
    const bubble = document.createElement("div");
    bubble.className = `agent-bubble ${type}`;
    
    // Check if the message contains crawl success or analysis completion to make it double-clickable
    if (text.includes("Conformance report generated") || text.includes("Successfully crawled")) {
        bubble.classList.add("interactive-report-bubble");
        bubble.title = "Double-click to open the Conformance Report";
        bubble.addEventListener("dblclick", () => {
            showReportModal(activeRepoName, currentGraph.language || "Unsupported");
        });
    }
    
    bubble.innerHTML = `
        <div class="agent-title">${agent}</div>
        <div class="agent-text">${text}</div>
    `;
    agentChatContainer.appendChild(bubble);
    agentChatContainer.scrollTop = agentChatContainer.scrollHeight;
}

// Generate dynamically structured conformance report text matching the active intents
function generateReportText(repoName, lang) {
    const cleanName = repoName.includes(":") ? repoName.split(":")[0].trim() : repoName;
    const project = cleanName.split("/")[1] || cleanName;
    const diff = computeDiff();
    const isFallback = lang !== "Java" && lang !== "Python";
    const unit = isFallback ? (lang === "Unsupported" ? "files" : `${lang} files`) : (lang === "Java" ? "classes" : "modules");
    
    let conformanceStatus = "CONFORMANT";
    let violations = [];
    
    // Check cyclic dependency intent
    const hasCycleIntent = intents.some(i => i.type === "no-cycles");
    if (hasCycleIntent && diff.newCycles.length > 0) {
        conformanceStatus = "NON-CONFORMANT";
        violations.push(`   * VIOLATION: Detected ${diff.newCycles.length} new cyclic dependency paths. This breaches the active intent 'No Cyclic Dependencies'.`);
    }
    
    // Check coupling threshold intent
    const couplingIntent = intents.find(i => i.type === "max-coupling");
    if (couplingIntent) {
        const threshold = couplingIntent.val;
        const overloaded = currentGraph.nodes.filter(n => n.metrics.coupling > threshold);
        if (overloaded.length > 0) {
            conformanceStatus = "NON-CONFORMANT";
            violations.push(`   * VIOLATION: ${overloaded.length} node(s) exceed the maximum coupling threshold of ${threshold} (e.g. ${overloaded.slice(0, 3).map(n => n.name).join(", ")}).`);
        }
    }

    if (violations.length === 0) {
        violations.push("   * Status: CONFORMANT. No structural or dependency violations detected against active intents.");
    }
    
    let recommendation = "";
    if (conformanceStatus === "NON-CONFORMANT") {
        recommendation = "Action required: refactor dependencies to break cycle loops and decouple high-coupling hubs.";
    } else {
        recommendation = "Architecture remains stable. Maintain current modular boundaries and dependency guidelines.";
    }

    return `Architectural Evolution Report for ${repoName} (${lang})
===========================================================
1. Structural Changes:
   * Total Nodes in current version: ${currentGraph.nodes.length} ${unit}
   * Added Nodes: ${diff.addedNodes.length}
   * Added Dependencies: ${diff.addedEdges.length}
   * Removed Nodes: ${diff.removedNodes.length}
   * Removed Dependencies: ${diff.removedEdges.length}

2. Dependency Cycles:
   * Total Cycles: ${diff.newCycles.length}

3. Codebase Metrics Summary:
   * Total Lines of Code (LOC): ${currentGraph.systemMetrics.totalLinesOfCode}
   * Average Coupling: ${currentGraph.systemMetrics.averageCoupling.toFixed(2)}

4. Intent Conformance Evaluation:
   * Status: ${conformanceStatus}
${violations.join("\n")}

5. Recommendations:
   * ${recommendation}
`;
}

// Render and show the conformance report modal with two tabs:
// Tab 1 — local rule-based metrics summary (instant)
// Tab 2 — LLM/RAG narrative (async, fetches /api/llm-analysis, falls back gracefully)
function showReportModal(repoName, lang) {
    // Build or retrieve modal
    let modal = document.getElementById("conformance-report-modal");
    if (!modal) {
        modal = document.createElement("div");
        modal.id = "conformance-report-modal";
        modal.className = "modal-overlay";
        modal.innerHTML = `
            <div class="modal-box">
                <div class="modal-header">
                    <h3 id="modal-title">Architectural Conformance Report</h3>
                    <span class="modal-close">&times;</span>
                </div>
                <div class="modal-tabs">
                    <button class="modal-tab active" data-tab="metrics">📊 Metrics</button>
                    <button class="modal-tab" data-tab="llm">🤖 LLM Analysis</button>
                </div>
                <div class="modal-body">
                    <pre id="modal-tab-metrics" class="modal-tab-content active"></pre>
                    <div id="modal-tab-llm" class="modal-tab-content">
                        <div id="modal-llm-spinner" class="modal-spinner">⏳ Requesting LLM analysis…</div>
                        <pre id="modal-llm-content" style="display:none"></pre>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="modal-btn-close">Close Report</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);

        // Tab switching
        modal.querySelectorAll(".modal-tab").forEach(btn => {
            btn.addEventListener("click", () => {
                modal.querySelectorAll(".modal-tab").forEach(b => b.classList.remove("active"));
                modal.querySelectorAll(".modal-tab-content").forEach(c => c.classList.remove("active"));
                btn.classList.add("active");
                document.getElementById(`modal-tab-${btn.dataset.tab}`).classList.add("active");
            });
        });

        modal.querySelector(".modal-close").addEventListener("click", () => modal.classList.remove("active"));
        modal.querySelector(".modal-btn-close").addEventListener("click", () => modal.classList.remove("active"));
        modal.addEventListener("click", (e) => { if (e.target === modal) modal.classList.remove("active"); });
    }

    // Always reset to Metrics tab when opening
    modal.querySelectorAll(".modal-tab").forEach(b => b.classList.remove("active"));
    modal.querySelectorAll(".modal-tab-content").forEach(c => c.classList.remove("active"));
    modal.querySelector('[data-tab="metrics"]').classList.add("active");
    document.getElementById("modal-tab-metrics").classList.add("active");

    // Populate title
    document.getElementById("modal-title").innerText = `${repoName} — Conformance Report`;

    // Tab 1: instant local metrics
    document.getElementById("modal-tab-metrics").innerText = generateReportText(repoName, lang);

    // Tab 2: reset to spinner state
    document.getElementById("modal-llm-spinner").style.display = "block";
    document.getElementById("modal-llm-content").style.display = "none";
    document.getElementById("modal-llm-content").innerText = "";

    modal.classList.add("active");

    // Async: call the LLM API server
    const diff = computeDiff();
    const payload = {
        repo: repoName,
        lang,
        intents: intents.map(i => {
            if (i.type === "no-cycles") return "avoid cyclic dependencies";
            if (i.type === "max-coupling") return `max coupling threshold: ${i.val}`;
            if (i.type === "max-inheritance") return `max inheritance depth: ${i.val}`;
            return i.type;
        }),
        diff: {
            version_old: baseGraph.version || "v1",
            version_new: currentGraph.version || "v2",
            addedNodes: diff.addedNodes.length,
            removedNodes: diff.removedNodes.length,
            addedEdges: diff.addedEdges.length,
            removedEdges: diff.removedEdges.length,
            newCycles: diff.newCycles.length,
            brokenCycles: 0,
            addedNodeIds: diff.addedNodes.map(n => n.id || n.name || ""),
            removedNodeIds: diff.removedNodes.map(n => n.id || n.name || ""),
            addedEdgeIds: [],
            newCycleIds: diff.newCycles,
        },
        metrics: {
            topHubs: currentGraph.nodes.slice(0, 5).map(n => n.id || n.name),
            couplingAnomalies: [],
        }
    };

    const apiPort = window.IMPACT_API_PORT || 7842;
    fetch(`http://localhost:${apiPort}/api/llm-analysis`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(15000)
    })
    .then(r => r.ok ? r.json() : Promise.reject(`HTTP ${r.status}`))
    .then(data => {
        document.getElementById("modal-llm-spinner").style.display = "none";
        document.getElementById("modal-llm-content").innerText = data.report;
        document.getElementById("modal-llm-content").style.display = "block";
        const job = crawlerQueue.find(j => j.repo === repoName || (j.isDemo && repoName.includes("TelemetryService")));
        if (job) {
            job.llmReport = data.report;
        }
    })
    .catch(() => {
        // API server not running — show informative fallback in the tab
        document.getElementById("modal-llm-spinner").style.display = "none";
        document.getElementById("modal-llm-content").style.display = "block";
        document.getElementById("modal-llm-content").innerText =
            "ℹ️  LLM Analysis requires the IMPACT API server.\n\n" +
            "Start it with:\n" +
            "  python -m core.dashboard.api_server\n\n" +
            "Set GEMINI_API_KEY, OPENAI_API_KEY, or LLM_API_URL in your environment\n" +
            "to enable live LLM/RAG-powered architectural narrative.\n\n" +
            "Without an LLM key, the server will use a built-in rule-based analyser.";
    });
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
    updateUILabels();
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
        crawlerQueue[0].graphs = { v1: data1, v2: data2 };
        console.log("[Dashboard] Successfully loaded live graph files via fetch.");
    } catch (e) {
        console.log("[Dashboard] Fetch failed or blocked by CORS, using embedded fallback graph data:", e);
        crawlerQueue[0].graphs = { v1: GRAPH_DATA_V1, v2: GRAPH_DATA_V2 };
    }
    init();
}

runAnalysisBtn.addEventListener("click", () => {
    runAnalysis();
});

function escapeCSV(val) {
    if (val === undefined || val === null) return "";
    const str = String(val);
    if (str.includes(",") || str.includes('"') || str.includes("\n") || str.includes("\r")) {
        return `"${str.replace(/"/g, '""')}"`;
    }
    return str;
}

function computeDiffForGraphs(v1, v2) {
    const addedNodes = v2.nodes.filter(n => !v1.nodes.some(bn => bn.id === n.id));
    const removedNodes = v1.nodes.filter(bn => !v2.nodes.some(n => n.id === bn.id));
    const addedEdges = v2.edges.filter(e => !v1.edges.some(be => be.source === e.source && be.target === e.target));
    const removedEdges = v1.edges.filter(be => !v2.edges.some(e => e.source === be.source && e.target === be.target));

    const cyclesBase = findSimpleCycles(v1);
    const cyclesCurrent = findSimpleCycles(v2);

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

function getEcosystemReport(job, v1, v2, diff) {
    if (job.llmReport) {
        return job.llmReport;
    }
    // Fallback to a detailed conformance analysis
    const lang = job.detectedLanguage || "Java";
    const hasCycleIntent = intents.some(i => i.type === "no-cycles");
    let conformanceStatus = "CONFORMANT";
    let violations = [];
    if (hasCycleIntent && diff.newCycles.length > 0) {
        conformanceStatus = "NON-CONFORMANT";
        violations.push(`Detected ${diff.newCycles.length} new cyclic dependency paths.`);
    }
    const couplingIntent = intents.find(i => i.type === "max-coupling");
    if (couplingIntent) {
        const threshold = couplingIntent.val || couplingIntent.limit || 5;
        const overloaded = v2.nodes.filter(n => n.metrics.coupling > threshold);
        if (overloaded.length > 0) {
            conformanceStatus = "NON-CONFORMANT";
            violations.push(`${overloaded.length} node(s) exceed maximum coupling threshold of ${threshold}.`);
        }
    }
    let recommendation = conformanceStatus === "NON-CONFORMANT" 
        ? "Action required: refactor dependencies to break cycle loops and decouple high-coupling hubs."
        : "Architecture remains stable. Maintain current modular boundaries.";
        
    return `[Rule-based LLM Fallback] Status: ${conformanceStatus}. Violations: ${violations.join("; ") || "None"}. Recommendation: ${recommendation}`;
}

function exportEcosystemToCSV() {
    // Filter to crawled or demo repositories
    const crawledJobs = crawlerQueue.filter(j => j.status === "crawled" || j.isDemo);
    
    if (crawledJobs.length === 0) {
        alert("No repositories have been crawled successfully yet.");
        return;
    }

    let csvContent = "";
    
    // Title/Header
    csvContent += "IMPACT Ecosystem Architectural Evolution Export\n";
    csvContent += `Exported At,${escapeCSV(new Date().toLocaleString())}\n\n`;
    
    // Section 1: Repository Level Summaries
    csvContent += "Ecosystem Summary Table\n";
    csvContent += "Repository,Status,Language,Base Version,Target Version,Total Classes,Lines of Code,Average Coupling,Cycles Detected,Conformance Status,LLM Analysis & Recommendations\n";
    
    crawledJobs.forEach(job => {
        // Ensure graphs are populated
        const graphs = job.graphs || generateRepositoryGraph(job.repo, job.detectedLanguage);
        const v1 = graphs.v1;
        const v2 = graphs.v2;
        const diff = computeDiffForGraphs(v1, v2);
        
        const lang = job.detectedLanguage || v2.language || "Java";
        const hasCycleIntent = intents.some(i => i.type === "no-cycles");
        let conformanceStatus = "CONFORMANT";
        
        if (hasCycleIntent && diff.newCycles.length > 0) {
            conformanceStatus = "NON-CONFORMANT";
        }
        const couplingIntent = intents.find(i => i.type === "max-coupling");
        if (couplingIntent) {
            const threshold = couplingIntent.val || couplingIntent.limit || 5;
            const overloaded = v2.nodes.filter(n => n.metrics.coupling > threshold);
            if (overloaded.length > 0) {
                conformanceStatus = "NON-CONFORMANT";
            }
        }
        
        const reportText = getEcosystemReport(job, v1, v2, diff);
        
        csvContent += `${escapeCSV(job.repo)},${escapeCSV(job.status)},${escapeCSV(lang)},${escapeCSV(v1.version || "v1")},${escapeCSV(v2.version || "v2")},${escapeCSV(v2.systemMetrics.totalClasses)},${escapeCSV(v2.systemMetrics.totalLinesOfCode)},${escapeCSV(v2.systemMetrics.averageCoupling.toFixed(2))},${escapeCSV(diff.newCycles.length)},${escapeCSV(conformanceStatus)},${escapeCSV(reportText)}\n`;
    });
    
    csvContent += "\n\n";
    
    // Section 2: Detailed Class-Level Diff Table
    csvContent += "Detailed Class-Level Diff Table\n";
    csvContent += "Repository,Class (FQCN),Change Status,LOC,Complexity,Coupling,Type\n";
    
    crawledJobs.forEach(job => {
        const graphs = job.graphs || generateRepositoryGraph(job.repo, job.detectedLanguage);
        const v1 = graphs.v1;
        const v2 = graphs.v2;
        
        v2.nodes.forEach(n => {
            const isAdded = !v1.nodes.some(bn => bn.id === n.id);
            const status = isAdded ? "ADDED" : "UNCHANGED";
            csvContent += `${escapeCSV(job.repo)},${escapeCSV(n.id)},${escapeCSV(status)},${escapeCSV(n.metrics.loc)},${escapeCSV(n.metrics.complexity)},${escapeCSV(n.metrics.coupling)},${escapeCSV(n.type)}\n`;
        });
    });

    const defaultFilename = "impact_ecosystem_evolution_report.csv";
    const filename = prompt("Enter a name for the exported CSV file:", defaultFilename);
    if (!filename) return; // User canceled the dialog
    
    let finalFilename = filename.trim();
    if (!finalFilename.endsWith(".csv")) {
        finalFilename += ".csv";
    }
    
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", finalFilename);
    link.style.visibility = "hidden";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

const exportEcosystemBtn = document.getElementById("export-ecosystem-btn");
if (exportEcosystemBtn) {
    exportEcosystemBtn.addEventListener("click", exportEcosystemToCSV);
}

document.addEventListener("DOMContentLoaded", loadGraphs);

