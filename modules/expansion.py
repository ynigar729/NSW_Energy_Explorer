# -*- coding: utf-8 -*-
"""
Created on Mon Jun 15 00:22:45 2026

@author: yasmi
"""

import pypsa
import pandas as pd
import numpy as np


def create_expansion_network():
    """
    Future NSW Capacity Expansion Model.

    Scenario:
    - Eraring coal RETIRED (2,880 MW gone)
    - Bayswater coal RETIRED (2,640 MW gone)
    - Demand grown 20% from EVs and electrification
    - NO slack generator — forces real investment
    - Capital costs correctly annualised over 8,760 hours
    """

    # ── TIME INDEX ────────────────────────────────────────────────
    hours = pd.date_range("2024-01-17", periods=24, freq="h")

    # ── FUTURE DEMAND — 20% growth ────────────────────────────────
    future_demand = pd.Series([
        8640, 8280, 8040, 7920, 8040, 8640,
        9360, 10080, 10800, 11040, 11160, 11040,
        10920, 10800, 11040, 11280, 11520, 11760,
        12120, 11760, 11280, 10800, 10200, 9480
    ], index=hours)

    # ── RENEWABLE PROFILES ────────────────────────────────────────
    solar_profile = pd.Series([
        0, 0, 0, 0, 0, 0.02,
        0.15, 0.40, 0.65, 0.82, 0.92, 0.97,
        0.98, 0.95, 0.88, 0.75, 0.55, 0.20,
        0.02, 0, 0, 0, 0, 0
    ], index=hours)

    wind_profile = pd.Series([
        0.45, 0.42, 0.40, 0.38, 0.40, 0.45,
        0.50, 0.48, 0.42, 0.40, 0.38, 0.35,
        0.33, 0.35, 0.40, 0.48, 0.55, 0.60,
        0.62, 0.58, 0.55, 0.52, 0.50, 0.47
    ], index=hours)

    # ── CAPITAL COSTS ─────────────────────────────────────────────
    # CRITICAL: divide annual cost by 8,760 hours
    # NOT by 24 — that made costs 365x too high
    # Source: AEMO ISP 2024 Input & Assumptions Workbook
    HOURS_PER_YEAR        = 8760
    SOLAR_CAPEX_HR        = 96_000  / HOURS_PER_YEAR  # $10.96/MW/hr
    WIND_CAPEX_HR         = 170_000 / HOURS_PER_YEAR  # $19.41/MW/hr
    BATTERY_CAPEX_HR      = 660_000 / HOURS_PER_YEAR  # $75.34/MW/hr
    GAS_CAPEX_HR          = 80_000  / HOURS_PER_YEAR  # $9.13/MW/hr
    TRANSMISSION_CAPEX_HR = 150_000 / HOURS_PER_YEAR  # $17.12/MW/hr

    # ── CREATE NETWORK ────────────────────────────────────────────
    n = pypsa.Network()
    n.set_snapshots(hours)

    # ── BUSES ─────────────────────────────────────────────────────
    n.add("Bus", "Sydney",    carrier="AC")
    n.add("Bus", "Newcastle", carrier="AC")
    n.add("Bus", "Orana",     carrier="AC")
    n.add("Bus", "Snowy",     carrier="AC")
    n.add("Bus", "Eraring",   carrier="AC")

    # ── FIXED LINES ───────────────────────────────────────────────
    n.add("Line", "Sydney-Newcastle",
          bus0="Sydney", bus1="Newcastle",
          x=0.1, r=0.01, s_nom=3000,
          carrier="AC")

    n.add("Line", "Newcastle-Eraring",
          bus0="Newcastle", bus1="Eraring",
          x=0.08, r=0.01, s_nom=2500,
          carrier="AC")

    n.add("Line", "Sydney-Snowy",
          bus0="Sydney", bus1="Snowy",
          x=0.15, r=0.02, s_nom=2000,
          carrier="AC")

    # Sydney-Orana — EXPANDABLE
    n.add("Line", "Sydney-Orana",
          bus0="Sydney", bus1="Orana",
          x=0.12, r=0.015,
          s_nom=2500,
          s_nom_extendable=True,
          s_nom_max=8000,
          capital_cost=TRANSMISSION_CAPEX_HR,
          carrier="AC")

    # ── LOAD ──────────────────────────────────────────────────────
    n.add("Load", "Sydney_Load",
          bus="Sydney",
          p_set=future_demand)

    # ── EXISTING GENERATORS ───────────────────────────────────────
    # ERARING NOT ADDED  — 2,880 MW retired
    # BAYSWATER NOT ADDED — 2,640 MW retired
    # Total coal gap = 5,520 MW

    # Mt Piper — kept
    n.add("Generator", "MtPiper_Coal",
          bus="Orana",
          p_nom=1400,
          marginal_cost=42,
          carrier="coal")

    # Gas — all kept
    n.add("Generator", "Tallawarra_Gas",
          bus="Sydney",
          p_nom=760,
          marginal_cost=85,
          carrier="gas")

    n.add("Generator", "Uranquinty_Gas",
          bus="Sydney",
          p_nom=664,
          marginal_cost=90,
          carrier="gas")

    n.add("Generator", "Colongra_Peaker",
          bus="Sydney",
          p_nom=724,
          marginal_cost=180,
          carrier="gas")

    # Hydro
    n.add("Generator", "Snowy_Hydro",
          bus="Snowy",
          p_nom=2356,
          marginal_cost=12,
          carrier="hydro")

    # Existing Solar
    n.add("Generator", "Orana_Solar",
          bus="Orana",
          p_nom=6600,
          marginal_cost=3,
          carrier="solar")

    # Existing Wind
    n.add("Generator", "Orana_Wind",
          bus="Orana",
          p_nom=2822,
          marginal_cost=5,
          carrier="wind")

    # NO SLACK GENERATOR
    # Without slack optimizer MUST build real capacity
    # to meet demand — this forces non-zero investment

    # ── EXISTING PROFILES ─────────────────────────────────────────
    n.generators_t.p_max_pu = pd.DataFrame({
        "Orana_Solar": solar_profile,
        "Orana_Wind":  wind_profile,
    }, index=hours)

    # ── NEW BUILD CANDIDATES ──────────────────────────────────────
    # capital_cost uses HOURS_PER_YEAR not len(hours)
    # This is critical for correct investment signals

    n.add("Generator", "New_Solar",
          bus="Orana",
          p_nom=0,
          p_nom_extendable=True,
          p_nom_max=15000,
          capital_cost=SOLAR_CAPEX_HR,
          marginal_cost=3,
          carrier="solar",
          p_max_pu=solar_profile)

    n.add("Generator", "New_Wind",
          bus="Orana",
          p_nom=0,
          p_nom_extendable=True,
          p_nom_max=8000,
          capital_cost=WIND_CAPEX_HR,
          marginal_cost=5,
          carrier="wind",
          p_max_pu=wind_profile)

    n.add("Generator", "New_Gas_OCGT",
          bus="Sydney",
          p_nom=0,
          p_nom_extendable=True,
          p_nom_max=5000,
          capital_cost=GAS_CAPEX_HR,
          marginal_cost=180,
          carrier="gas")

    n.add("StorageUnit", "New_Battery",
          bus="Sydney",
          p_nom=0,
          p_nom_extendable=True,
          p_nom_max=8000,
          max_hours=4,
          capital_cost=BATTERY_CAPEX_HR,
          marginal_cost=0,
          marginal_cost_storage=0,
          efficiency_store=np.sqrt(0.92),
          efficiency_dispatch=np.sqrt(0.92),
          state_of_charge_initial=0.5,
          cyclic_state_of_charge=True,
          carrier="battery")

    # ── UPDATE ALL PROFILES ───────────────────────────────────────
    n.generators_t.p_max_pu = pd.DataFrame({
        "Orana_Solar": solar_profile,
        "Orana_Wind":  wind_profile,
        "New_Solar":   solar_profile,
        "New_Wind":    wind_profile,
    }, index=hours)

    return n, hours, future_demand


