"""
Nexus — Live Graph Node Visualiser  v2
Bigger nodes, labels + role descriptions below each node,
connection flow indicators, retry counter on arc, topology key.
Canvas: 900 × 300
"""

# Node definitions: (id, short_label, role_desc, cx, cy, color)
NODES = [
    ("architect",   "ARCHITECT",   "designs topology\n& tools",     110, 120, "#378ADD"),
    ("spec_writer", "SPEC",        "writes JSON\nagent spec",        270, 120, "#7F77DD"),
    ("code_gen",    "CODE GEN",    "generates\nrunnable Python",     430, 120, "#BA7517"),
    ("validator",   "VALIDATOR",   "3-stage sandbox\nvalidation",    590, 120, "#E24B4A"),
    ("deployer",    "DEPLOYER",    "registers &\nspawns process",    750, 120, "#1D9E75"),
    ("monitor",     "MONITOR",     "health checks\n& restarts",      750,  38, "#D4537E"),
]

LOG_TO_NODE = {
    "[ARCHITECT]":   "architect",
    "[SPEC WRITER]": "spec_writer",
    "[CODE GEN]":    "code_gen",
    "[VALIDATOR]":   "validator",
    "[DEPLOYER]":    "deployer",
    "[MONITOR]":     "monitor",
}

NODE_R = 40   # node radius


def _active_node_from_log(build_log: list) -> tuple:
    done_nodes  = set()
    active_node = ""
    retry_count = 0
    last_seen   = {}

    for i, line in enumerate(build_log):
        for prefix, node in LOG_TO_NODE.items():
            if prefix in line:
                last_seen[node] = i
                active_node = node
                for n, idx in last_seen.items():
                    if idx < i:
                        done_nodes.add(n)
        if "[VALIDATOR]" in line and "retry" in line.lower():
            retry_count += 1
        if any("[DEPLOYER]" in l or "[MONITOR]" in l for l in build_log):
            done_nodes.update({"architect", "spec_writer", "code_gen", "validator", "deployer"})

    return active_node, done_nodes, retry_count


