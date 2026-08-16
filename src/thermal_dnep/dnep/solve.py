import pyomo.environ as pyo

from thermal_dnep.network.ieee33 import (
    create_ieee33_network,
)

from .network_model import (
    get_line_data,
    get_bus_data,
)

from .load_model import (
    load_hourly_demand,
    compute_electrical_load,
    aggregate_to_representative_periods,
)

from .technology_model import TechnologyParams
from .objective import build_objective
from .constraints import build_constraints


def _safe_mean(series):
    """میانگین با مدیریت NaN — اگر داده نبود، صفر برمی‌گرداند."""
    s = series.dropna()
    return float(s.mean()) if not s.empty else 0.0


def build_and_solve(
    parquet_path: str,
    electrification_level: float = 0.30,
    base_eer: float = 2.8,
    solver_name: str = "appsi_highs",
    tee: bool = False,
):
    """
    ساخت و حل کامل مدل DNEP چندساله با ساختار ظرفیت/استفاده.
    """
    # ================================================================
    # 1. داده‌ها
    # ================================================================
    net = create_ieee33_network()
    lines = get_line_data(net)
    buses = get_bus_data(net)
    tech = TechnologyParams()

    demand_raw = load_hourly_demand(parquet_path)
    demand = compute_electrical_load(
        demand_raw,
        electrification_level=electrification_level,
    )

    periods = aggregate_to_representative_periods(demand, n_periods_per_year=4)

    all_years = sorted(int(y) for y in set(y for y, _ in periods.keys()))
    # هر دوره نماینده فقط یک timestep دارد
    max_period_len = 1
    print(f"  سال‌های داده : {all_years}")
    print(f"  تعداد دوره‌های نماینده : {len(periods)}")
    print(f"  حداکثر طول دوره : {max_period_len} ساعت")

    # ================================================================
    # 2. مدل Pyomo
    # ================================================================
    m = pyo.ConcreteModel(name="DNEP_CapacityUse")

    # --- مجموعه‌ها ---
    m.BUSES = pyo.Set(initialize=list(buses.keys()))
    m.LINES = pyo.Set(initialize=list(lines.keys()))
    m.YEARS = pyo.Set(initialize=all_years, ordered=True)
    m.SUB_BUSES = pyo.Set(initialize=[0])
    m.PV_BUSES = pyo.Set(initialize=list(buses.keys()))
    m.DG_BUSES = pyo.Set(initialize=list(buses.keys()))
    m.REF_BUS = 0
    m.SBASE = 100.0

    H_TECHS = list(range(tech.n_heating_techs))
    C_TECHS = list(range(tech.n_cooling_techs))
    m.H_TECHS = pyo.Set(initialize=H_TECHS)
    m.C_TECHS = pyo.Set(initialize=C_TECHS)

    valid_yp = [(int(y), int(p)) for y, p in periods.keys()]
    m.YEAR_PERIODS = pyo.Set(initialize=valid_yp, dimen=2)

    # m.TIME_INDEX = pyo.Set(initialize=list(range(max_period_len)))
    m.TIME_INDEX = {0}

    # --- نگاشت‌های کمکی ---
    period_hours_map = {(int(y), int(p)): len(periods[(y, p)]["hours"]) for y, p in periods}
    period_weight_map = {(int(y), int(p)): periods[(y, p)]["weight"] for y, p in periods}

    m.period_weight = pyo.Param(m.YEAR_PERIODS, initialize=period_weight_map)
    m.period_hours = pyo.Param(m.YEAR_PERIODS, initialize=period_hours_map)

    # --- Adjacency جهت‌دار بر اساس BFS از ریشه ---
    from collections import deque

    adj_undirected = {b: [] for b in buses}
    for l, ld in lines.items():
        adj_undirected[ld["from_bus"]].append((l, ld["to_bus"]))
        adj_undirected[ld["to_bus"]].append((l, ld["from_bus"]))

    # BFS از ریشه برای تعیین جهت
    visited = {m.REF_BUS}
    queue = deque([m.REF_BUS])
    parent_of = {}  # child -> (line_idx, parent)

    while queue:
        b = queue.popleft()
        for l, nb in adj_undirected[b]:
            if nb not in visited:
                visited.add(nb)
                parent_of[nb] = (l, b)
                queue.append(nb)

    # ساخت لیست‌های جهت‌دار
    out_lines = {b: [] for b in buses}
    in_lines = {b: [] for b in buses}

    for child, (l, parent) in parent_of.items():
        out_lines[parent].append(l)
        in_lines[child].append(l)

    m.OUT_LINES = pyo.Param(m.BUSES, initialize=out_lines, domain=pyo.Any)
    m.IN_LINES = pyo.Param(m.BUSES, initialize=in_lines, domain=pyo.Any)

    # --- پارامترهای خطوط ---
    m.LINE_FROM = pyo.Param(m.LINES, initialize={l: lines[l]["from_bus"] for l in lines})
    m.LINE_TO = pyo.Param(m.LINES, initialize={l: lines[l]["to_bus"] for l in lines})
    m.LINE_X_PU = pyo.Param(m.LINES, initialize={
        l: lines[l]["x_ohm_per_km"] * lines[l]["length_km"] / (12.66 ** 2 / 100.0)
        for l in lines
    })
    m.LINE_BASE_CAP = pyo.Param(m.LINES, initialize={l: lines[l]["base_capacity_mva"] for l in lines})
    m.LINE_REINFORCE_ADD = pyo.Param(m.LINES, initialize={
        l: lines[l]["base_capacity_mva"] * 0.5 for l in lines
    })
    m.LINE_NEW_CAP = pyo.Param(m.LINES, initialize={l: lines[l]["base_capacity_mva"] for l in lines})
    m.line_length = pyo.Param(m.LINES, initialize={l: lines[l]["length_km"] for l in lines})

    # --- پارامترهای پست ---
    m.SUB_BASE_CAP = pyo.Param(m.SUB_BUSES, initialize={0: 10.0})
    m.SUB_UPGRADE_ADD = pyo.Param(m.SUB_BUSES, initialize={0: 5.0})

    # --- PV capacity factor ---
    season_labels = ["summer", "fall", "winter", "spring"]
    pv_cf_dict = {}
    for yp in valid_yp:
        _, pid = yp
        season = season_labels[pid % len(season_labels)]
        pv_cf_dict[yp] = tech.pv_capacity_factor.get(season, 0.18)
    m.PV_CF = pyo.Param(m.YEAR_PERIODS, initialize=pv_cf_dict)

    # --- پارامترهای فناوری‌ها ---
    m.HEAT_COP = pyo.Param(m.H_TECHS, initialize={
        k: tech.heating_technologies[k].cop for k in H_TECHS
    })
    m.COOL_EER = pyo.Param(m.C_TECHS, initialize={
        j: tech.cooling_technologies[j].eer for j in C_TECHS
    })
    m.HEAT_CAPEX = pyo.Param(m.H_TECHS, initialize={
        k: tech.heating_technologies[k].capex_per_kw for k in H_TECHS
    })
    m.COOL_CAPEX = pyo.Param(m.C_TECHS, initialize={
        j: tech.cooling_technologies[j].capex_per_kw for j in C_TECHS
    })
    m.DUALITY=pyo.Param(m.H_TECHS, initialize={
        k: tech.heating_technologies[k].duality for k in H_TECHS
    })

    # ✅ EER پایه هر باس (سیستم سرمایشی فعلی)
    m.EER_BASE = pyo.Param(
        m.BUSES,
        initialize={b: base_eer for b in buses},
    )

    # ✅ سقف برقی‌سازی حرارت کل سیستم (سناریو)
    m.electrification_cap = pyo.Param(initialize=electrification_level)

    # --- دیکشنری بار برای هر (bus, year, period, time_index) ---
    #
    # هر Representative Period فقط یک timestep دارد:
    #
    #       TIME_INDEX = [0]
    #
    # مقدار بار این timestep از میانگین ساعات عضو همان خوشه
    # در bus_load_profile گرفته می‌شود.
    # ------------------------------------------------------------

    base_load_dict = {}
    cool_load_dict = {}
    heat_load_dict = {}

    for yp, pdata in periods.items():

        year, pid = int(yp[0]), int(yp[1])
        yp_key = (year, pid)

        # هر خوشه فقط یک timestep نماینده دارد
        ti = 0

        bus_profile = pdata.get("bus_load_profile")

        if bus_profile is None:
            continue

        for b in buses:

            if b in bus_profile.index:

                row = bus_profile.loc[b]

                base_load_dict[
                    (b, year, yp_key, ti)
                ] = float(
                    row.get("BaseLoadBus_MW", 0.0)
                )

                cool_load_dict[
                    (b, year, yp_key, ti)
                ] = float(
                    row.get("CoolingLoadBus_MW", 0.0)
                )

                heat_load_dict[
                    (b, year, yp_key, ti)
                ] = float(
                    row.get("HeatingLoadBus_MW", 0.0)
                )

            else:

                base_load_dict[
                    (b, year, yp_key, ti)
                ] = 0.0

                cool_load_dict[
                    (b, year, yp_key, ti)
                ] = 0.0

                heat_load_dict[
                    (b, year, yp_key, ti)
                ] = 0.0


    # ------------------------------------------------------------
    # پارامترهای بار
    # ------------------------------------------------------------

    m.BASE_LOAD = pyo.Param(
        m.BUSES,
        m.YEARS,
        m.YEAR_PERIODS,
        m.TIME_INDEX,
        initialize=base_load_dict,
        default=0.0,
        mutable=False,
    )

    m.COOL_LOAD = pyo.Param(
        m.BUSES,
        m.YEARS,
        m.YEAR_PERIODS,
        m.TIME_INDEX,
        initialize=cool_load_dict,
        default=0.0,
        mutable=False,
    )

    m.HEAT_LOAD = pyo.Param(
        m.BUSES,
        m.YEARS,
        m.YEAR_PERIODS,
        m.TIME_INDEX,
        initialize=heat_load_dict,
        default=0.0,
        mutable=False,
    )
    # بار میانگین سالانه برای هزینه فناوری و سقف سیستمی
    m.base_cooling_load = pyo.Param(m.BUSES, initialize={
        b: _safe_mean(demand[demand["bus"] == b]["CoolingLoadBus_MW"])
        for b in buses
    }, default=0.0)

    m.base_heating_load = pyo.Param(m.BUSES, initialize={
        b: _safe_mean(demand[demand["bus"] == b]["HeatingLoadBus_MW"])
        for b in buses
    }, default=0.0)

    # بار حرارتی کل سیستم برای نرمال‌سازی سقف برقی‌سازی
    m.total_system_heat = pyo.Param(
        initialize=sum(
            _safe_mean(demand[demand["bus"] == b]["HeatingLoadBus_MW"])
            for b in buses
        )
    )

    # ================================================================
    # 3. متغیرها
    # ================================================================

    # تصمیمات سرمایه‌ای شبکه
    m.x_line_new = pyo.Var(m.LINES, m.YEARS, domain=pyo.Binary)
    m.x_line_reinforce = pyo.Var(m.LINES, m.YEARS, domain=pyo.Binary)
        # ✅ متغیر باینری: خط فعال/غیرفعال در هر سال
    # z_line[l,y] = 1 اگر خط l در سال y فعال باشد
    m.z_line = pyo.Var(m.LINES, m.YEARS, domain=pyo.Binary)

    # ✅ متغیر پیوسته: جریان مجازی برای تضمین شعاعی بودن
    # g_flow[l,y] ∈ [0, N-1] جریان کالای مجازی روی خط l در سال y
    n_buses = len(list(buses))
    m.g_flow = pyo.Var(
        m.LINES, m.YEARS,
        domain=pyo.NonNegativeReals,
        bounds=(0, n_buses - 1),
    )
    m.x_sub_upgrade = pyo.Var(m.SUB_BUSES, m.YEARS, domain=pyo.Binary)
    m.pv_capacity = pyo.Var(m.PV_BUSES, m.YEARS, domain=pyo.NonNegativeReals, bounds=(0, 5.0))
    m.dg_capacity = pyo.Var(m.DG_BUSES, m.YEARS, domain=pyo.NonNegativeReals, bounds=(0, 3.0))

    # ✅ ظرفیت نصب‌شده سرمایش [MW سرمایشی]
    m.cc_cap = pyo.Var(
        m.BUSES, m.YEARS, m.C_TECHS,
        domain=pyo.NonNegativeReals,
    )

    # ✅ استفاده ساعتی سرمایش [MW سرمایشی]
    m.cc_use = pyo.Var(
        m.BUSES, m.YEARS, m.YEAR_PERIODS, m.TIME_INDEX, m.C_TECHS,
        domain=pyo.NonNegativeReals,
    )

    # ✅ ظرفیت نصب‌شده هیت پمپ [MW حرارتی]
    m.hp_cap = pyo.Var(
        m.BUSES, m.YEARS, m.H_TECHS,
        domain=pyo.NonNegativeReals,
    )

    # ✅ استفاده ساعتی هیت پمپ [MW حرارتی]
    m.hp_use = pyo.Var(
        m.BUSES, m.YEARS, m.YEAR_PERIODS, m.TIME_INDEX, m.H_TECHS,
        domain=pyo.NonNegativeReals,
    )
    # ✅ استفاده ساعتی هیت پمپ [MW سرمایشی]
    m.hp_use2 = pyo.Var(
        m.BUSES, m.YEARS, m.YEAR_PERIODS, m.TIME_INDEX, m.H_TECHS,
        domain=pyo.NonNegativeReals,
    )
    # متغیرهای بهره‌برداری شبکه
    m.p_import = pyo.Var(
        m.BUSES, m.YEARS, m.YEAR_PERIODS, m.TIME_INDEX,
        domain=pyo.NonNegativeReals,
    )
    m.p_dg = pyo.Var(
        m.DG_BUSES, m.YEARS, m.YEAR_PERIODS, m.TIME_INDEX,
        domain=pyo.NonNegativeReals,
    )
    m.p_pv = pyo.Var(
        m.PV_BUSES, m.YEARS, m.YEAR_PERIODS, m.TIME_INDEX,
        domain=pyo.NonNegativeReals,
    )
    m.theta = pyo.Var(
        m.BUSES, m.YEARS, m.YEAR_PERIODS, m.TIME_INDEX,
        domain=pyo.Reals,
    )
    m.f_line = pyo.Var(
        m.LINES, m.YEARS, m.YEAR_PERIODS, m.TIME_INDEX,
        domain=pyo.Reals,
    )
    m.total_load = pyo.Var(
        m.BUSES, m.YEARS, m.YEAR_PERIODS, m.TIME_INDEX,
        domain=pyo.NonNegativeReals,
    )

    # ================================================================
    # 4. هدف و قیود
    # ================================================================
    print()
    print("=" * 70)
    print("MODEL BUILDING")
    print("=" * 70)

    print(f"  Buses                 : {len(buses):,}")
    print(f"  Lines                 : {len(lines):,}")
    print(f"  Years                 : {len(all_years):,}")
    print(f"  Representative periods: {len(periods):,}")
    print(f"  Max period length     : {max_period_len:,}")
    print()

    build_objective(m, tech, periods)
    build_constraints(m, tech, periods)

    # ================================================================
    # 5. گزارش اندازه مدل و حل
    # ================================================================

    def _count_component(component):
        """تعداد واقعی آیتم‌های یک Component در مدل."""
        return sum(1 for _ in component.values())


    def _print_model_summary(model, periods, buses, lines):
        """نمایش خلاصه اندازه مدل قبل از شروع Solver."""

        # ------------------------------------------------------------
        # تعداد متغیرها
        # ------------------------------------------------------------
        variable_counts = {}

        for var in model.component_objects(
            pyo.Var,
            active=True,
        ):
            variable_counts[var.name] = _count_component(var)

        total_variables = sum(variable_counts.values())

        # ------------------------------------------------------------
        # تعداد قیود
        # ------------------------------------------------------------
        constraint_counts = {}

        for con in model.component_objects(
            pyo.Constraint,
            active=True,
        ):
            constraint_counts[con.name] = _count_component(con)

        total_constraints = sum(constraint_counts.values())

        # ------------------------------------------------------------
        # اطلاعات کلی مدل
        # ------------------------------------------------------------
        years = list(model.YEARS)
        year_periods = list(model.YEAR_PERIODS)

        print()
        print("=" * 72)
        print("                    DNEP MODEL SUMMARY")
        print("=" * 72)

        print()
        print("Model dimensions")
        print("-" * 72)
        print(f"  Buses                         : {len(buses):,}")
        print(f"  Lines                         : {len(lines):,}")
        print(f"  Years                         : {len(years):,}")
        print(f"  Representative periods       : {len(year_periods):,}")
        print(f"  Time indices                 : {len(model.TIME_INDEX):,}")

        print()
        print("Representative periods by year")
        print("-" * 72)

        for year in sorted(years):
            year_periods_count = sum(
                1 for y, _ in year_periods
                if y == year
            )

            total_hours = sum(
                len(periods[(y, p)]["hours"])
                for y, p in year_periods
                if y == year
            )

            print(
                f"  {year}: "
                f"{year_periods_count} periods, "
                f"{total_hours:,} representative hours"
            )

        # ------------------------------------------------------------
        # متغیرها
        # ------------------------------------------------------------
        print()
        print("Variables")
        print("-" * 72)

        for name, count in variable_counts.items():
            print(f"  {name:<35}: {count:>12,}")

        print("-" * 72)
        print(f"  {'TOTAL VARIABLES':<35}: {total_variables:>12,}")

        # ------------------------------------------------------------
        # قیود
        # ------------------------------------------------------------
        print()
        print("Constraints")
        print("-" * 72)

        for name, count in constraint_counts.items():
            print(f"  {name:<35}: {count:>12,}")

        print("-" * 72)
        print(f"  {'TOTAL CONSTRAINTS':<35}: {total_constraints:>12,}")

        # ------------------------------------------------------------
        # وضعیت مدل
        # ------------------------------------------------------------
        print()
        print("Model status")
        print("-" * 72)
        print(f"  Variables                    : {total_variables:,}")
        print(f"  Constraints                  : {total_constraints:,}")
        print(
            f"  Constraints / Variables      : "
            f"{total_constraints / total_variables:.2f}"
            if total_variables
            else "  Constraints / Variables      : N/A"
        )

        print()
        print("=" * 72)
        print("                    STARTING SOLVER")
        print("=" * 72)
        print()


    _print_model_summary(
        model=m,
        periods=periods,
        buses=buses,
        lines=lines,
    )

    opt = pyo.SolverFactory(solver_name)
    results = opt.solve(m, tee=tee)


    print(f"  وضعیت حل: {results.solver.termination_condition}")
    print(f"  هزینه بهینه (NPV): {pyo.value(m.obj):,.0f}")

    return m, results