def run_expansion(n):
    """Run capacity expansion optimisation."""
    n.optimize(solver_name="highs")
    return n


def get_expansion_results(n):
    """Extract results."""

    hours = n.snapshots

    # New build
    new_solar_mw    = n.generators.at["New_Solar",    "p_nom_opt"]
    new_wind_mw     = n.generators.at["New_Wind",     "p_nom_opt"]
    new_gas_mw      = n.generators.at["New_Gas_OCGT", "p_nom_opt"]
    new_battery_mw  = n.storage_units.at["New_Battery","p_nom_opt"]
    new_battery_mwh = new_battery_mw * 4

    # Transmission
    line_original   = 2500
    line_optimised  = n.lines.at["Sydney-Orana", "s_nom_opt"]
    line_upgrade    = max(0, line_optimised - line_original)

    # Capital costs — multiply by 8760 to get annual figure
    solar_capex        = new_solar_mw   * 96_000
    wind_capex         = new_wind_mw    * 170_000
    gas_capex          = new_gas_mw     * 80_000
    battery_capex      = new_battery_mw * 660_000
    transmission_capex = line_upgrade   * 150_000
    total_capex = (
        solar_capex + wind_capex +
        gas_capex   + battery_capex +
        transmission_capex
    )

    # Operating cost
    dispatch = n.generators_t.p.copy()
    opex = (
        dispatch * n.generators.marginal_cost
    ).sum().sum()

    # Generation mix
    carrier_map      = n.generators.carrier
    dispatch_by_fuel = dispatch.T.groupby(carrier_map).sum().T

    # Totals
    total_solar = 6600 + new_solar_mw
    total_wind  = 2822 + new_wind_mw

    total_energy  = n.loads_t.p_set.sum().sum()
    renewable_gen = sum(
        dispatch_by_fuel[f].sum()
        for f in ["solar", "wind", "hydro"]
        if f in dispatch_by_fuel.columns
    )
    ren_pct = renewable_gen / total_energy * 100

    # Hourly cost
    hourly_cost = pd.Series(0.0, index=hours)
    for gen in dispatch.columns:
        if gen in n.generators.index:
            mc = n.generators.at[gen, "marginal_cost"]
            hourly_cost += dispatch[gen] * mc

    # Curtailment
    solar_cf = np.array([
        0, 0, 0, 0, 0, 0.02,
        0.15, 0.40, 0.65, 0.82, 0.92, 0.97,
        0.98, 0.95, 0.88, 0.75, 0.55, 0.20,
        0.02, 0, 0, 0, 0, 0
    ])
    wind_cf = np.array([
        0.45, 0.42, 0.40, 0.38, 0.40, 0.45,
        0.50, 0.48, 0.42, 0.40, 0.38, 0.35,
        0.33, 0.35, 0.40, 0.48, 0.55, 0.60,
        0.62, 0.58, 0.55, 0.52, 0.50, 0.47
    ])

    avail_solar = solar_cf * total_solar
    avail_wind  = wind_cf  * total_wind

    solar_disp = (
        dispatch.get(
            "Orana_Solar",
            pd.Series(0, index=hours)
        ).values +
        dispatch.get(
            "New_Solar",
            pd.Series(0, index=hours)
        ).values
    )
    wind_disp = (
        dispatch.get(
            "Orana_Wind",
            pd.Series(0, index=hours)
        ).values +
        dispatch.get(
            "New_Wind",
            pd.Series(0, index=hours)
        ).values
    )

    solar_curtailed = np.maximum(
        0, avail_solar - solar_disp
    ).sum()
    wind_curtailed  = np.maximum(
        0, avail_wind  - wind_disp
    ).sum()

    return {
        "new_solar_mw":       round(new_solar_mw,    0),
        "new_wind_mw":        round(new_wind_mw,     0),
        "new_gas_mw":         round(new_gas_mw,      0),
        "new_battery_mw":     round(new_battery_mw,  0),
        "new_battery_mwh":    round(new_battery_mwh, 0),
        "line_original_mw":   line_original,
        "line_upgraded_mw":   round(line_optimised,  0),
        "line_upgrade_mw":    round(line_upgrade,    0),
        "solar_capex":        round(solar_capex,     0),
        "wind_capex":         round(wind_capex,      0),
        "gas_capex":          round(gas_capex,       0),
        "battery_capex":      round(battery_capex,   0),
        "transmission_capex": round(transmission_capex, 0),
        "total_capex":        round(total_capex,     0),
        "total_opex":         round(opex,            0),
        "total_cost":         round(total_capex+opex,0),
        "dispatch":           dispatch,
        "dispatch_by_fuel":   dispatch_by_fuel,
        "hourly_cost":        hourly_cost,
        "renewable_pct":      round(ren_pct,         1),
        "total_solar":        round(total_solar,     0),
        "total_wind":         round(total_wind,      0),
        "solar_curtailed":    round(solar_curtailed, 0),
        "wind_curtailed":     round(wind_curtailed,  0),
        "hours":              hours,
        "demand":             n.loads_t.p_set["Sydney_Load"],
    }