def render_graph_svg(build_log: list) -> str:
    active_node, done_nodes, retry_count = _active_node_from_log(build_log or [])
    idle = not build_log

    W, H = 900, 290

    # ── Node renderer ──────────────────────────────────────────────────────────
    def _node(node_id, label, role, cx, cy, color):
        is_active = node_id == active_node
        is_done   = node_id in done_nodes and not is_active
        is_idle   = not is_active and not is_done

        # Visual state
        if is_active:
            fill    = f"{color}30"
            stroke  = color
            stroke_w = "2.5"
            text_c  = color
            # Pulse ring
            pulse = f'''<circle cx="{cx}" cy="{cy}" r="{NODE_R+10}" fill="none"
              stroke="{color}" stroke-width="1" opacity="0.0">
              <animate attributeName="r" values="{NODE_R};{NODE_R+18};{NODE_R}" dur="1.6s" repeatCount="indefinite"/>
              <animate attributeName="opacity" values="0.4;0;0.4" dur="1.6s" repeatCount="indefinite"/>
            </circle>'''
        elif is_done:
            fill    = f"{color}18"
            stroke  = f"{color}70"
            stroke_w = "1.5"
            text_c  = f"{color}cc"
            pulse   = ""
        else:
            fill    = "rgba(10,16,12,0.7)"
            stroke  = "rgba(74,222,128,0.18)"
            stroke_w = "1"
            text_c  = "#3d5a42"
            pulse   = ""

        # Done checkmark
        check = f'<text x="{cx+NODE_R-6}" y="{cy-NODE_R+10}" font-family="monospace" font-size="11" fill="{color}cc">✓</text>' if is_done else ""

        # Active dot indicator
        active_dot = f'<circle cx="{cx}" cy="{cy-NODE_R-8}" r="4" fill="{color}"><animate attributeName="opacity" values="1;0.2;1" dur="0.8s" repeatCount="indefinite"/></circle>' if is_active else ""

        # Label lines (split on \n)
        role_lines = role.split("\n")
        label_y  = cy + NODE_R + 18
        role_y1  = cy + NODE_R + 33
        role_y2  = cy + NODE_R + 47 if len(role_lines) > 1 else 0

        role_svg = f'<text x="{cx}" y="{role_y1}" text-anchor="middle" font-family="JetBrains Mono,monospace" font-size="8.5" fill="{text_c}" opacity="0.7">{role_lines[0]}</text>'
        if role_y2:
            role_svg += f'<text x="{cx}" y="{role_y2}" text-anchor="middle" font-family="JetBrains Mono,monospace" font-size="8.5" fill="{text_c}" opacity="0.7">{role_lines[1]}</text>'

        return f"""
{pulse}
<circle cx="{cx}" cy="{cy}" r="{NODE_R}" fill="{fill}" stroke="{stroke}" stroke-width="{stroke_w}"/>
{check}
{active_dot}
<text x="{cx}" y="{cy+5}" text-anchor="middle"
  font-family="JetBrains Mono,monospace" font-size="10" font-weight="700"
  letter-spacing="0.5" fill="{text_c}">{label}</text>
<text x="{cx}" y="{label_y}" text-anchor="middle"
  font-family="JetBrains Mono,monospace" font-size="9" font-weight="600"
  fill="{text_c}">{label}</text>
{role_svg}"""

    # ── Edges (horizontal chain) ───────────────────────────────────────────────
    h_nodes = [n for n in NODES if n[0] != "monitor"]
    edges_svg = ""
    for i in range(len(h_nodes) - 1):
        nid1, _, _, x1, y1, c1 = h_nodes[i]
        nid2, _, _, x2, y2, c2 = h_nodes[i + 1]
        is_lit = h_nodes[i][0] in done_nodes or h_nodes[i][0] == active_node
        stroke = c1 if is_lit else "rgba(74,222,128,0.15)"
        sw     = "1.8" if is_lit else "1"
        # Line
        edges_svg += f'<line x1="{x1+NODE_R}" y1="{y1}" x2="{x2-NODE_R}" y2="{y2}" stroke="{stroke}" stroke-width="{sw}" opacity="0.8"/>'
        # Arrow
        ax = x2 - NODE_R - 2
        edges_svg += f'<polygon points="{ax-10},{y2-5} {ax},{y2} {ax-10},{y2+5}" fill="{stroke}" opacity="0.8"/>'

    # Deployer → Monitor vertical edge
    dep_id, _, _, dep_x, dep_y, dep_c = NODES[4]
    mon_id, _, _, mon_x, mon_y, mon_c = NODES[5]
    dep_lit  = dep_id in done_nodes or dep_id == active_node
    v_stroke = dep_c if dep_lit else "rgba(74,222,128,0.15)"
    v_sw     = "1.8" if dep_lit else "1"
    edges_svg += f'<line x1="{dep_x}" y1="{dep_y-NODE_R}" x2="{mon_x}" y2="{mon_y+NODE_R}" stroke="{v_stroke}" stroke-width="{v_sw}" opacity="0.8"/>'
    edges_svg += f'<polygon points="{mon_x-5},{mon_y+NODE_R+8} {mon_x},{mon_y+NODE_R} {mon_x+5},{mon_y+NODE_R+8}" fill="{v_stroke}" opacity="0.8"/>'

    # ── Retry arc: Validator → CodeGen ────────────────────────────────────────
    val_id, _, _, val_x, val_y, val_c = NODES[3]
    cg_id,  _, _, cg_x,  cg_y,  cg_c = NODES[2]
    arc_color   = "#E24B4A" if retry_count > 0 else "rgba(229,62,62,0.25)"
    arc_opacity = "1" if retry_count > 0 else "0.4"
    retry_txt   = f"retry ×{retry_count}" if retry_count > 0 else "retry loop"
    retry_svg = f'''
<path d="M {val_x} {val_y+NODE_R} Q 510 230 {cg_x} {cg_y+NODE_R}"
  fill="none" stroke="{arc_color}" stroke-width="1.4" stroke-dasharray="5,4" opacity="{arc_opacity}"/>
<polygon points="{cg_x+8},{cg_y+NODE_R+10} {cg_x},{cg_y+NODE_R} {cg_x-8},{cg_y+NODE_R+10}"
  fill="{arc_color}" opacity="{arc_opacity}"/>
<text x="510" y="248" text-anchor="middle"
  font-family="JetBrains Mono,monospace" font-size="9" fill="{arc_color}" opacity="{arc_opacity}"
  letter-spacing="0.5">{retry_txt}</text>'''

    # ── All nodes ─────────────────────────────────────────────────────────────
    nodes_svg = "".join(_node(*n) for n in NODES)

    # ── Status bar at top right ────────────────────────────────────────────────
    if idle:
        status_txt = "AWAITING FORGE REQUEST"
        status_c   = "rgba(74,222,128,0.3)"
    elif active_node:
        status_txt = f"RUNNING · {active_node.upper().replace('_',' ')}"
        status_c   = "#4ade80"
    elif done_nodes:
        status_txt = "COMPLETE"
        status_c   = "#4ade80"
    else:
        status_txt = "READY"
        status_c   = "rgba(74,222,128,0.4)"

    status_svg = f'''<text x="{W-12}" y="16" text-anchor="end"
      font-family="JetBrains Mono,monospace" font-size="9" fill="{status_c}"
      letter-spacing="1.5">{status_txt}</text>'''

    # ── Legend key ────────────────────────────────────────────────────────────
    legend_items = [
        ("waiting",  "rgba(74,222,128,0.18)", "#3d5a42"),
        ("active",   "#378ADD",              "#378ADD"),
        ("done",     "#1D9E75",              "#1D9E75cc"),
    ]
    legend_svg = ""
    lx = 12
    for label, fill, tc in legend_items:
        legend_svg += f'<circle cx="{lx+6}" cy="{H-16}" r="5" fill="{fill}" opacity="0.6"/>'
        legend_svg += f'<text x="{lx+15}" y="{H-12}" font-family="JetBrains Mono,monospace" font-size="8" fill="{tc}" opacity="0.7">{label}</text>'
        lx += 62

    return f"""<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg"
     style="width:100%;height:auto;display:block;max-height:300px">
  <rect width="{W}" height="{H}" fill="#050806" rx="12"/>
  <text x="12" y="16" font-family="JetBrains Mono,monospace" font-size="8.5"
    fill="rgba(74,222,128,0.4)" letter-spacing="2">NEXUS META-GRAPH</text>
  {status_svg}
  {edges_svg}
  {retry_svg}
  {nodes_svg}
  {legend_svg}
</svg>"""