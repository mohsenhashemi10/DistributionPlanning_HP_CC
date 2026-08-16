from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class HeatingTechnology:
    name: str
    cop: float
    capex_per_kw: float      # $/kW حرارتی
    max_share: float = 1.0   # حداکثر سهم قابل نصب


@dataclass
class CoolingTechnology:
    name: str
    eer: float               # COP سرمایشی
    capex_per_kw: float      # $/kW سرمایشی
    max_share: float = 1.0


@dataclass
class TechnologyParams:
    # --- گزینه‌های فناوری گرمایشی ---
    heating_technologies: List[HeatingTechnology] = field(default_factory=lambda: [
        HeatingTechnology("electric_resistance", cop=0.95, capex_per_kw=100),
        HeatingTechnology("ashp",              cop=3.0,  capex_per_kw=400),
        HeatingTechnology("gshp",              cop=4.5,  capex_per_kw=800),
    ])

    # --- گزینه‌های فناوری سرمایشی ---
    cooling_technologies: List[CoolingTechnology] = field(default_factory=lambda: [
        CoolingTechnology("ac_standard",       eer=2.8, capex_per_kw=200),
        CoolingTechnology("ac_inverter",       eer=4.0, capex_per_kw=350),
        CoolingTechnology("chiller_high_eff",  eer=5.5, capex_per_kw=600),
    ])

    # --- شبکه ---
    # line_build_cost_per_km: float = 50_000.0
    line_build_cost_per_km: float = 50_0.0
    # line_reinforce_cost_per_km: float = 25_000.0
    # substation_upgrade_cost: float = 200_000.0
    line_reinforce_cost_per_km: float = 25_0.0
    substation_upgrade_cost: float = 200_0.0
    # --- PV ---
    pv_capex_per_kw: float = 800.0
    pv_opex_per_kw_yr: float = 15.0
    pv_lifetime_yr: int = 25
    pv_capacity_factor: Dict[str, float] = field(
        default_factory=lambda: {"summer": 0.22, "winter": 0.12, "spring": 0.18, "fall": 0.16}
    )

    # --- DG ---
    dg_capex_per_kw: float = 1200.0
    dg_opex_per_kwh: float = 0.04
    dg_efficiency: float = 0.35
    dg_gas_hhv_kwh_per_m3: float = 10.0

    # --- اعتبار سوخت ---
    gas_price_per_m3: float = 0.10
    gasoil_price_per_liter: float = 0.60
    gasoil_hhv_kwh_per_liter: float = 10.0
    gas_hhv_kwh_per_m3: float = 10.0

    # --- عمومی ---
    discount_rate: float = 0.08
    planning_horizon_yr: int = 10
    # elec_purchase_price_per_mwh: float = 50.0
    elec_purchase_price_per_mwh: float = 0

    max_electrification: float = 1.0

    @property
    def avoided_fuel_credit_per_m3_gas(self) -> float:
        gas_energy = self.gas_hhv_kwh_per_m3
        gasoil_equiv_liters = gas_energy / self.gasoil_hhv_kwh_per_liter
        return gasoil_equiv_liters * self.gasoil_price_per_liter

    @property
    def crf(self) -> float:
        r = self.discount_rate
        n = self.planning_horizon_yr
        return r * (1 + r) ** n / ((1 + r) ** n - 1)

    @property
    def n_heating_techs(self) -> int:
        return len(self.heating_technologies)

    @property
    def n_cooling_techs(self) -> int:
        return len(self.cooling_technologies)