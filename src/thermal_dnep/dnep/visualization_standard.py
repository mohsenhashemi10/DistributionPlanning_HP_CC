import pandapower as pp
import plotly.graph_objects as go


def get_ieee33_standard_coordinates():
    """
    مختصات استاندارد IEEE 33-bus مطابق شکل کلاسیک مقالات.
    باس‌ها بر اساس شماره‌گذاری pandapower case33bw (0-indexed).
    """
    coords = {}

    # شاخه اصلی: باس 0 تا 17 (افقی در وسط)
    for b in range(18):
        coords[b] = (float(b), 0.0)

    # انشعاب از باس 1: باس‌های 18 تا 21 (پایین)
    coords[18] = (1.0, -2.0)
    coords[19] = (2.0, -2.0)
    coords[20] = (3.0, -2.0)
    coords[21] = (4.0, -2.0)

    # انشعاب از باس 2: باس‌های 22 تا 24 (بالا)
    coords[22] = (2.0, 2.0)
    coords[23] = (3.0, 2.0)
    coords[24] = (4.0, 2.0)

    # انشعاب از باس 5: باس‌های 25 تا 32 (پایین)
    coords[25] = (5.0, -2.0)
    coords[26] = (6.0, -2.0)
    coords[27] = (7.0, -2.0)
    coords[28] = (8.0, -2.0)
    coords[29] = (9.0, -2.0)
    coords[30] = (10.0, -2.0)
    coords[31] = (11.0, -2.0)
    coords[32] = (12.0, -2.0)

    return coords


def prepare_network_standard(net):
    """اعمال مختصات استاندارد IEEE 33 به شبکه."""
    import pandas as pd

    coords = get_ieee33_standard_coordinates()

    if "bus_geodata" not in net or net.bus_geodata.empty:
        net.bus_geodata = pd.DataFrame(index=net.bus.index, columns=["x", "y"])

    for b in net.bus.index:
        b = int(b)
        if b in coords:
            net.bus_geodata.at[b, "x"] = coords[b][0]
            net.bus_geodata.at[b, "y"] = coords[b][1]
        else:
            # fallback برای باس‌های غیرمنتظره
            net.bus_geodata.at[b, "x"] = float(b)
            net.bus_geodata.at[b, "y"] = 0.0

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


def build_network_figure_standard(net, results, title="IEEE 33-Bus — Standard Layout"):
    """ساخت شکل تعاملی plotly با چیدمان استاندارد IEEE 33."""
    net = prepare_network_standard(net)
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
            text=f"Line {l_idx}: {line_label}<br>Bus {fb} → Bus {tb}",
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
        bus_size.append(max(16, 16 + total_cap * 4))

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

    # --- پست‌های ارتقاء‌یافته ---
    sub_buses = results.get("substations_upgraded", [])
    if sub_buses:
        fig.add_trace(go.Scatter(
            x=[net.bus_geodata.loc[int(b), "x"] for b in sub_buses],
            y=[net.bus_geodata.loc[int(b), "y"] for b in sub_buses],
            mode="markers",
            marker=dict(size=24, symbol="square-open", color="#8e44ad", line_width=3),
            name="Upgraded substation",
            hoverinfo="text",
            hovertext=[f"Bus {b}: Substation upgraded" for b in sub_buses],
        ))

    # --- پست اصلی ---
    fig.add_trace(go.Scatter(
        x=[net.bus_geodata.loc[0, "x"]],
        y=[net.bus_geodata.loc[0, "y"]],
        mode="markers",
        marker=dict(size=26, symbol="diamond", color="#c0392b", line_width=2),
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
        width=1100,
        height=600,
        margin=dict(l=30, r=30, t=60, b=30),
    )

    return fig


def show_results_standard(net, results, electrification_level=None, output_html=None):
    """نمایش تعاملی نتایج با چیدمان استاندارد IEEE 33."""
    title = "IEEE 33-Bus — Standard Layout"
    if electrification_level is not None:
        title += f" — Electrification: {electrification_level:.0%}"

    fig = build_network_figure_standard(net, results, title=title)

    if output_html:
        fig.write_html(output_html)
        print(f"Saved: {output_html}")

    fig.show()

    return fig