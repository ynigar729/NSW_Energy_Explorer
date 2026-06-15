# -*- coding: utf-8 -*-
"""
Created on Sun Jun 14 19:26:05 2026

@author: yasmi
"""

import pypsa
import pandas as pd
import numpy as np

def create_nsw_network():
    """
    Build a multi-bus NSW network with REAL generator data.
    Source: AEMO NEM Registration and Exemption List (June 2026)
    Sheet: PU and Scheduled Loads, filtered Region = NSW1
    """

    # --- 24-hour time index (17 Jan 2024 - peak summer day) ---
    hours = pd.date_range("2024-01-17", periods=24, freq="h")

    # --- Synthetic NSW load profile (MW) ---
    # Shape based on AEMO typical summer weekday demand for NSW
    # 17 Jan 2024 was a hot day - high air conditioning load
    nsw_demand = pd.Series([
        7200, 6900, 6700, 6600, 6700, 7200,
        7800, 8400, 9000, 9200, 9300, 9200,
        9100, 9000, 9200, 9400, 9600, 9800,
        10100, 9800, 9400, 9000, 8500, 7900
    ], index=hours)

    # --- Solar capacity factor (fraction of rated MW) ---
    # Source: AEMO ISP typical summer solar trace for NSW
    solar_profile = pd.Series([
        0.00, 0.00, 0.00, 0.00, 0.00, 0.02,
        0.15, 0.40, 0.65, 0.82, 0.92, 0.97,
        0.98, 0.95, 0.88, 0.75, 0.55, 0.20,
        0.02, 0.00, 0.00, 0.00, 0.00, 0.00
    ], index=hours)

    # --- Wind capacity factor ---
    # Source: AEMO ISP typical wind trace for Orana REZ NSW
    wind_profile = pd.Series([
        0.45, 0.42, 0.40, 0.38, 0.40, 0.45,
        0.50, 0.48, 0.42, 0.40, 0.38, 0.35,
        0.33, 0.35, 0.40, 0.48, 0.55, 0.60,
        0.62, 0.58, 0.55, 0.52, 0.50, 0.47
    ], index=hours)

    # --- Create PyPSA Network ---
    n = pypsa.Network()
    n.set_snapshots(hours)

    # ── BUSES ──────────────────────────────────────────────────────
    # Same as placing busbars on your single line diagram
    n.add("Bus", "Sydney")
    n.add("Bus", "Newcastle")
    n.add("Bus", "Orana")
    n.add("Bus", "Snowy")
    n.add("Bus", "Eraring")

    # ── TRANSMISSION LINES ─────────────────────────────────────────
    n.add("Line", "Sydney-Newcastle",
          bus0="Sydney", bus1="Newcastle",
          x=0.1, r=0.01, s_nom=3000)

    n.add("Line", "Newcastle-Eraring",
          bus0="Newcastle", bus1="Eraring",
          x=0.08, r=0.01, s_nom=2500)

    n.add("Line", "Sydney-Snowy",
          bus0="Sydney", bus1="Snowy",
          x=0.15, r=0.02, s_nom=2000)

    n.add("Line", "Sydney-Orana",
          bus0="Sydney", bus1="Orana",
          x=0.12, r=0.015, s_nom=2500)

    # ── LOAD ───────────────────────────────────────────────────────
    n.add("Load", "Sydney_Load",
          bus="Sydney",
          p_set=nsw_demand)

    # ── GENERATORS ─────────────────────────────────────────────────
    # Source: AEMO NEM Registration and Exemption List, June 2026
    # Marginal costs: estimated SRMC from AER State of Energy Market 2024

    # COAL — Eraring Power Station
    # REAL: 4 x 720 MW units = 2,880 MW registered capacity
    n.add("Generator", "Eraring_Coal",
          bus="Eraring",
          p_nom=2880,
          marginal_cost=35,
          p_min_pu=0.0,
          p_max_pu=1.0,
          carrier="coal")

    # COAL — Bayswater Power Station
    # REAL: 4 x 660 MW units = 2,640 MW registered capacity
    n.add("Generator", "Bayswater_Coal",
          bus="Newcastle",
          p_nom=2640,
          marginal_cost=38,
          p_min_pu=0.0,
          p_max_pu=1.0,
          carrier="coal")

    # COAL — Mt Piper Power Station
    # REAL: 2 x 700 MW units = 1,400 MW registered capacity
    n.add("Generator", "MtPiper_Coal",
          bus="Orana",
          p_nom=1400,
          marginal_cost=42,
          p_min_pu=0.0,
          p_max_pu=1.0,
          carrier="coal")

    # GAS CCGT — Tallawarra Power Station
    # REAL: 440 MW (unit A) + 320 MW (unit B) = 760 MW
    n.add("Generator", "Tallawarra_Gas",
          bus="Sydney",
          p_nom=760,
          marginal_cost=85,
          p_min_pu=0.0,
          p_max_pu=1.0,
          carrier="gas")

    # GAS CCGT — Uranquinty Power Station
    # REAL: 4 x 166 MW units = 664 MW registered capacity
    n.add("Generator", "Uranquinty_Gas",
          bus="Sydney",
          p_nom=664,
          marginal_cost=90,
          p_min_pu=0.0,
          p_max_pu=1.0,
          carrier="gas")

    # GAS PEAKER — Colongra Power Station
    # REAL: 4 x 181 MW units = 724 MW registered capacity
    n.add("Generator", "Colongra_Peaker",
          bus="Sydney",
          p_nom=724,
          marginal_cost=180,
          p_min_pu=0.0,
          p_max_pu=1.0,
          carrier="gas")

    # HYDRO — Snowy Scheme (Tumut 3 + Tumut + Shoalhaven)
    # REAL: 1500 + 616 + 240 = 2,356 MW
    n.add("Generator", "Snowy_Hydro",
          bus="Snowy",
          p_nom=2356,
          marginal_cost=12,
          p_min_pu=0.0,
          p_max_pu=1.0,
          carrier="hydro")

    # SOLAR — All NSW registered solar farms aggregated
    # REAL: 6,600 MW across 49 solar farms in NSW
    n.add("Generator", "Orana_Solar",
          bus="Orana",
          p_nom=6600,
          marginal_cost=3,
          p_min_pu=0.0,
          p_max_pu=1.0,
          carrier="solar")

    # WIND — All NSW registered wind farms aggregated
    # REAL: 2,822 MW across 20 wind farms in NSW
    n.add("Generator", "Orana_Wind",
          bus="Orana",
          p_nom=2822,
          marginal_cost=5,
          p_min_pu=0.0,
          p_max_pu=1.0,
          carrier="wind")

    # SLACK — Safety valve, covers any supply gap
    # Very expensive so only runs if nothing else can
    n.add("Generator", "Slack",
          bus="Sydney",
          p_nom=99999,
          marginal_cost=300,
          p_min_pu=0.0,
          p_max_pu=1.0,
          carrier="slack")

    # ── ATTACH TIME-VARYING PROFILES ───────────────────────────────
    n.generators_t.p_max_pu = pd.DataFrame({
        "Orana_Solar": solar_profile,
        "Orana_Wind":  wind_profile
    }, index=hours)

    return n, hours, nsw_demand


