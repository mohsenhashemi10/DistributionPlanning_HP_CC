import pandapower as pp
import numpy as np


def get_line_data(net):
    """استخراج اطلاعات خطوط به صورت دیکشنری"""
    lines = {}
    for idx, row in net.line.iterrows():
        from_bus = int(row["from_bus"])
        vn_kv = net.bus.loc[from_bus, "vn_kv"]

        # ظرفیت نامی خط: S = √3 × V × I
        base_capacity_mva = np.sqrt(3) * vn_kv * row["max_i_ka"]

        lines[idx] = {
            "from_bus": from_bus,
            "to_bus": int(row["to_bus"]),
            "r_ohm_per_km": row["r_ohm_per_km"],
            "x_ohm_per_km": row["x_ohm_per_km"],
            "length_km": row["length_km"],
            "max_i_ka": row["max_i_ka"],
            "base_capacity_mva": base_capacity_mva,
        }
    return lines


def get_bus_data(net):
    """استخراج اطلاعات باس‌ها"""
    buses = {}
    for idx, row in net.bus.iterrows():
        buses[int(idx)] = {
            "name": row.get("name", f"bus_{idx}"),
            "vn_kv": row["vn_kv"],
            "type": row.get("type", "b"),
        }
    return buses