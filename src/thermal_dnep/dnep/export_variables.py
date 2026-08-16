import pyomo.environ as pyo
import pandas as pd
from pathlib import Path


def _var_to_dataframe(var, var_name, index_names):
    """
    تبدیل یک متغیر Pyomo به DataFrame.
    فقط مقادیر غیرصفر و مقداردهی‌شده ذخیره می‌شوند.
    """
    rows = []
    for idx in var:
        try:
            val = pyo.value(var[idx], exception=False)
        except Exception:
            continue

        # رد کردن مقادیر None یا NaN
        if val is None:
            continue

        try:
            val = float(val)
        except (TypeError, ValueError):
            continue

        # فقط مقادیر معنادار
        if abs(val) > 1e-6:
            if isinstance(idx, tuple):
                row = dict(zip(index_names, idx))
            else:
                row = {index_names[0]: idx}
            row[var_name] = val
            rows.append(row)

    return pd.DataFrame(rows)


def extract_all_variables(m):
    """
    استخراج تمام متغیرهای تصمیم مدل به صورت دسته‌بندی‌شده.

    Returns
    -------
    dict
        {"investment": {name: DataFrame}, "operation": {name: DataFrame}}
    """
    results = {"investment": {}, "operation": {}}

    # ================================================================
    # متغیرهای احداث (Investment / Capacity)
    # ================================================================

    # خطوط جدید
    if hasattr(m, "x_line_new"):
        results["investment"]["x_line_new"] = _var_to_dataframe(
            m.x_line_new, "x_line_new", ["line", "year"]
        )

    # تقویت خطوط
    if hasattr(m, "x_line_reinforce"):
        results["investment"]["x_line_reinforce"] = _var_to_dataframe(
            m.x_line_reinforce, "x_line_reinforce", ["line", "year"]
        )

    # ارتقاء پست
    if hasattr(m, "x_sub_upgrade"):
        results["investment"]["x_sub_upgrade"] = _var_to_dataframe(
            m.x_sub_upgrade, "x_sub_upgrade", ["bus", "year"]
        )

    # ظرفیت PV
    if hasattr(m, "pv_capacity"):
        results["investment"]["pv_capacity"] = _var_to_dataframe(
            m.pv_capacity, "pv_capacity_mw", ["bus", "year"]
        )

    # ظرفیت DG
    if hasattr(m, "dg_capacity"):
        results["investment"]["dg_capacity"] = _var_to_dataframe(
            m.dg_capacity, "dg_capacity_mw", ["bus", "year"]
        )

    # ظرفیت سرمایش نصب‌شده
    if hasattr(m, "cc_cap"):
        results["investment"]["cc_cap"] = _var_to_dataframe(
            m.cc_cap, "cc_cap_mw", ["bus", "year", "cool_tech"]
        )

    # ظرفیت هیت پمپ نصب‌شده
    if hasattr(m, "hp_cap"):
        results["investment"]["hp_cap"] = _var_to_dataframe(
            m.hp_cap, "hp_cap_mw", ["bus", "year", "heat_tech"]
        )

    # متغیر باینری فعال بودن خطوط
    if hasattr(m, "z_line"):
        results["investment"]["z_line"] = _var_to_dataframe(
            m.z_line, "z_line", ["line", "year"]
        )

    # ================================================================
    # متغیرهای بهره‌برداری (Operation / Hourly)
    # ================================================================

    # استفاده ساعتی سرمایش
    if hasattr(m, "cc_use"):
        results["operation"]["cc_use"] = _var_to_dataframe(
            m.cc_use, "cc_use_mw",
            ["bus", "year", "yp_year", "yp_period", "time", "cool_tech"]
        )

    # استفاده ساعتی هیت پمپ
    if hasattr(m, "hp_use"):
        results["operation"]["hp_use"] = _var_to_dataframe(
            m.hp_use, "hp_use_mw",
            ["bus", "year", "yp_year", "yp_period", "time", "heat_tech"]
        )
    # استفاده ساعتی هیت پمپ سرمایش
    if hasattr(m, "hp_use2"):
        results["operation"]["hp_use2"] = _var_to_dataframe(
            m.hp_use2, "hp_use2_mw",
            ["bus", "year", "yp_year", "yp_period", "time", "heat_tech"]
        )
    # توان وارداتی از پست
    if hasattr(m, "p_import"):
        results["operation"]["p_import"] = _var_to_dataframe(
            m.p_import, "p_import_mw",
            ["bus", "year", "yp_year", "yp_period", "time"]
        )

    # توان DG
    if hasattr(m, "p_dg"):
        results["operation"]["p_dg"] = _var_to_dataframe(
            m.p_dg, "p_dg_mw",
            ["bus", "year", "yp_year", "yp_period", "time"]
        )

    # توان PV
    if hasattr(m, "p_pv"):
        results["operation"]["p_pv"] = _var_to_dataframe(
            m.p_pv, "p_pv_mw",
            ["bus", "year", "yp_year", "yp_period", "time"]
        )

    # بار کل
    if hasattr(m, "total_load"):
        results["operation"]["total_load"] = _var_to_dataframe(
            m.total_load, "total_load_mw",
            ["bus", "year", "yp_year", "yp_period", "time"]
        )

    # جریان خطوط
    if hasattr(m, "f_line"):
        results["operation"]["f_line"] = _var_to_dataframe(
            m.f_line, "f_line_mw",
            ["line", "year", "yp_year", "yp_period", "time"]
        )

    # زاویه ولتاژ
    if hasattr(m, "theta"):
        results["operation"]["theta"] = _var_to_dataframe(
            m.theta, "theta_rad",
            ["bus", "year", "yp_year", "yp_period", "time"]
        )

    # جریان مجازی شعاعی بودن
    if hasattr(m, "g_flow"):
        results["investment"]["g_flow"] = _var_to_dataframe(
            m.g_flow, "g_flow", ["line", "year"]
        )

    return results


