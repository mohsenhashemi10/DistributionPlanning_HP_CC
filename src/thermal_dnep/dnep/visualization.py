import pandapower as pp
import plotly.graph_objects as go
from collections import deque


def _compute_radial_coordinates(net, root_bus=0):
    """
    ساخت مختصات شعاعی برای شبکه IEEE 33 با BFS.
    - محور X: ترتیب درختی (BFS)
    - محور Y: عمق از ریشه
    """
    # ساخت adjacency لیست
    adj = {b: [] for b in net.bus.index}
    for _, row in net.line.iterrows():
        fb, tb = int(row["from_bus"]), int(row["to_bus"])
        adj[fb].append(tb)
        adj[tb].append(fb)

    # BFS از ریشه
    depth = {}
    order = []
    visited = {root_bus}
    queue = deque([(root_bus, 0)])

    while queue:
        b, d = queue.popleft()
        depth[b] = d
        order.append(b)
        for nb in adj[b]:
            if nb not in visited:
                visited.add(nb)
                queue.append((nb, d + 1))

    # مرتب‌سازی باس‌ها بر اساس عمق و سپس شماره برای چیدمان منظم
    by_depth = {}
    for b in order:
        by_depth.setdefault(depth[b], []).append(b)
    for d in by_depth:
        by_depth[d].sort()

    # اختصاص مختصات
    coords = {}
    max_depth = max(by_depth.keys()) if by_depth else 1

    for d, buses in by_depth.items():
        n = len(buses)
        for i, b in enumerate(buses):
            # x: پخش افقی متناسب با تعداد باس‌های هم‌عمق
            # y: عمق از بالا به پایین (عمیق‌تر = پایین‌تر)
            if n > 1:
                x = i - (n - 1) / 2
            else:
                x = 0.0
            y = max_depth - d  # بالاترین عمق در بالا
            coords[b] = (float(x), float(y))

    return coords


def prepare_network(net):
    """ساخت مختصات شعاعی بدون نیاز به igraph."""
    coords = _compute_radial_coordinates(net, root_bus=0)

    # پر کردن bus_geodata
    if "bus_geodata" not in net or net.bus_geodata.empty:
        import pandas as pd
        net.bus_geodata = pd.DataFrame(index=net.bus.index, columns=["x", "y"])

    for b, (x, y) in coords.items():
        net.bus_geodata.at[b, "x"] = x
        net.bus_geodata.at[b, "y"] = y

    return net


def _aggregate_capacity_by_bus(results):
    """تجمیع ظرفیت هر نوع تجهیزات به ازای هر باس."""
    cap = {}

    for b, techs in results.get("cc_capacity", {}).items():
        cap.setdefault(b, {"cc": 0, "hp": 0, "pv": 0, "dg": 0})
        cap[b]["cc"] += sum(techs.values())

    for b, techs in results.get("hp_capacity", {}).items():
        cap.setdefault(b, {"cc": 0, "hp": 0, "pv": 0, "dg": 0})
        cap[b]["hp"] += sum(techs.values())

    for b, v in results.get("pv_capacity", {}).items():
        cap.setdefault(b, {"cc": 0, "hp": 0, "pv": 0, "dg": 0})
        cap[b]["pv"] += v

    for b, v in results.get("dg_capacity", {}).items():
        cap.setdefault(b, {"cc": 0, "hp": 0, "pv": 0, "dg": 0})
        cap[b]["dg"] += v

    return cap


