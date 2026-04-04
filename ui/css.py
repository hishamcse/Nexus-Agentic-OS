APP_CSS = """
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;600&family=Space+Grotesk:wght@400;500;600&display=swap');

:root {
  --bg:        #0b0f0b;
  --surface:   #0f1410;
  --surface-2: #131a14;
  --border:    rgba(74, 222, 128, 0.12);
  --border-hi: rgba(74, 222, 128, 0.30);
  --text:      #d1fae5;
  --muted:     #4b7a5a;
  --dim:       #2d4a35;

  --green:     #4ade80;
  --green-hi:  #86efac;
  --amber:     #fbbf24;
  --red:       #f87171;
  --cyan:      #34d399;
  --blue:      #60a5fa;
  --purple:    #a78bfa;

  --mono: 'JetBrains Mono', 'Fira Code', monospace;
  --sans: 'Space Grotesk', system-ui, sans-serif;
}

.gradio-container {
  background: var(--bg) !important;
  color: var(--text) !important;
  font-family: var(--sans) !important;
}
footer { display: none !important; }

/* ── Shell ── */
.nx-shell {
  border-radius: 16px;
  border: 1px solid var(--border);
  background: linear-gradient(180deg, rgba(74,222,128,0.02) 0%, rgba(0,0,0,0) 100%);
  box-shadow: 0 0 60px rgba(74,222,128,0.04), 0 32px 80px rgba(0,0,0,0.8);
  overflow: hidden;
}

/* ── Hero ── */
.nx-hero {
  padding: 36px 40px 28px;
  background:
    radial-gradient(ellipse at top left, rgba(74,222,128,0.08) 0%, transparent 45%),
    radial-gradient(ellipse at bottom right, rgba(52,211,153,0.05) 0%, transparent 40%),
    linear-gradient(180deg, #0c1410 0%, #0b0f0b 100%);
  border-bottom: 1px solid var(--border);
}
.nx-kicker {
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 0.28em;
  text-transform: uppercase;
  color: var(--cyan);
  margin-bottom: 12px;
}
.nx-title {
  font-family: var(--mono);
  font-size: 36px;
  font-weight: 600;
  color: var(--green-hi);
  letter-spacing: -0.02em;
  margin: 0 0 6px;
  line-height: 1;
}
.nx-title-dim { color: var(--muted); }
.nx-subtitle {
  font-family: var(--sans);
  font-size: 13px;
  color: var(--muted);
  margin: 0 0 20px;
  line-height: 1.6;
}
.nx-badge-row { display: flex; flex-wrap: wrap; gap: 7px; }
.nx-badge {
  padding: 3px 12px;
  border-radius: 999px;
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 0.06em;
  background: rgba(74,222,128,0.06);
  border: 1px solid rgba(74,222,128,0.18);
  color: var(--green);
}
.nx-badge.amber { background:rgba(251,191,36,0.06);border-color:rgba(251,191,36,0.2);color:var(--amber); }
.nx-badge.red   { background:rgba(248,113,113,0.06);border-color:rgba(248,113,113,0.2);color:var(--red); }
.nx-badge.blue  { background:rgba(96,165,250,0.06);border-color:rgba(96,165,250,0.2);color:var(--blue); }
.nx-badge.purple{ background:rgba(167,139,250,0.06);border-color:rgba(167,139,250,0.2);color:var(--purple); }

/* ── Panels ── */
.nx-panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 18px 20px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.3);
}
.nx-panel-label {
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 14px;
}

/* ── Terminal / build log ── */
.nx-terminal {
  background: #050806;
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 16px;
  font-family: var(--mono);
  font-size: 12px;
  line-height: 1.8;
  min-height: 200px;
  overflow-y: auto;
}
.nx-log-line { margin: 0; white-space: pre-wrap; word-break: break-all; }
.log-architect { color: var(--blue); }
.log-spec      { color: var(--purple); }
.log-codegen   { color: var(--amber); }
.log-validator { color: var(--cyan); }
.log-deployer  { color: var(--green); }
.log-monitor   { color: var(--green-hi); }
.log-nexus     { color: var(--red); }
.log-default   { color: var(--muted); }

/* ── Mission control — agent cards ── */
.nx-agent-grid { display: grid; gap: 10px; }
.nx-agent-card {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 14px;
  align-items: center;
  padding: 14px 16px;
  border-radius: 12px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  transition: border-color 0.15s;
}
.nx-agent-card:hover { border-color: var(--border-hi); }
.nx-agent-card.selected { border-color: var(--green); }
.nx-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.dot-running  { background: var(--green); box-shadow: 0 0 6px var(--green); }
.dot-idle     { background: var(--amber); }
.dot-crashed  { background: var(--red); }
.dot-stopped  { background: var(--muted); }
.nx-agent-name {
  font-family: var(--mono);
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 2px;
}
.nx-agent-purpose {
  font-family: var(--sans);
  font-size: 11px;
  color: var(--muted);
  line-height: 1.4;
}
.nx-agent-meta {
  text-align: right;
}
.nx-task-count {
  font-family: var(--mono);
  font-size: 18px;
  font-weight: 600;
  color: var(--green);
}
.nx-agent-status-tag {
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 0.1em;
  padding: 2px 8px;
  border-radius: 4px;
}
.tag-running { background: rgba(74,222,128,0.10); color: var(--green); border: 0.5px solid rgba(74,222,128,0.25); }
.tag-idle    { background: rgba(251,191,36,0.08); color: var(--amber); border: 0.5px solid rgba(251,191,36,0.2); }
.tag-crashed { background: rgba(248,113,113,0.08); color: var(--red);  border: 0.5px solid rgba(248,113,113,0.2); }
.tag-stopped { background: rgba(75,122,90,0.08);  color: var(--muted); border: 0.5px solid rgba(75,122,90,0.2); }

/* ── Inspector task output ── */
.nx-task-output {
  background: #050806;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px;
  font-family: var(--mono);
  font-size: 12px;
  color: var(--green-hi);
  line-height: 1.7;
  min-height: 120px;
  white-space: pre-wrap;
  word-break: break-all;
}

/* ── Lifecycle timeline ── */
.nx-timeline { display: grid; gap: 0; }
.nx-tl-row {
  display: grid;
  grid-template-columns: 80px 24px 1fr;
  gap: 0 10px;
  align-items: start;
  padding-bottom: 12px;
  position: relative;
}
.nx-tl-time {
  font-family: var(--mono);
  font-size: 9px;
  color: var(--muted);
  padding-top: 3px;
  text-align: right;
}
.nx-tl-dot-col {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.nx-tl-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 1.5px solid var(--green);
  background: var(--surface);
  flex-shrink: 0;
}
.nx-tl-line {
  width: 1.5px;
  flex: 1;
  background: var(--border);
  min-height: 20px;
}
.nx-tl-content {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--text);
  line-height: 1.5;
  padding-bottom: 4px;
}
.nx-tl-meta {
  font-size: 10px;
  color: var(--muted);
  margin-top: 2px;
}

/* ── Code viewer ── */
.nx-code-block {
  background: #050806;
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 16px;
  font-family: var(--mono);
  font-size: 11px;
  color: #a7f3d0;
  line-height: 1.65;
  overflow-x: auto;
  white-space: pre;
  max-height: 500px;
  overflow-y: auto;
}

/* ── Metric cards ── */
.nx-metric-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 16px; }
.nx-metric {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 14px 16px;
  text-align: center;
}
.nx-metric-val {
  font-family: var(--mono);
  font-size: 28px;
  font-weight: 600;
  color: var(--green);
  margin-bottom: 4px;
}
.nx-metric-lbl {
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--muted);
}

/* ── Forge form ── */
.gradio-container input, .gradio-container textarea, .gradio-container select {
  background: var(--surface) !important;
  color: var(--text) !important;
  border: 1px solid var(--border) !important;
  border-radius: 10px !important;
  font-family: var(--sans) !important;
}
.gradio-container input:focus, .gradio-container textarea:focus {
  border-color: rgba(74,222,128,0.4) !important;
  box-shadow: 0 0 0 2px rgba(74,222,128,0.07) !important;
  outline: none !important;
}
.gradio-container label, .gradio-container .label-wrap span {
  font-family: var(--mono) !important;
  font-size: 9px !important;
  letter-spacing: 0.16em !important;
  text-transform: uppercase !important;
  color: var(--muted) !important;
}
.gradio-container button.primary {
  background: linear-gradient(135deg, #166534, #14532d) !important;
  border: 1px solid rgba(74,222,128,0.25) !important;
  color: var(--green-hi) !important;
  font-family: var(--mono) !important;
  font-size: 11px !important;
  letter-spacing: 0.12em !important;
  border-radius: 10px !important;
  padding: 12px 24px !important;
}
.gradio-container button.primary:hover {
  background: linear-gradient(135deg, #15803d, #166534) !important;
}
.gradio-container button.secondary {
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  color: var(--green) !important;
  font-family: var(--mono) !important;
  font-size: 11px !important;
  letter-spacing: 0.10em !important;
  border-radius: 10px !important;
}
.gradio-container button.secondary:hover {
  border-color: var(--border-hi) !important;
}

/* ── Deploy banner ── */
.nx-deploy-success {
  background: rgba(74,222,128,0.07);
  border: 1px solid rgba(74,222,128,0.25);
  border-radius: 12px;
  padding: 16px 18px;
  font-family: var(--mono);
  font-size: 13px;
  color: var(--green);
}
.nx-deploy-error {
  background: rgba(248,113,113,0.07);
  border: 1px solid rgba(248,113,113,0.2);
  border-radius: 12px;
  padding: 16px 18px;
  font-family: var(--mono);
  font-size: 13px;
  color: var(--red);
}

/* ── Empty state ── */
.nx-empty {
  text-align: center;
  padding: 52px 24px;
  font-family: var(--mono);
  font-size: 12px;
  color: var(--muted);
  letter-spacing: 0.06em;
}
.nx-empty-icon { font-size: 28px; margin-bottom: 12px; opacity: 0.35; }
"""