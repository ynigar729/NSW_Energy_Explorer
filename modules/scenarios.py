# -*- coding: utf-8 -*-
"""
Created on Mon Jun 15 09:47:55 2026

@author: yasmi
"""

import pypsa
import pandas as pd
import numpy as np


def run_scenario(scenario_name):
    """
    Run a specific energy scenario for NSW.

    Four scenarios:
    1. Base           — today's real NSW grid
    2. High Gas       — replace coal with gas
    3. High Renewables— replace coal with solar/wind
    4. Net Zero       — full transition + demand growth

    This mirrors PLEXOS ISP scenario methodology.
    """

    hours = pd.date_range("2024-01-17", periods=24, freq="h")

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

    base_demand = np.array([
        7200, 6900, 6700, 6600, 6700, 7200,
        7800, 8400, 9000, 9200, 9300, 9200,
        9100, 9000, 9200, 9400, 9600, 9800,
        10100, 9800, 9400, 9000, 8500, 7900
    ])

    # ── SCENARIO PARAMETERS ───────────────────────────────────────
    if scenario_name == "Base":
        # Today's real NSW grid
        # All coal running, existing renewables only
        demand_multiplier = 1.0
        coal_mw           = 6920
        gas_mw            = 2148
        solar_mw          = 6600
        wind_mw           = 2822
        battery_mw        = 0
        transmission_mw   = 2500
        coal_srmc         = 38
        gas_srmc          = 90
        description       = (
            "Today's NSW grid — real AEMO registered fleet"
        )

    elif scenario_name == "High Gas":
        # Replace all retiring coal with new gas CCGT
        # Gas is firm — runs 24 hours unlike solar
        # Higher emissions than renewables but lower than coal
        # Represents a fossil fuel transition pathway
        demand_multiplier = 1.0
        coal_mw           = 0       # all coal retired
        gas_mw            = 9068    # existing 2,148 + 6,920 replacement
        solar_mw          = 6600    # existing solar kept
        wind_mw           = 2822    # existing wind kept
        battery_mw        = 0
        transmission_mw   = 2500
        coal_srmc         = 0
        gas_srmc          = 90
        description       = (
            "Coal replaced by gas CCGT — firm but high emissions"
        )

    elif scenario_name == "High Renewables":
        # Replace coal with solar and wind
        # Upgrade transmission to unlock Orana REZ
        # Small battery for evening transition
        # Coal fully retired
        demand_multiplier = 1.0
        coal_mw           = 0       # all coal retired
        gas_mw            = 2148    # existing gas kept as backup
        solar_mw          = 12308   # existing + 5,708 new
        wind_mw           = 10822   # existing + 8,000 new
        battery_mw        = 696     # from expansion model
        transmission_mw   = 8000    # upgraded Orana line
        coal_srmc         = 0
        gas_srmc          = 90
        description       = (
            "Coal retired — solar/wind + gas backup"
        )

    elif scenario_name == "Net Zero":
        # Full energy transition
        # All coal retired, demand grows 20% from EVs
        # Large battery replaces gas firm capacity
        # Minimal gas emergency backup only
        demand_multiplier = 1.1    # +20% from electrification
        coal_mw           = 0       # all coal retired
        gas_mw            = 500    # emergency backup only
        solar_mw          = 12308   # maximum solar build
        wind_mw           = 10822   # existing + new wind
        battery_mw        = 8000    # large battery for overnight
        transmission_mw   = 8000    # upgraded line
        coal_srmc         = 0
        gas_srmc          = 250
        description       = (
            "Full transition — coal out, large battery, demand +20%"
        )

    # ── BUILD NETWORK ─────────────────────────────────────────────
    demand = pd.Series(
        base_demand * demand_multiplier,
        index=hours
    )

    n = pypsa.Network()
    n.set_snapshots(hours)

    # Buses
    for bus in ["Sydney","Newcastle","Orana","Snowy","Eraring"]:
        n.add("Bus", bus, carrier="AC")

    # Lines
    n.add("Line", "Sydney-Newcastle",
          bus0="Sydney", bus1="Newcastle",
          x=0.1, r=0.01, s_nom=3000, carrier="AC")
    n.add("Line", "Newcastle-Eraring",
          bus0="Newcastle", bus1="Eraring",
          x=0.08, r=0.01, s_nom=2500, carrier="AC")
    n.add("Line", "Sydney-Snowy",
          bus0="Sydney", bus1="Snowy",
          x=0.15, r=0.02, s_nom=2000, carrier="AC")
    n.add("Line", "Sydney-Orana",
          bus0="Sydney", bus1="Orana",
          x=0.12, r=0.015,
          s_nom=transmission_mw, carrier="AC")

    # Load
    n.add("Load", "Sydney_Load",
          bus="Sydney", p_set=demand)

    # Coal
    if coal_mw > 0:
        n.add("Generator", "Coal",
              bus="Eraring",
              p_nom=coal_mw,
              marginal_cost=coal_srmc,
              carrier="coal")

    # Gas
    if gas_mw > 0:
        n.add("Generator", "Gas",
              bus="Sydney",
              p_nom=gas_mw,
              marginal_cost=gas_srmc,
              carrier="gas")

    # Hydro
    n.add("Generator", "Snowy_Hydro",
          bus="Snowy",
          p_nom=2356,
          marginal_cost=12,
          carrier="hydro")

    # Solar
    n.add("Generator", "Solar",
          bus="Orana",
          p_nom=solar_mw,
          marginal_cost=3,
          carrier="solar",
          p_max_pu=solar_profile)

    # Wind
    n.add("Generator", "Wind",
          bus="Orana",
          p_nom=wind_mw,
          marginal_cost=5,
          carrier="wind",
          p_max_pu=wind_profile)

    # Slack — safety valve
    n.add("Generator", "Slack",
          bus="Sydney",
          p_nom=99999,
          marginal_cost=300,
          carrier="slack")

    # Battery
    if battery_mw > 0:
        n.add("StorageUnit", "Battery",
              bus="Sydney",
              p_nom=battery_mw,
              max_hours=4,
              marginal_cost=0,
              marginal_cost_storage=0,
              efficiency_store=np.sqrt(0.92),
              efficiency_dispatch=np.sqrt(0.92),
              state_of_charge_initial=0.5,
              cyclic_state_of_charge=True,
              carrier="battery")

    # Profiles
    pmax_df = {"Solar": solar_profile, "Wind": wind_profile}
    n.generators_t.p_max_pu = pd.DataFrame(
        pmax_df, index=hours
    )

    # ── OPTIMISE ──────────────────────────────────────────────────
    n.optimize(solver_name="highs")

    # ── EXTRACT RESULTS ───────────────────────────────────────────
    dispatch = n.generators_t.p.copy()

    # Total operating cost
    total_cost = (
        dispatch * n.generators.marginal_cost
    ).sum().sum()

    # Generation by fuel
    carrier_map      = n.generators.carrier
    dispatch_by_fuel = dispatch.T.groupby(carrier_map).sum().T

    # Renewable share
    total_energy  = demand.sum()
    renewable_gen = sum(
        dispatch_by_fuel[f].sum()
        for f in ["solar","wind","hydro"]
        if f in dispatch_by_fuel.columns
    )
    ren_pct = renewable_gen / total_energy * 100

    # Emissions
    # Coal = 0.9 tCO2/MWh (black coal NSW)
    # Gas  = 0.5 tCO2/MWh (CCGT)
    coal_gen = dispatch_by_fuel.get(
        "coal", pd.Series(0, index=hours)
    ).sum()
    gas_gen = dispatch_by_fuel.get(
        "gas",  pd.Series(0, index=hours)
    ).sum()
    emissions_tco2 = (coal_gen * 0.9) + (gas_gen * 0.5)

    # Curtailment
    solar_avail = (solar_profile * solar_mw).values
    wind_avail  = (wind_profile  * wind_mw).values
    solar_disp  = dispatch.get(
        "Solar", pd.Series(0, index=hours)
    ).values
    wind_disp   = dispatch.get(
        "Wind",  pd.Series(0, index=hours)
    ).values
    solar_curtailed = np.maximum(
        0, solar_avail - solar_disp
    ).sum()
    wind_curtailed  = np.maximum(
        0, wind_avail  - wind_disp
    ).sum()

    # Average spot price
    avg_price = total_cost / total_energy

    # Hourly cost
    hourly_cost = pd.Series(0.0, index=hours)
    for gen in dispatch.columns:
        if gen in n.generators.index:
            mc = n.generators.at[gen, "marginal_cost"]
            hourly_cost += dispatch[gen] * mc

    return {
        "scenario":         scenario_name,
        "description":      description,
        "total_cost":       round(total_cost,       0),
        "avg_price":        round(avg_price,        2),
        "renewable_pct":    round(ren_pct,          1),
        "emissions_tco2":   round(emissions_tco2,   0),
        "coal_mw":          coal_mw,
        "gas_mw":           gas_mw,
        "solar_mw":         solar_mw,
        "wind_mw":          wind_mw,
        "battery_mw":       battery_mw,
        "transmission_mw":  transmission_mw,
        "peak_demand":      round(demand.max(),     0),
        "solar_curtailed":  round(solar_curtailed,  0),
        "wind_curtailed":   round(wind_curtailed,   0),
        "dispatch_by_fuel": dispatch_by_fuel,
        "hourly_cost":      hourly_cost,
        "demand":           demand,
        "hours":            hours,
    }


