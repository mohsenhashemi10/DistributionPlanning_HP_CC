import pyomo.environ as pyo


def build_constraints(m, tech, periods):
    """ساخت تمام قیود مدل DNEP با ساختار ظرفیت/استفاده."""

    # --------------------------------------------------
    # 1. تعادل توان
    # --------------------------------------------------
    def power_balance_rule(m, b, y, yp_y, yp_p, t):
        yp = (yp_y, yp_p)
        if yp[0] != y:
            return pyo.Constraint.Skip
        if t >= m.period_hours[yp]:
            return pyo.Constraint.Skip

        gen = m.p_import[b, y, yp, t] + m.p_dg[b, y, yp, t] + m.p_pv[b, y, yp, t]
        load = m.total_load[b, y, yp, t]
        flow_out = sum(m.f_line[l, y, yp, t] for l in m.OUT_LINES[b])
        flow_in = sum(m.f_line[l, y, yp, t] for l in m.IN_LINES[b])
        return gen - load == flow_out - flow_in

    m.power_balance = pyo.Constraint(
        m.BUSES, m.YEARS, m.YEAR_PERIODS, m.TIME_INDEX,
        rule=power_balance_rule,
    )

    # --------------------------------------------------
    # 2. پخش بار DC
    # --------------------------------------------------
    def dc_flow_rule(m, l, y, yp_y, yp_p, t):
        yp = (yp_y, yp_p)
        if yp[0] != y:
            return pyo.Constraint.Skip
        if t >= m.period_hours[yp]:
            return pyo.Constraint.Skip

        fb = m.LINE_FROM[l]
        tb = m.LINE_TO[l]
        x_pu = m.LINE_X_PU[l]
        return m.f_line[l, y, yp, t] == (
            m.theta[fb, y, yp, t] - m.theta[tb, y, yp, t]
        ) / x_pu * m.SBASE

    m.dc_flow = pyo.Constraint(
        m.LINES, m.YEARS, m.YEAR_PERIODS, m.TIME_INDEX,
        rule=dc_flow_rule,
    )

    # --------------------------------------------------
    # 3. باس مرجع
    # --------------------------------------------------
    def ref_bus_rule(m, y, yp_y, yp_p, t):
        yp = (yp_y, yp_p)
        if yp[0] != y:
            return pyo.Constraint.Skip
        if t >= m.period_hours[yp]:
            return pyo.Constraint.Skip
        return m.theta[m.REF_BUS, y, yp, t] == 0.0

    m.ref_bus = pyo.Constraint(
        m.YEARS, m.YEAR_PERIODS, m.TIME_INDEX,
        rule=ref_bus_rule,
    )

    # --------------------------------------------------
    # 4. ظرفیت خطوط (دو قید جدا)
    # --------------------------------------------------
    def _line_capacity(m, l, y):
        #فرض کردم ظرفیت خطوط 33 باسه نصف این باشد که هست
        return (
            0.1*m.LINE_BASE_CAP[l]
            + m.x_line_reinforce[l, y] * m.LINE_REINFORCE_ADD[l]
            + m.x_line_new[l, y] * m.LINE_NEW_CAP[l]
        )

    def line_cap_upper_rule(m, l, y, yp_y, yp_p, t):
        yp = (yp_y, yp_p)
        if yp[0] != y:
            return pyo.Constraint.Skip
        if t >= m.period_hours[yp]:
            return pyo.Constraint.Skip
        cap = _line_capacity(m, l, y)
        return m.f_line[l, y, yp, t] <= cap

    def line_cap_lower_rule(m, l, y, yp_y, yp_p, t):
        yp = (yp_y, yp_p)
        if yp[0] != y:
            return pyo.Constraint.Skip
        if t >= m.period_hours[yp]:
            return pyo.Constraint.Skip
        cap = _line_capacity(m, l, y)
        return m.f_line[l, y, yp, t] >= -cap

    m.line_cap_upper = pyo.Constraint(
        m.LINES, m.YEARS, m.YEAR_PERIODS, m.TIME_INDEX,
        rule=line_cap_upper_rule,
    )
    m.line_cap_lower = pyo.Constraint(
        m.LINES, m.YEARS, m.YEAR_PERIODS, m.TIME_INDEX,
        rule=line_cap_lower_rule,
    )

    # --------------------------------------------------
    # 5. ظرفیت پست
    # --------------------------------------------------
    def sub_capacity_rule(m, b, y, yp_y, yp_p, t):
        yp = (yp_y, yp_p)
        if yp[0] != y:
            return pyo.Constraint.Skip
        if t >= m.period_hours[yp]:
            return pyo.Constraint.Skip

        cap = 0.1*m.SUB_BASE_CAP[b] + m.x_sub_upgrade[b, y] * m.SUB_UPGRADE_ADD[b]
        return m.p_import[b, y, yp, t] <= cap

    m.sub_cap = pyo.Constraint(
        m.SUB_BUSES, m.YEARS, m.YEAR_PERIODS, m.TIME_INDEX,
        rule=sub_capacity_rule,
    )

    def no_import_rule(m, b, y, yp_y, yp_p, t):
        yp = (yp_y, yp_p)
        if b in list(m.SUB_BUSES):
            return pyo.Constraint.Skip
        if yp[0] != y:
            return pyo.Constraint.Skip
        if t >= m.period_hours[yp]:
            return pyo.Constraint.Skip
        return m.p_import[b, y, yp, t] == 0

    m.no_import = pyo.Constraint(
        m.BUSES, m.YEARS, m.YEAR_PERIODS, m.TIME_INDEX,
        rule=no_import_rule,
    )

    # --------------------------------------------------
    # 6. PV
    # --------------------------------------------------
    def pv_gen_rule(m, b, y, yp_y, yp_p, t):
        yp = (yp_y, yp_p)
        if yp[0] != y:
            return pyo.Constraint.Skip
        if t >= m.period_hours[yp]:
            return pyo.Constraint.Skip
        cf = m.PV_CF[yp]
        return m.p_pv[b, y, yp, t] == m.pv_capacity[b, y] * cf

    m.pv_gen = pyo.Constraint(
        m.PV_BUSES, m.YEARS, m.YEAR_PERIODS, m.TIME_INDEX,
        rule=pv_gen_rule,
    )

    # --------------------------------------------------
    # 7. DG
    # --------------------------------------------------
    def dg_cap_rule(m, b, y, yp_y, yp_p, t):
        yp = (yp_y, yp_p)
        if yp[0] != y:
            return pyo.Constraint.Skip
        if t >= m.period_hours[yp]:
            return pyo.Constraint.Skip
        return m.p_dg[b, y, yp, t] <= m.dg_capacity[b, y]

    m.dg_cap_con = pyo.Constraint(
        m.DG_BUSES, m.YEARS, m.YEAR_PERIODS, m.TIME_INDEX,
        rule=dg_cap_rule,
    )

    # --------------------------------------------------
    # 8. قیود سرمایش (ظرفیت/استفاده)
    # --------------------------------------------------
    # 8a. استفاده ساعتی ≤ ظرفیت نصب‌شده
    def cc_use_capacity_rule(m, b, y, yp_y, yp_p, t, j):
        yp = (yp_y, yp_p)
        if yp[0] != y:
            return pyo.Constraint.Skip
        if t >= m.period_hours[yp]:
            return pyo.Constraint.Skip
        return m.cc_use[b, y, yp, t, j] <= m.cc_cap[b, y, j]

    m.cc_use_capacity = pyo.Constraint(
        m.BUSES, m.YEARS, m.YEAR_PERIODS, m.TIME_INDEX, m.C_TECHS,
        rule=cc_use_capacity_rule,
    )

    # 8b. جمع استفاده ≤ بار سرمایشی موجود در آن ساعت
    def cc_demand_limit_rule(m, b, y, yp_y, yp_p, t):
        yp = (yp_y, yp_p)
        if yp[0] != y:
            return pyo.Constraint.Skip
        if t >= m.period_hours[yp]:
            return pyo.Constraint.Skip
        return (
            sum(m.cc_use[b, y, yp, t, j] for j in m.C_TECHS)
            <= m.COOL_LOAD[b, y, yp, t]
        )

    m.cc_demand_limit = pyo.Constraint(
        m.BUSES, m.YEARS, m.YEAR_PERIODS, m.TIME_INDEX,
        rule=cc_demand_limit_rule,
    )

    # --------------------------------------------------
    # 9. قیود گرمایش (ظرفیت/استفاده)
    # --------------------------------------------------
    # 9a. استفاده ساعتی ≤ ظرفیت نصب‌شده
    def hp_use_capacity_rule(m, b, y, yp_y, yp_p, t, k):
        yp = (yp_y, yp_p)
        if yp[0] != y:
            return pyo.Constraint.Skip
        if t >= m.period_hours[yp]:
            return pyo.Constraint.Skip
        return m.hp_use[b, y, yp, t, k] <= m.hp_cap[b, y, k]

    m.hp_use_capacity = pyo.Constraint(
        m.BUSES, m.YEARS, m.YEAR_PERIODS, m.TIME_INDEX, m.H_TECHS,
        rule=hp_use_capacity_rule,
    )

    # 9b. جمع استفاده ≤ بار حرارتی موجود در آن ساعت
    def hp_demand_limit_rule(m, b, y, yp_y, yp_p, t):
        yp = (yp_y, yp_p)
        if yp[0] != y:
            return pyo.Constraint.Skip
        if t >= m.period_hours[yp]:
            return pyo.Constraint.Skip
        return (
            sum(m.hp_use[b, y, yp, t, k] for k in m.H_TECHS)
            <= m.HEAT_LOAD[b, y, yp, t]
        )

    m.hp_demand_limit = pyo.Constraint(
        m.BUSES, m.YEARS, m.YEAR_PERIODS, m.TIME_INDEX,
        rule=hp_demand_limit_rule,
    )

    # 9c. سقف برقی‌سازی حرارت روی کل سیستم
    def system_hp_limit_rule(m, y):
        if pyo.value(m.total_system_heat) < 1e-9:
            return pyo.Constraint.Skip
        return (
            sum(m.hp_cap[b, y, k] for b in m.BUSES for k in m.H_TECHS)
            <= m.electrification_cap * m.total_system_heat
        )

    m.system_hp_limit = pyo.Constraint(m.YEARS, rule=system_hp_limit_rule)

    # --------------------------------------------------
    # 10. تعریف بار کل (با cc_use و hp_use)
    # --------------------------------------------------
    def total_load_def(m, b, y, yp_y, yp_p, t):
        yp = (yp_y, yp_p)
        if yp[0] != y:
            return pyo.Constraint.Skip
        if t >= m.period_hours[yp]:
            return pyo.Constraint.Skip

        base = m.BASE_LOAD[b, y, yp, t]

        # سرمایش: بخش قدیمی + بخش جدید
        new_cool = sum(m.cc_use[b, y, yp, t, j] for j in m.C_TECHS)
        old_cool = m.COOL_LOAD[b, y, yp, t] - new_cool

        cool = old_cool / m.EER_BASE[b] + sum(
            m.cc_use[b, y, yp, t, j] / m.COOL_EER[j]
            for j in m.C_TECHS
        )

        # گرمایش برقی
        heat_elec = sum(
            m.hp_use[b, y, yp, t, k] / m.HEAT_COP[k]
            for k in m.H_TECHS
        )

        return m.total_load[b, y, yp, t] == base + cool + heat_elec

    m.total_load_def = pyo.Constraint(
        m.BUSES, m.YEARS, m.YEAR_PERIODS, m.TIME_INDEX,
        rule=total_load_def,
    )


    # --------------------------------------------------
    # 12. قیود شعاعی بودن و اتصال به ریشه
    #     فرمولاسیون Single Commodity Flow
    # --------------------------------------------------
    n_buses = len(list(m.BUSES))

    # 12a. ارتباط z_line با تصمیمات توسعه شبکه
    #      خط فعال است اگر: خط اولیه موجود باشد OR تقویت شده باشد OR جدید ساخته شده باشد
    #      برای IEEE 33 همه خطوط اولیه موجود هستند، پس z_line >= 1 همیشه
    #      اما اگر خط جدیدی ساخته شود، z_line آن هم 1 می‌شود
    #      نکته: در IEEE 33 ثابت، همه خطوط همیشه فعال هستند
    #      این قید برای شبکه‌هایی با امکان حذف خط کاربرد دارد
    def z_line_active_rule(m, l, y):
        """خطوط موجود همیشه فعال؛ خطوط جدید فقط اگر ساخته شوند."""
        # خطوط موجود (همه خطوط IEEE 33) همیشه فعال
        # اگر در آینده امکان حذف خط اضافه شد، این قید تغییر می‌کند
        return m.z_line[l, y] == 1

    m.z_line_active = pyo.Constraint(m.LINES, m.YEARS, rule=z_line_active_rule)

    # 12b. بالانس جریان مجازی در هر باس غیرریشه
    #      Σ g_flow(ورودی) - Σ g_flow(خروجی) = 1 (هر باس ۱ واحد مصرف می‌کند)
    def scf_balance_non_root_rule(m, b, y):
        if b == m.REF_BUS:
            return pyo.Constraint.Skip
        inflow = sum(m.g_flow[l, y] for l in m.IN_LINES[b])
        outflow = sum(m.g_flow[l, y] for l in m.OUT_LINES[b])
        return inflow - outflow == 1

    m.scf_balance_non_root = pyo.Constraint(
        m.BUSES, m.YEARS, rule=scf_balance_non_root_rule,
    )

    # 12c. بالانس جریان مجازی در باس ریشه
    #      Σ g_flow(خروجی) - Σ g_flow(ورودی) = N-1 (ریشه N-1 واحد تولید می‌کند)
    def scf_balance_root_rule(m, y):
        outflow = sum(m.g_flow[l, y] for l in m.OUT_LINES[m.REF_BUS])
        inflow = sum(m.g_flow[l, y] for l in m.IN_LINES[m.REF_BUS])
        return outflow - inflow == n_buses - 1

    m.scf_balance_root = pyo.Constraint(m.YEARS, rule=scf_balance_root_rule)

    # 12d. ظرفیت جریان مجازی روی هر خط
    #      g_flow[l,y] <= (N-1) * z_line[l,y]
    #      اگر خط غیرفعال باشد، جریان مجازی صفر است
    def scf_capacity_rule(m, l, y):
        return m.g_flow[l, y] <= (n_buses - 1) * m.z_line[l, y]

    m.scf_capacity = pyo.Constraint(m.LINES, m.YEARS, rule=scf_capacity_rule)

    # 12e. هر باس غیرریشه دقیقاً یک والد دارد (شعاعی بودن)
    #      Σ z_line[l,y] for l in IN_LINES[b] == 1
    def single_parent_rule(m, b, y):
        if b == m.REF_BUS:
            return pyo.Constraint.Skip
        return sum(m.z_line[l, y] for l in m.IN_LINES[b]) == 1

    m.single_parent = pyo.Constraint(m.BUSES, m.YEARS, rule=single_parent_rule)


    # --------------------------------------------------
    # 11. یکنوایی تصمیمات سرمایه‌ای
    # --------------------------------------------------

    def mono_2d_rule(var):
        def rule(m, idx, y):
            years = list(m.YEARS)
            if y == years[0]:
                return pyo.Constraint.Skip
            prev_y = years[years.index(y) - 1]
            return var[idx, y] >= var[idx, prev_y]
        return rule

    m.mono_line_new = pyo.Constraint(m.LINES, m.YEARS, rule=mono_2d_rule(m.x_line_new))
    m.mono_line_reinf = pyo.Constraint(m.LINES, m.YEARS, rule=mono_2d_rule(m.x_line_reinforce))
    m.mono_sub = pyo.Constraint(m.SUB_BUSES, m.YEARS, rule=mono_2d_rule(m.x_sub_upgrade))

    # ✅ ترتیب مطابق تعریف cc_cap: (BUSES, YEARS, C_TECHS)
    # year آخرین نیست → باید rule را تطبیق دهیم

    def mono_3d_cc_rule(m, b, y, j):
        years = list(m.YEARS)
        if y == years[0]:
            return pyo.Constraint.Skip
        prev_y = years[years.index(y) - 1]
        return m.cc_cap[b, y, j] >= m.cc_cap[b, prev_y, j]

    m.mono_cc = pyo.Constraint(
        m.BUSES, m.YEARS, m.C_TECHS,
        rule=mono_3d_cc_rule,
    )

    def mono_3d_hp_rule(m, b, y, k):
        years = list(m.YEARS)
        if y == years[0]:
            return pyo.Constraint.Skip
        prev_y = years[years.index(y) - 1]
        return m.hp_cap[b, y, k] >= m.hp_cap[b, prev_y, k]

    m.mono_hp = pyo.Constraint(
        m.BUSES, m.YEARS, m.H_TECHS,
        rule=mono_3d_hp_rule,
    )

    m.mono_zline = pyo.Constraint(m.LINES, m.YEARS, rule=mono_2d_rule(m.z_line))