def save_all_variables(m, output_dir, prefix="dnep", fmt="csv"):
    """
    ذخیره تمام متغیرهای تصمیم در فایل‌های جداگانه.

    Parameters
    ----------
    m : pyomo.ConcreteModel
        مدل حل‌شده
    output_dir : str or Path
        مسیر ذخیره
    prefix : str
        پیشوند نام فایل‌ها
    fmt : str
        فرمت ذخیره: "csv" یا "parquet"

    Returns
    -------
    dict
        مسیر فایل‌های ذخیره‌شده
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = extract_all_variables(m)
    saved_files = {}

    for category, vars_dict in results.items():
        for var_name, df in vars_dict.items():
            if df.empty:
                continue

            filename = f"{prefix}_{category}_{var_name}.{fmt}"
            filepath = output_dir / filename

            if fmt == "csv":
                df.to_csv(filepath, index=False, encoding="utf-8-sig")
            elif fmt == "parquet":
                df.to_parquet(filepath, index=False)
            else:
                raise ValueError(f"فرمت پشتیبانی‌نشده: {fmt}")

            saved_files[f"{category}.{var_name}"] = str(filepath)

    # خلاصه متغیرها در یک فایل
    summary_rows = []
    for category, vars_dict in results.items():
        for var_name, df in vars_dict.items():
            summary_rows.append({
                "category": category,
                "variable": var_name,
                "n_nonzero_records": len(df),
                "columns": ", ".join(df.columns) if not df.empty else "",
            })

    summary_df = pd.DataFrame(summary_rows)
    summary_path = output_dir / f"{prefix}_variables_summary.{fmt}"
    if fmt == "csv":
        summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")
    else:
        summary_df.to_parquet(summary_path, index=False)
    saved_files["summary"] = str(summary_path)

    print(f"\n{'='*60}")
    print(f"متغیرهای ذخیره‌شده در: {output_dir}")
    print(f"{'='*60}")
    for key, path in saved_files.items():
        print(f"  {key:40s} → {Path(path).name}")

    return saved_files


def print_variable_summary(m):
    """
    چاپ خلاصه سریع متغیرهای تصمیم در کنسول برای بررسی فوری.
    """
    print("\n" + "=" * 70)
    print("VARIABLE SUMMARY")
    print("=" * 70)

    sections = [
        ("INVESTMENT VARIABLES", [
            ("x_line_new", "Lines new", lambda l: pyo.value(m.x_line_new[l]) > 0.5),
            ("x_line_reinforce", "Lines reinforced", lambda l: pyo.value(m.x_line_reinforce[l]) > 0.5),
            ("x_sub_upgrade", "Substations upgraded", lambda b: pyo.value(m.x_sub_upgrade[b]) > 0.5),
        ]),
    ]

    # خطوط جدید
    if hasattr(m, "x_line_new"):
        years = list(m.YEARS)
        y_last = years[-1]
        new_lines = [l for l in m.LINES if pyo.value(m.x_line_new[l, y_last]) > 0.5]
        reinf_lines = [l for l in m.LINES if pyo.value(m.x_line_reinforce[l, y_last]) > 0.5]
        print(f"\nLines new (last year)        : {new_lines}")
        print(f"Lines reinforced (last year) : {reinf_lines}")

    # ظرفیت‌ها
    if hasattr(m, "pv_capacity"):
        years = list(m.YEARS)
        y_last = years[-1]
        pv_total = sum(pyo.value(m.pv_capacity[b, y_last]) for b in m.PV_BUSES)
        dg_total = sum(pyo.value(m.dg_capacity[b, y_last]) for b in m.DG_BUSES)
        print(f"Total PV capacity            : {pv_total:.3f} MW")
        print(f"Total DG capacity            : {dg_total:.3f} MW")

    if hasattr(m, "cc_cap"):
        years = list(m.YEARS)
        y_last = years[-1]
        cc_total = sum(
            pyo.value(m.cc_cap[b, y_last, j])
            for b in m.BUSES for j in m.C_TECHS
        )
        hp_total = sum(
            pyo.value(m.hp_cap[b, y_last, k])
            for b in m.BUSES for k in m.H_TECHS
        )
        print(f"Total cooling capacity       : {cc_total:.3f} MW")
        print(f"Total heat pump capacity     : {hp_total:.3f} MW")

    print("=" * 70)