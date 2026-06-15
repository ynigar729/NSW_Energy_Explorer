# -*- coding: utf-8 -*-
"""
Created on Sun Jun 14 21:58:22 2026

@author: yasmi
"""

import pypsa
import pandas as pd
import numpy as np
from  modules.dispatch import create_nsw_network

def create_network_with_battery(
        battery_power_mw=1096,
        battery_energy_mwh=4380,
        battery_efficiency=0.92
        ):
    """
    Add battery storage to NSW network.
    
    Default values based on Waratah Super Battery:
    - Power:      1,096 MW  (registered in your AEMO data)
    - Energy:     4,380 MWh (4 hour battery = 4 × 1,096)
    - Efficiency: 92%       (round trip efficiency)
    
    PyPSA StorageUnit object = PLEXOS Battery object
    Charges cheap, discharges expensive = arbitrage
    """
    n,hours,demand=create_nsw_network()
    
    n.add("StorageUnit","Waratah_Battery",
          bus="Sydney",
          p_nom=battery_power_mw,
          max_hours=battery_energy_mwh/battery_power_mw,
          efficiency_store=np.sqrt(battery_efficiency),
          efficiency_dispatch=np.sqrt(battery_efficiency),
          
          marginal_cost=0,
          marginal_cost_storage=0,
          
          state_of_charge_initial=0.5,
          cyclic_state_of_charge=True,
          carrier="battery"         
          )
    return n,hours,demand

def run_battery_dispatch(n):
    n.optimize(solver_name="highs")
    return n

def get_battery_results(n,results_base):
    """
    Extract battery-specific results after optimisation.
    Compare with base case (no battery)
    """
    hours=n.snapshots
    dispatch=n.generators_t.p.copy()
    
    battery_charge    = n.storage_units_t.p_store.get(
        "Waratah_Battery", pd.Series(0, index=hours)
    )
    battery_discharge = n.storage_units_t.p_dispatch.get(
        "Waratah_Battery", pd.Series(0, index=hours)
    )
    battery_soc       = n.storage_units_t.state_of_charge.get(
        "Waratah_Battery", pd.Series(0, index=hours)
    )

    # Net battery = discharge - charge
    battery_net = battery_discharge - battery_charge

     # ── SYSTEM COSTS ───────────────────────────────────────────────
    total_cost_with_battery = (
        n.generators_t.p *
        n.generators.marginal_cost
    ).sum().sum()

    total_cost_base = results_base["total_cost"]
    cost_saving     = total_cost_base - total_cost_with_battery

    # ── RENEWABLE METRICS ──────────────────────────────────────────
    carrier_map      = n.generators.carrier
    dispatch_by_fuel = dispatch.T.groupby(carrier_map).sum().T

    # Available vs dispatched renewables
    available_solar  = (
        n.generators_t.p_max_pu["Orana_Solar"] *
        n.generators.at["Orana_Solar", "p_nom"]
    )
    available_wind   = (
        n.generators_t.p_max_pu["Orana_Wind"] *
        n.generators.at["Orana_Wind", "p_nom"]
    )
    solar_curtailed  = (
        available_solar - dispatch.get(
            "Orana_Solar", pd.Series(0, index=hours)
        )
    ).clip(lower=0)
    wind_curtailed   = (
        available_wind - dispatch.get(
            "Orana_Wind", pd.Series(0, index=hours)
        )
    ).clip(lower=0)

    # ── ARBITRAGE REVENUE ──────────────────────────────────────────
    # Battery buys cheap, sells expensive
    # Revenue = discharge × price - charge × price
    try:
        price = n.buses_t.marginal_price.get(
            "Sydney", pd.Series(35, index=hours)
        )
        arbitrage_revenue = (
            battery_discharge * price -
            battery_charge    * price
        ).sum()
    except:
        arbitrage_revenue = 0

    # ── PEAK SHAVING ───────────────────────────────────────────────
    demand_series = n.loads_t.p_set["Sydney_Load"]
    # Net demand after battery = demand - battery net injection
    net_demand      = demand_series - battery_net
    peak_reduction  = demand_series.max() - net_demand.max()

    results_battery = {
        "dispatch":               dispatch,
        "dispatch_by_fuel":       dispatch_by_fuel,
        "battery_charge":         battery_charge,
        "battery_discharge":      battery_discharge,
        "battery_net":            battery_net,
        "battery_soc":            battery_soc,
        "total_cost":             total_cost_with_battery,
        "cost_saving":            cost_saving,
        "solar_curtailed":        solar_curtailed,
        "wind_curtailed":         wind_curtailed,
        "arbitrage_revenue":      arbitrage_revenue,
        "peak_reduction":         peak_reduction,
        "available_solar":        available_solar,
        "available_wind":         available_wind,
    }

    return results_battery


def print_battery_summary(results_battery):
    """Print battery operation summary."""

    print("=" * 55)
    print("   BATTERY DISPATCH RESULTS — Waratah Super Battery")
    print("=" * 55)

    bc = results_battery["battery_charge"]
    bd = results_battery["battery_discharge"]
    bs = results_battery["battery_soc"]

    print("\n--- Battery Operation (MW) ---")
    print(f"  Max charge rate:    {bc.max():>8,.1f} MW")
    print(f"  Max discharge rate: {bd.max():>8,.1f} MW")
    print(f"  Total charged:      {bc.sum():>8,.1f} MWh")
    print(f"  Total discharged:   {bd.sum():>8,.1f} MWh")
    print(f"  Max state of charge:{bs.max():>8,.1f} MWh")
    print(f"  Min state of charge:{bs.min():>8,.1f} MWh")

    print("\n--- System Benefits ---")
    print(f"  Cost saving:        ${results_battery['cost_saving']:>10,.2f}")
    print(f"  Peak reduction:     {results_battery['peak_reduction']:>8,.1f} MW")
    print(f"  Arbitrage revenue:  ${results_battery['arbitrage_revenue']:>10,.2f}")
    print(f"  Solar curtailed:    {results_battery['solar_curtailed'].sum():>8,.1f} MWh")
    print(f"  Wind curtailed:     {results_battery['wind_curtailed'].sum():>8,.1f} MWh")

    print("\n--- Hourly Battery Operation ---")
    battery_ops = pd.DataFrame({
        "Charge (MW)":    bc.round(1).values,
        "Discharge (MW)": bd.round(1).values,
        "SOC (MWh)":      bs.round(1).values,
    }, index=[f"{h.hour:02d}:00" for h in bc.index])
    print(battery_ops.to_string())


# ── QUICK TEST ─────────────────────────────────────────────────────
if __name__ == "__main__":
    from modules.dispatch import get_dispatch_results

    print("Building network with Waratah Super Battery...")
    n, hours, demand = create_network_with_battery(
        battery_power_mw=1096,
        battery_energy_mwh=4380,
        battery_efficiency=0.92
    )

    print("Running base case first...")
    n_base, h_base, d_base = create_nsw_network()
    n_base = run_battery_dispatch(n_base)
    results_base = get_dispatch_results(n_base)

    print("Running battery dispatch...")
    n = run_battery_dispatch(n)
    results_battery = get_battery_results(n, results_base)

    print_battery_summary(results_battery)