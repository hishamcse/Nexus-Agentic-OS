HERO_HTML = """
<div class="nx-hero">
  <div class="nx-kicker">Meta-Orchestration · Dynamic Graph Construction · Runtime Agent Lifecycle</div>
  <div class="nx-title">
    <span>nexus</span><span class="nx-title-dim">://</span><span>agent-os</span>
  </div>
  <div class="nx-subtitle">
    Describe an agent. Nexus architects it, generates the code, validates it in a sandbox,
    deploys it as a live subprocess, and monitors it — autonomously. Agents spawning agents at runtime.
  </div>
  <div class="nx-badge-row">
    <span class="nx-badge">Architect</span>
    <span class="nx-badge">Spec Writer</span>
    <span class="nx-badge amber">Code Generator</span>
    <span class="nx-badge red">Validator</span>
    <span class="nx-badge blue">Deployer</span>
    <span class="nx-badge purple">Monitor</span>
    <span class="nx-badge">Retry loop</span>
    <span class="nx-badge amber">Sandbox execution</span>
    <span class="nx-badge blue">MCP registry</span>
    <span class="nx-badge purple">Live subprocess</span>
  </div>
</div>
"""

EMPTY_MISSION_HTML = """
<div class="nx-empty">
  <div class="nx-empty-icon">⬡</div>
  <div>No agents deployed yet.</div>
  <div style="margin-top:5px;opacity:0.6">Use the Forge to build and deploy your first agent.</div>
</div>"""

EMPTY_INSPECTOR_HTML = """
<div class="nx-empty">
  <div class="nx-empty-icon">⬡</div>
  <div>Select an agent from Mission Control.</div>
  <div style="margin-top:5px;opacity:0.6">Send it a task and watch it execute.</div>
</div>"""

EMPTY_LOG_HTML = """
<div class="nx-terminal">
  <p class="nx-log-line log-nexus">[NEXUS] System ready. Awaiting forge request...</p>
  <p class="nx-log-line log-default">[NEXUS] Submit a description to begin agent construction.</p>
</div>"""

EMPTY_CODE_HTML = """
<div class="nx-empty">
  <div class="nx-empty-icon">⬡</div>
  <div>No agent selected.</div>
  <div style="margin-top:5px;opacity:0.6">Select an agent to view its generated source code.</div>
</div>"""