from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import igraph as ig


# ============================================================
# LAYOUT
# ============================================================

def _create_bus_layout(net):
    """
    Create bus coordinates for visualization.

    Priority:
        1. pandapower bus_geodata
        2. generated circular layout
    """

    buses = list(net.bus.index)

    # --------------------------------------------------------
    # Use geographical/network coordinates if available
    # --------------------------------------------------------

    if (
        hasattr(net, "bus_geodata")
        and isinstance(net.bus_geodata, pd.DataFrame)
        and not net.bus_geodata.empty
    ):

        geodata = net.bus_geodata.copy()

        if {"x", "y"}.issubset(geodata.columns):

            coordinates = {}

            for bus in buses:

                if bus in geodata.index:

                    x = geodata.loc[bus, "x"]
                    y = geodata.loc[bus, "y"]

                    if pd.notna(x) and pd.notna(y):

                        coordinates[bus] = (
                            float(x),
                            float(y),
                        )

            if len(coordinates) == len(buses):

                return coordinates

    # --------------------------------------------------------
    # Fallback: circular layout
    # --------------------------------------------------------

    angles = np.linspace(
        0,
        2 * np.pi,
        len(buses),
        endpoint=False,
    )

    coordinates = {}

    for bus, angle in zip(buses, angles):

        coordinates[bus] = (
            float(np.cos(angle)),
            float(np.sin(angle)),
        )

    return coordinates


# ============================================================
# RESULT EXTRACTION
# ============================================================

def _get_result_value(
    results,
    name,
    default=0,
):
    """
    Safely extract a result value.
    """

    if results is None:
        return default

    if isinstance(results, dict):

        return results.get(
            name,
            default,
        )

    if hasattr(results, name):

        return getattr(
            results,
            name,
        )

    return default


# ============================================================
# BUILD NETWORK FIGURE
# ============================================================

def build_network_figure(
    net,
    results,
    title="Distribution Network",
):
    """
    Build an igraph-based visualization of the
    optimized distribution network.

    The function does not require bus_geodata.
    """

    # --------------------------------------------------------
    # Buses
    # --------------------------------------------------------

    buses = list(net.bus.index)

    bus_position = _create_bus_layout(net)

    bus_to_vertex = {
        bus: i
        for i, bus in enumerate(buses)
    }

    # --------------------------------------------------------
    # Create igraph
    # --------------------------------------------------------

    graph = ig.Graph(
        n=len(buses),
        directed=False,
    )

    graph.vs["bus"] = buses

    # --------------------------------------------------------
    # Existing lines
    # --------------------------------------------------------

    for line_idx, line in net.line.iterrows():

        from_bus = int(
            line["from_bus"]
        )

        to_bus = int(
            line["to_bus"]
        )

        if (
            from_bus not in bus_to_vertex
            or to_bus not in bus_to_vertex
        ):
            continue

        graph.add_edge(
            bus_to_vertex[from_bus],
            bus_to_vertex[to_bus],
        )

    # --------------------------------------------------------
    # New candidate lines
    #
    # If optimization results provide candidate lines,
    # they can be added here.
    # --------------------------------------------------------

    new_lines = _get_result_value(
        results,
        "lines_new",
        [],
    )

    if new_lines is None:
        new_lines = []

    for item in new_lines:

        try:

            from_bus = int(item[0])
            to_bus = int(item[1])

        except (
            TypeError,
            ValueError,
            IndexError,
        ):

            continue

        if (
            from_bus in bus_to_vertex
            and to_bus in bus_to_vertex
        ):

            graph.add_edge(
                bus_to_vertex[from_bus],
                bus_to_vertex[to_bus],
            )

    # --------------------------------------------------------
    # Plot
    # --------------------------------------------------------

    fig, ax = plt.subplots(
        figsize=(12, 8)
    )

    # --------------------------------------------------------
    # Draw lines
    # --------------------------------------------------------

    for edge in graph.es:

        source = graph.vs[
            edge.source
        ]["bus"]

        target = graph.vs[
            edge.target
        ]["bus"]

        x0, y0 = bus_position[
            source
        ]

        x1, y1 = bus_position[
            target
        ]

        ax.plot(
            [x0, x1],
            [y0, y1],
            linewidth=1.5,
        )

    # --------------------------------------------------------
    # Draw buses
    # --------------------------------------------------------

    for bus in buses:

        x, y = bus_position[bus]

        ax.scatter(
            x,
            y,
            s=100,
            zorder=5,
        )

        ax.text(
            x,
            y,
            str(bus),
            ha="center",
            va="center",
            fontsize=8,
            zorder=6,
        )

    # --------------------------------------------------------
    # Title
    # --------------------------------------------------------

    ax.set_title(
        title,
        fontsize=14,
    )

    ax.set_aspect(
        "equal",
        adjustable="datalim",
    )

    ax.axis("off")

    fig.tight_layout()

    return fig


# ============================================================
# SHOW RESULTS
# ============================================================

def show_results(
    net,
    results,
    title="Optimized Distribution Network",
    save_path=None,
):
    """
    Display and optionally save optimization results.
    """

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    total_cost = _get_result_value(
        results,
        "total_cost",
        None,
    )

    lines_new = _get_result_value(
        results,
        "lines_new",
        0,
    )

    lines_reinforced = _get_result_value(
        results,
        "lines_reinforced",
        0,
    )

    substations_upgraded = _get_result_value(
        results,
        "substations_upgraded",
        0,
    )

    print("\n" + "=" * 70)
    print("OPTIMIZATION RESULTS")
    print("=" * 70)

    if total_cost is not None:

        print(
            f"Total cost (NPV): "
            f"{total_cost:,.0f}"
        )

    print(
        f"Lines new: "
        f"{lines_new}"
    )

    print(
        f"Lines reinforced: "
        f"{lines_reinforced}"
    )

    print(
        f"Substations upgraded: "
        f"{substations_upgraded}"
    )

    # --------------------------------------------------------
    # Figure
    # --------------------------------------------------------

    fig = build_network_figure(
        net,
        results,
        title=title,
    )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    if save_path is not None:

        save_path = Path(
            save_path
        )

        save_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        fig.savefig(
            save_path,
            dpi=300,
            bbox_inches="tight",
        )

        print(
            f"\nFigure saved to:"
            f"\n{save_path}"
        )

    # --------------------------------------------------------
    # Show
    # --------------------------------------------------------

    plt.show()

    return fig