def build_network_figure(net, results, title="Distribution Network Expansion Results"):
    """ساخت شکل تعاملی plotly از شبکه با نتایج بهینه‌سازی."""
    net = prepare_network(net)
    cap_by_bus = _aggregate_capacity_by_bus(results)

    fig = go.Figure()

    # --- رسم خطوط ---
    reinforced_lines = set(results.get("lines_reinforced", []))
    new_lines = set(results.get("lines_new", []))

    for l_idx, l in net.line.iterrows():
        fb = int(l["from_bus"])
        tb = int(l["to_bus"])

        x0, y0 = net.bus_geodata.loc[fb, ["x", "y"]]
        x1, y1 = net.bus_geodata.loc[tb, ["x", "y"]]

        if l_idx in new_lines:
            line_color, line_width, line_label = "#e74c3c", 5, "New line"
        elif l_idx in reinforced_lines:
            line_color, line_width, line_label = "#f39c12", 5, "Reinforced"
        else:
            line_color, line_width, line_label = "#95a5a6", 2, "Existing"

        fig.add_trace(go.Scatter(
            x=[x0, x1, None],
            y=[y0, y1, None],
            mode="lines",
            line=dict(width=line_width, color=line_color),
            hoverinfo="text",
            text=f"Line {l_idx}: {line_label}<br>{fb} → {tb}",
            showlegend=False,
        ))

    # --- رسم باس‌ها ---
    bus_x, bus_y, bus_text, bus_size, bus_color = [], [], [], [], []

    for b in net.bus.index:
        b = int(b)
        x, y = net.bus_geodata.loc[b, ["x", "y"]]
        bus_x.append(x)
        bus_y.append(y)

        cap = cap_by_bus.get(b, {"cc": 0, "hp": 0, "pv": 0, "dg": 0})
        total_cap = cap["cc"] + cap["hp"] + cap["pv"] + cap["dg"]

        bus_color.append(total_cap)
        bus_size.append(max(14, 14 + total_cap * 4))

        tooltip = (
            f"Bus {b}<br>"
            f"Cooling cap: {cap['cc']:.2f} MW<br>"
            f"Heat pump cap: {cap['hp']:.2f} MW<br>"
            f"PV cap: {cap['pv']:.2f} MW<br>"
            f"DG cap: {cap['dg']:.2f} MW<br>"
            f"Total: {total_cap:.2f} MW"
        )
        bus_text.append(tooltip)

    fig.add_trace(go.Scatter(
        x=bus_x,
        y=bus_y,
        mode="markers+text",
        text=[str(b) for b in net.bus.index],
        textposition="top center",
        marker=dict(
            size=bus_size,
            color=bus_color,
            colorscale="Viridis",
            showscale=True,
            colorbar=dict(title="Total Cap (MW)"),
            line=dict(width=1.5, color="#2c3e50"),
        ),
        hoverinfo="text",
        hovertext=bus_text,
        name="Buses",
    ))

    # --- علائم پست‌ها ---
    sub_buses = results.get("substations_upgraded", [])
    if sub_buses:
        fig.add_trace(go.Scatter(
            x=[net.bus_geodata.loc[int(b), "x"] for b in sub_buses],
            y=[net.bus_geodata.loc[int(b), "y"] for b in sub_buses],
            mode="markers",
            marker=dict(size=22, symbol="square-open", color="#8e44ad", line_width=3),
            name="Upgraded substation",
            hoverinfo="text",
            hovertext=[f"Bus {b}: Substation upgraded" for b in sub_buses],
        ))

    # --- پست اصلی (root) ---
    fig.add_trace(go.Scatter(
        x=[net.bus_geodata.loc[0, "x"]],
        y=[net.bus_geodata.loc[0, "y"]],
        mode="markers",
        marker=dict(size=24, symbol="diamond", color="#c0392b", line_width=2),
        name="Root bus (substation)",
        hoverinfo="text",
        hovertext=["Bus 0: Root substation"],
    ))

    # --- تنظیمات نهایی ---
    fig.update_layout(
        title=title,
        showlegend=True,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        plot_bgcolor="white",
        width=1000,
        height=750,
        margin=dict(l=20, r=20, t=60, b=20),
    )

    return fig


def show_results(net, results, electrification_level=None, output_html=None, save_path=None):
    """نمایش تعاملی نتایج."""
    title = "Distribution Network Expansion Results"
    if electrification_level is not None:
        title += f" — Electrification: {electrification_level:.0%}"

    fig = build_network_figure(net, results, title=title)

    # پشتیبانی از هر دو نام پارامتر
    target = save_path or output_html
    if target:
        fig.write_html(target)
        print(f"Saved: {target}")

    fig.show()

    return fig