# ── QUICK TEST ─────────────────────────────────────────────────────
if __name__ == "__main__":
    n, hours, demand = create_nsw_network()

    print("=" * 50)
    print("✅ NSW Network created successfully")
    print("=" * 50)
    print(f"\nBuses:      {list(n.buses.index)}")
    print(f"Lines:      {list(n.lines.index)}")
    print(f"Generators: {list(n.generators.index)}")
    print(f"Snapshots:  {len(n.snapshots)} hours")
    print(f"Peak load:  {demand.max():,.0f} MW")
    print(f"Min load:   {demand.min():,.0f} MW")

    print("\n--- Generator Summary (REAL AEMO DATA) ---")
    print(n.generators[["bus", "p_nom", "marginal_cost", "carrier"]]
          .sort_values("marginal_cost")
          .to_string())

    total_cap = n.generators[n.generators.index != "Slack"]["p_nom"].sum()
    print(f"\nTotal installed capacity: {total_cap:,.0f} MW")
    print(f"Peak demand:              {demand.max():,.0f} MW")
    print(f"Reserve margin:           {(total_cap/demand.max()-1)*100:.1f}%")
    
def run_economic_dispatch(n):
    """
    Run linear optimal power flow (lopf) = Economic Dispatch
    PyPSA minimises total system cost subject to:
    - Demand must be met every hour
    - Generators cannot exceed their registered capacity
    - Solar/wind limited by their capacity factor profiles
    
    This is exactly what PLEXOS ST Schedule does.
    """

    # Run the optimisation
    # solver: use highs (free, fast, built into PyPSA)
    n.optimize(solver_name="highs")

    return n