def print_expansion_summary(results):
    """Print results."""

    print("=" * 55)
    print("   CAPACITY EXPANSION — FUTURE NSW")
    print("   Eraring + Bayswater retired | Demand +20%")
    print("=" * 55)

    print(f"\n  Peak future demand: {results['demand'].max():,.0f} MW")
    print(f"  (vs today:          10,100 MW)")

    print("\n--- What To Build ---")
    print(f"  New Solar:      {results['new_solar_mw']:>8,.0f} MW")
    print(f"  New Wind:       {results['new_wind_mw']:>8,.0f} MW")
    print(f"  New Gas OCGT:   {results['new_gas_mw']:>8,.0f} MW")
    print(f"  New Battery:    {results['new_battery_mw']:>8,.0f} MW")
    print(f"                  {results['new_battery_mwh']:>8,.0f} MWh")

    print("\n--- Transmission ---")
    print(
        f"  Line before:    "
        f"{results['line_original_mw']:>8,.0f} MW"
    )
    print(
        f"  Line after:     "
        f"{results['line_upgraded_mw']:>8,.0f} MW"
    )
    print(
        f"  Upgrade added:  "
        f"{results['line_upgrade_mw']:>8,.0f} MW"
    )

    print("\n--- Investment ($) ---")
    print(f"  Solar:          ${results['solar_capex']:>12,.0f}")
    print(f"  Wind:           ${results['wind_capex']:>12,.0f}")
    print(f"  Gas OCGT:       ${results['gas_capex']:>12,.0f}")
    print(f"  Battery:        ${results['battery_capex']:>12,.0f}")
    print(
        f"  Transmission:   "
        f"${results['transmission_capex']:>12,.0f}"
    )
    print(f"  TOTAL CAPEX:    ${results['total_capex']:>12,.0f}")
    print(f"  Operating cost: ${results['total_opex']:>12,.0f}")
    print(f"  TOTAL COST:     ${results['total_cost']:>12,.0f}")

    print("\n--- Performance ---")
    print(f"  Renewable share:{results['renewable_pct']:>7.1f}%")
    print(f"  Total solar:    {results['total_solar']:>8,.0f} MW")
    print(f"  Total wind:     {results['total_wind']:>8,.0f} MW")
    print(
        f"  Solar curtailed:{results['solar_curtailed']:>8,.0f} MWh"
    )
    print(
        f"  Wind curtailed: {results['wind_curtailed']:>8,.0f} MWh"
    )


# ── TEST ──────────────────────────────────────────────────────────
if __name__ == "__main__":

    print("=" * 55)
    print("NSW CAPACITY EXPANSION MODEL")
    print("=" * 55)
    print()
    print("Scenario:")
    print("  Eraring  RETIRED — 2,880 MW removed")
    print("  Bayswater RETIRED — 2,640 MW removed")
    print("  Demand growth: +20% from electrification")
    print()

    n, hours, demand = create_expansion_network()

    existing = n.generators[
        ~n.generators.p_nom_extendable
    ]["p_nom"].sum()

    print(f"  Future peak demand:  {demand.max():,.0f} MW")
    print(f"  Existing capacity:   {existing:,.0f} MW")
    print(
        f"  Investment gap:      "
        f"{demand.max() - existing:,.0f} MW"
    )
    print()
    print("Running optimisation...")

    n = run_expansion(n)
    results = get_expansion_results(n)
    print_expansion_summary(results)