import pyomo.environ as pyo
import pandas as pd


def extract_results(m, tech=None) -> dict:
    """استخراج تصمیمات بهینه به ازای آخرین سال + تایم‌لاین."""
    years = list(m.YEARS)
    y_last = years[-1]

    results = {
        "last_year": y_last,
        "total_cost_npv": round(pyo.value(m.obj), 2),
        "lines_new": [],
        "lines_reinforced": [],
        "substations_upgraded": [],
        "pv_capacity": {},
        "dg_capacity": {},
        "cc_capacity": {},
        "hp_capacity": {},
        "timeline": [],
    }

    for l in m.LINES:
        if pyo.value(m.x_line_new[l, y_last]) > 0.5:
            results["lines_new"].append(l)
        if pyo.value(m.x_line_reinforce[l, y_last]) > 0.5:
            results["lines_reinforced"].append(l)

    for b in m.SUB_BUSES:
        if pyo.value(m.x_sub_upgrade[b, y_last]) > 0.5:
            results["substations_upgraded"].append(b)

    for b in m.PV_BUSES:
        val = pyo.value(m.pv_capacity[b, y_last])
        if val > 1e-3:
            results["pv_capacity"][b] = round(val, 3)

    for b in m.DG_BUSES:
        val = pyo.value(m.dg_capacity[b, y_last])
        if val > 1e-3:
            results["dg_capacity"][b] = round(val, 3)

    # ✅ ظرفیت سرمایش نصب‌شده به ازای هر فناوری
    for b in m.BUSES:
        for j in m.C_TECHS:
            val = pyo.value(m.cc_cap[b, y_last, j])
            if val > 1e-3:
                name = tech.cooling_technologies[j].name if tech else j
                results["cc_capacity"].setdefault(b, {})[name] = round(val, 3)

    # ✅ ظرفیت هیت پمپ نصب‌شده به ازای هر فناوری
    for b in m.BUSES:
        for k in m.H_TECHS:
            val = pyo.value(m.hp_cap[b, y_last, k])
            if val > 1e-3:
                name = tech.heating_technologies[k].name if tech else k
                results["hp_capacity"].setdefault(b, {})[name] = round(val, 3)

    # تایم‌لاین
    for y in years:
        entry = {
            "year": y,
            "n_lines_new": sum(1 for l in m.LINES if pyo.value(m.x_line_new[l, y]) > 0.5),
            "n_lines_reinf": sum(1 for l in m.LINES if pyo.value(m.x_line_reinforce[l, y]) > 0.5),
            "n_sub_upgraded": sum(1 for b in m.SUB_BUSES if pyo.value(m.x_sub_upgrade[b, y]) > 0.5),
            "total_pv_mw": round(sum(pyo.value(m.pv_capacity[b, y]) for b in m.PV_BUSES), 3),
            "total_dg_mw": round(sum(pyo.value(m.dg_capacity[b, y]) for b in m.DG_BUSES), 3),
            "total_cc_mw": round(sum(
                pyo.value(m.cc_cap[b, y, j]) for b in m.BUSES for j in m.C_TECHS), 3),
            "total_hp_mw": round(sum(
                pyo.value(m.hp_cap[b, y, k]) for b in m.BUSES for k in m.H_TECHS), 3),
        }
        results["timeline"].append(entry)

    return results


def results_to_dataframe(results: dict) -> dict:
    """تبدیل نتایج به DataFrame برای ذخیره."""
    dfs = {}

    summary_row = {
        "last_year": results["last_year"],
        "total_cost_npv": results["total_cost_npv"],
        "n_lines_new": len(results["lines_new"]),
        "n_lines_reinforced": len(results["lines_reinforced"]),
        "n_substations_upgraded": len(results["substations_upgraded"]),
        "total_pv_mw": sum(results["pv_capacity"].values()),
        "total_dg_mw": sum(results["dg_capacity"].values()),
        "total_cc_mw": sum(
            sum(v.values()) for v in results["cc_capacity"].values()
        ),
        "total_hp_mw": sum(
            sum(v.values()) for v in results["hp_capacity"].values()
        ),
    }
    dfs["summary"] = pd.DataFrame([summary_row])

    bus_rows = []
    for b in set(list(results["cc_capacity"].keys()) + list(results["hp_capacity"].keys())):
        bus_rows.append({
            "bus": b,
            "cc_capacities": str(results["cc_capacity"].get(b, {})),
            "hp_capacities": str(results["hp_capacity"].get(b, {})),
            "pv_mw": results["pv_capacity"].get(b, 0.0),
            "dg_mw": results["dg_capacity"].get(b, 0.0),
        })
    dfs["bus_details"] = pd.DataFrame(bus_rows)

    dfs["timeline"] = pd.DataFrame(results["timeline"])

    return dfs


def run_sensitivity_analysis(
    parquet_path: str,
    levels: list = None,
    solver_name: str = "appsi_highs",
) -> pd.DataFrame:
    """اجرای مدل برای چندین سطح برقی‌سازی."""
    if levels is None:
        levels = [0.0, 0.1, 0.3, 0.5, 0.7, 1.0]

    from .solve import build_and_solve

    rows = []
    for alpha in levels:
        print(f"\n{'='*50}")
        print(f"سناریوی برقی‌سازی: {alpha:.0%}")
        print(f"{'='*50}")

        m, res = build_and_solve(
            parquet_path,
            electrification_level=alpha,
            solver_name=solver_name,
        )

        extracted = extract_results(m)

        total_pv = sum(extracted["pv_capacity"].values()) if extracted["pv_capacity"] else 0.0
        total_dg = sum(extracted["dg_capacity"].values()) if extracted["dg_capacity"] else 0.0
        total_cc = sum(sum(v.values()) for v in extracted["cc_capacity"].values())
        total_hp = sum(sum(v.values()) for v in extracted["hp_capacity"].values())

        rows.append({
            "electrification_pct": alpha,
            "total_cost_npv": extracted["total_cost_npv"],
            "n_lines_new": len(extracted["lines_new"]),
            "n_lines_reinforced": len(extracted["lines_reinforced"]),
            "n_substations_upgraded": len(extracted["substations_upgraded"]),
            "total_pv_mw": round(total_pv, 3),
            "total_dg_mw": round(total_dg, 3),
            "total_cc_mw": round(total_cc, 3),
            "total_hp_mw": round(total_hp, 3),
        })

    return pd.DataFrame(rows)