def get_dispatch_results(n):
    """
    Extract results after optimisation.
    Returns generation by generator for each hour.
    """

    # Actual generation dispatched each hour (MW)
    dispatch = n.generators_t.p.copy()

    # Total system cost ($)
    total_cost = (
        n.generators_t.p *
        n.generators.marginal_cost
    ).sum().sum()

    # Generation by carrier/fuel type
    carrier_map = n.generators.carrier
    dispatch_by_fuel = dispatch.T.groupby(carrier_map).sum().T

    # Curtailment = available renewable - actual dispatched
    available_solar = (
        n.generators_t.p_max_pu["Orana_Solar"] *
        n.generators.at["Orana_Solar", "p_nom"]
    )
    available_wind = (
        n.generators_t.p_max_pu["Orana_Wind"] *
        n.generators.at["Orana_Wind", "p_nom"]
    )
    solar_curtailed = available_solar - dispatch.get("Orana_Solar", 0)
    wind_curtailed  = available_wind  - dispatch.get("Orana_Wind",  0)

    results = {
        "dispatch":         dispatch,
        "dispatch_by_fuel": dispatch_by_fuel,
        "total_cost":       total_cost,
        "solar_curtailed":  solar_curtailed,
        "wind_curtailed":   wind_curtailed,
        "available_solar":  available_solar,
        "available_wind":   available_wind,
    }

    return results


def print_dispatch_summary(results):
    """Print a clean summary of dispatch results."""

    print("=" * 55)
    print("   ECONOMIC DISPATCH RESULTS — NSW 17 Jan 2024")
    print("=" * 55)

    dispatch = results["dispatch"]
    by_fuel  = results["dispatch_by_fuel"]

    print("\n--- Average Generation by Fuel (MW) ---")
    for fuel in by_fuel.columns:
        avg = by_fuel[fuel].mean()
        if avg > 0.1:
            print(f"  {fuel:<12} {avg:>8,.1f} MW")

    print(f"\n--- Total System Cost ---")
    print(f"  ${results['total_cost']:>15,.2f}")
    print(f"  ${results['total_cost']/24:>15,.2f} per hour avg")

    print(f"\n--- Renewable Curtailment ---")
    print(f"  Solar curtailed: "
          f"{results['solar_curtailed'].sum():,.1f} MWh")
    print(f"  Wind curtailed:  "
          f"{results['wind_curtailed'].sum():,.1f} MWh")

    print("\n--- Hourly Dispatch (MW) ---")
    print(dispatch.round(0).to_string())


# ── RUN EVERYTHING ─────────────────────────────────────────────────
if __name__ == "__main__":

    # Step 1: Build network
    n, hours, demand = create_nsw_network()
    print("✅ Network built")

    # Step 2: Run dispatch
    print("\n⏳ Running economic dispatch...")
    n = run_economic_dispatch(n)
    print("✅ Dispatch complete")

    # Step 3: Get and print results
    results = get_dispatch_results(n)
    print_dispatch_summary(results)   
    
    