def run_all_scenarios():
    """Run all four scenarios."""

    print("Running Base scenario...")
    base = run_scenario("Base")

    print("Running High Gas scenario...")
    high_gas = run_scenario("High Gas")

    print("Running High Renewables scenario...")
    high_ren = run_scenario("High Renewables")

   

    return base, high_gas, high_ren


# ── TEST ──────────────────────────────────────────────────────────
if __name__ == "__main__":

    base, high_gas, high_ren = run_all_scenarios()

    scenarios = [base, high_gas, high_ren]

    print("\n" + "=" * 75)
    print("   SCENARIO COMPARISON — NSW ENERGY TRANSITION")
    print("=" * 75)

    print(
        f"\n{'Metric':<25} "
        f"{'Base':>12} "
        f"{'High Gas':>12} "
        f"{'High Ren':>12} "
       
    )
    print("-" * 75)

    rows = [
        ("Total cost ($M)",      "total_cost",      1e6,  "{:.1f}"),
        ("Avg price ($/MWh)",    "avg_price",       1,    "{:.2f}"),
        ("Renewable share (%)",  "renewable_pct",   1,    "{:.1f}"),
        ("Emissions (tCO2)",     "emissions_tco2",  1,    "{:,.0f}"),
        ("Solar (MW)",           "solar_mw",        1,    "{:,.0f}"),
        ("Wind (MW)",            "wind_mw",         1,    "{:,.0f}"),
        ("Coal (MW)",            "coal_mw",         1,    "{:,.0f}"),
        ("Gas (MW)",             "gas_mw",          1,    "{:,.0f}"),
        ("Battery (MW)",         "battery_mw",      1,    "{:,.0f}"),
        ("Peak demand (MW)",     "peak_demand",     1,    "{:,.0f}"),
        ("Solar curtailed MWh",  "solar_curtailed", 1,    "{:,.0f}"),
        ("Wind curtailed MWh",   "wind_curtailed",  1,    "{:,.0f}"),
    ]

    for label, key, divisor, fmt in rows:
        vals = [fmt.format(sc[key]/divisor) for sc in scenarios]
        print(
            f"{label:<25} "
            f"{vals[0]:>12} "
            f"{vals[1]:>12} "
            f"{vals[2]:>12} "
           
        )