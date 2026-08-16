import pyomo.environ as pyo


def build_objective(m, tech, periods):
    """
    min Σ_y disc(y) × [C_inv(y) + C_op(y) − B_avoided(y)]
    """

    def obj_rule(m):
        expr = 0.0
        crf = tech.crf
        years = list(m.YEARS)
        y_min = years[0]

        for y in years:
            disc = 1.0 / (1.0 + tech.discount_rate) ** (y - y_min)
            cost_y = 0.0

            # ============================================================
            # هزینه‌های سرمایه‌ای (فقط افزایش نسبت به سال قبل)
            # ============================================================

            for l in m.LINES:
                prev = m.x_line_new[l, y - 1] if y > y_min else 0
                inc = m.x_line_new[l, y] - prev
                cost_y += crf * tech.line_build_cost_per_km * m.line_length[l] * inc

            for l in m.LINES:
                prev = m.x_line_reinforce[l, y - 1] if y > y_min else 0
                inc = m.x_line_reinforce[l, y] - prev
                cost_y += crf * tech.line_reinforce_cost_per_km * m.line_length[l] * inc

            for b in m.SUB_BUSES:
                prev = m.x_sub_upgrade[b, y - 1] if y > y_min else 0
                inc = m.x_sub_upgrade[b, y] - prev
                cost_y += crf * tech.substation_upgrade_cost * inc

            for b in m.PV_BUSES:
                prev = m.pv_capacity[b, y - 1] if y > y_min else 0
                inc = m.pv_capacity[b, y] - prev
                cost_y += crf * tech.pv_capex_per_kw * inc
                cost_y += tech.pv_opex_per_kw_yr * m.pv_capacity[b, y]

            for b in m.DG_BUSES:
                prev = m.dg_capacity[b, y - 1] if y > y_min else 0
                inc = m.dg_capacity[b, y] - prev
                cost_y += crf * tech.dg_capex_per_kw * inc
                cost_y += tech.dg_opex_per_kwh * m.dg_capacity[b, y] * 8760 * 0.3

            # ✅ هزینه سرمایه سرمایش (ظرفیت نصب‌شده)
            for b in m.BUSES:
                for j in m.C_TECHS:
                    prev = m.cc_cap[b, y - 1, j] if y > y_min else 0
                    inc = m.cc_cap[b, y, j] - prev
                    cost_y += crf * m.COOL_CAPEX[j] * inc

            # ✅ هزینه سرمایه گرمایش (ظرفیت نصب‌شده)
            for b in m.BUSES:
                for k in m.H_TECHS:
                    prev = m.hp_cap[b, y - 1, k] if y > y_min else 0
                    inc = m.hp_cap[b, y, k] - prev
                    cost_y += crf * m.HEAT_CAPEX[k] * inc

            # ============================================================
            # هزینه‌های بهره‌برداری
            # ============================================================
            for yp in m.YEAR_PERIODS:
                yy, pp = yp
                if yy != y:
                    continue

                w = m.period_weight[yp]
                hrs = m.period_hours[yp]

                for t in m.TIME_INDEX:
                    if t >= hrs:
                        continue

                    for b in m.BUSES:
                        cost_y += (
                            1
                            * m.p_import[b, y, yp, t]
                            * hrs
                            * tech.elec_purchase_price_per_mwh
                        )

                        gas_dg = m.p_dg[b, y, yp, t] * 1000.0 / (
                            tech.dg_efficiency * tech.gas_hhv_kwh_per_m3
                        )
                        cost_y += 1 * gas_dg * hrs * tech.gas_price_per_m3

            # ============================================================
            # اعتبار سوخت اجتناب‌شده
            # ============================================================
            credit_per_m3 = tech.avoided_fuel_credit_per_m3_gas
            for yp in m.YEAR_PERIODS:
                yy, pp = yp
                if yy != y:
                    continue

                w = m.period_weight[yp]
                annual_hours = w * 8760.0  # ✅ ساعات واقعی این دوره در سال
                hrs = m.period_hours[yp]
                for t in m.TIME_INDEX:
                    if t >= m.period_hours[yp]:
                        continue

                    for b in m.BUSES:
                        heat_supplied = sum(
                            m.hp_use[b, y, yp, t, k] for k in m.H_TECHS
                        )
                        gas_saved = heat_supplied * 1000.0 / 0.9 / tech.gas_hhv_kwh_per_m3
                        cost_y -= hrs * gas_saved * credit_per_m3
            expr += disc * cost_y

        return expr

    m.obj = pyo.Objective(rule=obj_rule, sense=pyo.minimize)