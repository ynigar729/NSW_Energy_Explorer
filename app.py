import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import sys, os

sys.path.append(os.path.dirname(__file__))
from modules.dispatch import (
    create_nsw_network,
    run_economic_dispatch,
    get_dispatch_results
)
from modules.storage import (
    create_network_with_battery,
    run_battery_dispatch,
    get_battery_results
)

from modules.expansion import (
    create_expansion_network,
    run_expansion,
    get_expansion_results
)

from modules.scenarios import run_all_scenarios
# ── PAGE CONFIG ────────────────────────────────────────────────────
st.set_page_config(
    page_title="NSW Energy Transition Scenario Explorer",
    page_icon="⚡",
    layout="wide"
)

COLOURS = {
    "coal":  "#4a4a4a",
    "gas":   "#f4a261",
    "hydro": "#2196f3",
    "solar": "#ffd600",
    "wind":  "#66bb6a",
    "slack": "#e53935",
}

# ── CUSTOM CSS ─────────────────────────────────────────────────────
st.markdown("""
<style>
    .block-container { padding: 1.5rem 2rem; }
    .dash-title {
        font-size: 26px; font-weight: 600;
        color: #1a1a2e; margin-bottom: 0px;
    }
    .dash-sub {
        font-size: 13px; color: #6c757d;
        margin-bottom: 1rem;
    }
    .kpi-card {
        background: white;
        border-radius: 12px;
        padding: 16px 20px;
        border: 1px solid #e9ecef;
    }
    .kpi-label {
        font-size: 11px; color: #6c757d;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 6px;
    }
    .kpi-value {
        font-size: 24px; font-weight: 600;
        color: #1a1a2e; margin-bottom: 2px;
    }
    .kpi-sub { font-size: 11px; color: #adb5bd; }
    .section-title {
        font-size: 14px; font-weight: 600;
        color: #1a1a2e; margin-bottom: 0px;
        padding-bottom: 8px;
        border-bottom: 2px solid #f0f0f0;
    }
    .footer {
        font-size: 11px; color: #adb5bd;
        text-align: center;
        padding-top: 1rem;
        border-top: 1px solid #e9ecef;
        margin-top: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# ── HEADER ─────────────────────────────────────────────────────────
st.markdown(
    '<p class="dash-title">⚡ NSW Energy Transition Scenario Explorer</p>',
    unsafe_allow_html=True
)
st.markdown(
    '<p class="dash-sub">'
    'Economic dispatch — 17 January 2024 (peak NSW summer demand) '
    '&nbsp;|&nbsp; '
    'Source: AEMO NEM Registration & Exemption List, June 2026 '
    '&nbsp;|&nbsp; '
    'Model: PyPSA + HiGHS solver'
    '</p>',
    unsafe_allow_html=True
)

# ── RUN ALL MODELS ONCE ────────────────────────────────────────────
with st.spinner("⏳ Running all models — please wait..."):

    # Module 1 — Base dispatch
    n, hours, demand = create_nsw_network()
    n = run_economic_dispatch(n)
    results = get_dispatch_results(n)

    # Module 2 — Battery
    n_bat, hours_bat, demand_bat = create_network_with_battery(
        battery_power_mw=1096,
        battery_energy_mwh=4380,
        battery_efficiency=0.92
    )
    n_bat = run_battery_dispatch(n_bat)
    results_bat = get_battery_results(n_bat, results)
   # Module 3 - Capacity Expansion
    n_exp, hours_exp, demand_exp = create_expansion_network()
    n_exp = run_expansion(n_exp)
    results_exp = get_expansion_results(n_exp)
    # Module 4 — Scenarios
    print("Running scenarios...")
    base_sc, high_gas_sc, high_ren_sc = run_all_scenarios()
    
   
st.success("✅ All models complete")
st.markdown("---")

# ── SHARED DATA ────────────────────────────────────────────────────
hour_labels = [f"{h.hour:02d}:00" for h in hours]

solar_cf_arr = np.array([
    0,0,0,0,0,0.02,0.15,0.40,0.65,0.82,
    0.92,0.97,0.98,0.95,0.88,0.75,0.55,
    0.20,0.02,0,0,0,0,0
])
wind_cf_arr = np.array([
    0.45,0.42,0.40,0.38,0.40,0.45,0.50,
    0.48,0.42,0.40,0.38,0.35,0.33,0.35,
    0.40,0.48,0.55,0.60,0.62,0.58,0.55,
    0.52,0.50,0.47
])

avail_solar = solar_cf_arr * 6600
avail_wind  = wind_cf_arr  * 2822

dispatch_base    = results["dispatch"]
dispatch_by_fuel = results["dispatch_by_fuel"]
dispatch_battery = results_bat["dispatch"]
dispatch_bat_fuel= results_bat["dispatch_by_fuel"]

battery_charge    = results_bat["battery_charge"]
battery_discharge = results_bat["battery_discharge"]
battery_soc       = results_bat["battery_soc"]
cost_saving       = results_bat["cost_saving"]
peak_reduction    = results_bat["peak_reduction"]
total_charged     = battery_charge.sum()
total_discharged  = battery_discharge.sum()
efficiency_loss   = total_charged - total_discharged

total_cost   = results["total_cost"]
total_energy = demand.sum()
avg_price    = total_cost / total_energy
renewable_gen = sum(
    dispatch_by_fuel[f].sum()
    for f in ["solar","wind","hydro"]
    if f in dispatch_by_fuel.columns
)
ren_pct = renewable_gen / total_energy * 100
solar_curtailed = results["solar_curtailed"].sum()
wind_curtailed  = results["wind_curtailed"].sum()

def safe_get_dispatch(dispatch_df, gen_name, index):
    """Safely extract generator dispatch — returns zeros if not found"""
    if gen_name in dispatch_df.columns:
        return dispatch_df[gen_name].values
    else:
        print(f"WARNING: {gen_name} not found in dispatch")
        print(f"Available columns: {dispatch_df.columns.tolist()}")
        return np.zeros(len(index))

base_solar_disp = safe_get_dispatch(
    dispatch_base, "Orana_Solar", hours
)
base_wind_disp  = safe_get_dispatch(
    dispatch_base, "Orana_Wind", hours
)
bat_solar_disp  = safe_get_dispatch(
    dispatch_battery, "Orana_Solar", hours_bat
)
bat_wind_disp   = safe_get_dispatch(
    dispatch_battery, "Orana_Wind", hours_bat
)


base_sol_curt = np.maximum(0, avail_solar - base_solar_disp)
base_win_curt = np.maximum(0, avail_wind  - base_wind_disp)
bat_sol_curt  = np.maximum(0, avail_solar - bat_solar_disp)
bat_win_curt  = np.maximum(0, avail_wind  - bat_wind_disp)

# Debug print — remove after fixing
print("Solar curtailed sample (07:00-12:00):", bat_sol_curt[7:13])
print("Wind curtailed sample (07:00-12:00):", bat_win_curt[7:13])
def hourly_cost(dispatch_df, n_network):
    costs = pd.Series(0.0, index=dispatch_df.index)
    for gen in dispatch_df.columns:
        if gen in n_network.generators.index:
            mc = n_network.generators.at[gen, "marginal_cost"]
            costs += dispatch_df[gen] * mc
    return costs

cost_base_hourly    = hourly_cost(dispatch_base,    n)
cost_battery_hourly = hourly_cost(dispatch_battery, n_bat)
cost_saving_hourly  = cost_base_hourly - cost_battery_hourly

# ── TABS ───────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Module 1 — Economic Dispatch",
    "🔋 Module 2 — Battery & Storage",
    "🏗️ Module 3 — Capacity Expansion",
    "🌍 Module 4 — Scenario Analysis",
    "📋 Raw Data"
])

# ══════════════════════════════════════════════════════════════════
# TAB 1 — ECONOMIC DISPATCH
# ══════════════════════════════════════════════════════════════════
with tab1:
    st.header("📊 Module 1: Economic Dispatch")
    st.markdown(
        "Merit order dispatch — 17 January 2024 "
        "(peak NSW summer demand day)"
    )

    # ── KPI CARDS ─────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    k1,k2,k3,k4,k5,k6 = st.columns(6)

    with k1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">💰 Total system cost</div>
            <div class="kpi-value">${total_cost/1e6:.1f}M</div>
            <div class="kpi-sub">17 Jan 2024, 24 hrs</div>
        </div>""", unsafe_allow_html=True)

    with k2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">⚡ Avg spot price</div>
            <div class="kpi-value">${avg_price:.1f}</div>
            <div class="kpi-sub">$/MWh estimated</div>
        </div>""", unsafe_allow_html=True)

    with k3:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">🌿 Renewable share</div>
            <div class="kpi-value">{ren_pct:.1f}%</div>
            <div class="kpi-sub">Solar + wind + hydro</div>
        </div>""", unsafe_allow_html=True)

    with k4:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">📈 Peak demand</div>
            <div class="kpi-value">10,100 MW</div>
            <div class="kpi-sub">Evening peak 18:00</div>
        </div>""", unsafe_allow_html=True)

    with k5:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">☀️ Solar curtailed</div>
            <div class="kpi-value">{solar_curtailed:,.0f}</div>
            <div class="kpi-sub">MWh wasted</div>
        </div>""", unsafe_allow_html=True)

    with k6:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">💨 Wind curtailed</div>
            <div class="kpi-value">{wind_curtailed:,.0f}</div>
            <div class="kpi-sub">MWh wasted</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── GENERATION STACK ──────────────────────────────────────────
    st.markdown(
        '<p class="section-title">🔋 Hourly Generation Stack (MW)</p>',
        unsafe_allow_html=True
    )
    fig_stack = go.Figure()
    for fuel in ["solar","wind","hydro","coal","gas"]:
        if fuel in dispatch_by_fuel.columns:
            fig_stack.add_trace(go.Bar(
                name=fuel.capitalize(),
                x=hour_labels,
                y=dispatch_by_fuel[fuel].round(0),
                marker_color=COLOURS[fuel],
                hovertemplate=(
                    f"<b>{fuel.capitalize()}</b><br>"
                    f"%{{x}}<br>%{{y:,.0f}} MW<extra></extra>"
                )
            ))
    fig_stack.add_trace(go.Scatter(
        name="Demand",
        x=hour_labels,
        y=demand.values,
        mode="lines+markers",
        line=dict(color="#e53935", width=2.5, dash="dash"),
        marker=dict(size=4, color="#e53935"),
        hovertemplate=(
            "<b>Demand</b><br>"
            "%{x}<br>%{y:,.0f} MW<extra></extra>"
        )
    ))
    fig_stack.update_layout(
        barmode="stack", height=320,
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=50,r=20,t=20,b=60),
        legend=dict(orientation="h",y=-0.25,x=0,font=dict(size=11)),
        xaxis=dict(showgrid=False, tickfont=dict(size=10)),
        yaxis=dict(
            title="MW", gridcolor="#f0f0f0",
            tickfont=dict(size=10), tickformat=","
        ),
        hovermode="x unified"
    )
    st.plotly_chart(fig_stack, use_container_width=True)

    # ── MERIT ORDER + DONUT ───────────────────────────────────────
    col_left, col_right = st.columns([3,2])

    generators = [
        {"name":"Orana Solar",    "fuel":"solar","mw":6600, "srmc":3},
        {"name":"Orana Wind",     "fuel":"wind", "mw":2822, "srmc":5},
        {"name":"Snowy Hydro",    "fuel":"hydro","mw":2356, "srmc":12},
        {"name":"Eraring Coal",   "fuel":"coal", "mw":2880, "srmc":35},
        {"name":"Bayswater Coal", "fuel":"coal", "mw":2640, "srmc":38},
        {"name":"Mt Piper Coal",  "fuel":"coal", "mw":1400, "srmc":42},
        {"name":"Tallawarra Gas", "fuel":"gas",  "mw":760,  "srmc":85},
        {"name":"Uranquinty Gas", "fuel":"gas",  "mw":664,  "srmc":90},
        {"name":"Colongra Peaker","fuel":"gas",  "mw":724,  "srmc":180},
    ]

    with col_left:
        st.markdown(
            '<p class="section-title">📈 Merit Order Supply Curve</p>',
            unsafe_allow_html=True
        )
        x_vals, y_vals = [], []
        cumulative = 0
        for g in generators:
            x_vals += [cumulative, cumulative + g["mw"]]
            y_vals += [g["srmc"],  g["srmc"]]
            cumulative += g["mw"]

        fig_merit = go.Figure()
        fig_merit.add_trace(go.Scatter(
            x=x_vals, y=y_vals,
            mode="lines",
            line=dict(color="#1565C0", width=2.5),
            fill="tozeroy",
            fillcolor="rgba(21,101,192,0.08)",
            name="Supply curve",
            hovertemplate=(
                "%{x:,.0f} MW → $%{y}/MWh<extra></extra>"
            )
        ))
        cum = 0
        for g in generators:
            fig_merit.add_trace(go.Scatter(
                x=[cum + g["mw"]/2],
                y=[g["srmc"]],
                mode="markers",
                marker=dict(
                    color=COLOURS[g["fuel"]],
                    size=12, symbol="square"
                ),
                showlegend=False,
                hovertemplate=(
                    f"<b>{g['name']}</b><br>"
                    f"{g['mw']:,} MW<br>"
                    f"${g['srmc']}/MWh<extra></extra>"
                )
            ))
            cum += g["mw"]

        fig_merit.add_vline(
            x=float(demand.max()),
            line_dash="dash",
            line_color="#e53935",
            line_width=2,
            annotation_text=(
                f"Peak demand<br>{demand.max():,.0f} MW"
            ),
            annotation_position="top right",
            annotation_font=dict(color="#e53935", size=10)
        )
        srmc_vals = sorted(set(g["srmc"] for g in generators))
        fig_merit.update_layout(
            height=280,
            plot_bgcolor="white", paper_bgcolor="white",
            margin=dict(l=50,r=20,t=20,b=50),
            showlegend=False,
            xaxis=dict(
                title="Cumulative capacity (MW)",
                tickformat=",", tickfont=dict(size=10),
                showgrid=False
            ),
            yaxis=dict(
                title="SRMC ($/MWh)",
                tickmode="array",
                tickvals=srmc_vals,
                ticktext=[f"${v}" for v in srmc_vals],
                tickfont=dict(size=10),
                gridcolor="#f0f0f0"
            )
        )
        st.plotly_chart(fig_merit, use_container_width=True)

    with col_right:
        st.markdown(
            '<p class="section-title">🥧 Generation Mix by Fuel</p>',
            unsafe_allow_html=True
        )
        fuel_totals = {
            f.capitalize(): dispatch_by_fuel[f].sum()
            for f in ["solar","wind","hydro","coal","gas"]
            if f in dispatch_by_fuel.columns
        }
        fig_donut = go.Figure(go.Pie(
            labels=list(fuel_totals.keys()),
            values=[round(v,0) for v in fuel_totals.values()],
            hole=0.62,
            marker=dict(
                colors=[
                    COLOURS[f.lower()]
                    for f in fuel_totals.keys()
                ],
                line=dict(color="white", width=2)
            ),
            textinfo="label+percent",
            textfont=dict(size=11),
            hovertemplate=(
                "<b>%{label}</b><br>"
                "%{value:,.0f} MWh<br>"
                "%{percent}<extra></extra>"
            )
        ))
        fig_donut.update_layout(
            height=280,
            paper_bgcolor="white",
            margin=dict(l=10,r=10,t=20,b=10),
            showlegend=False,
            annotations=[dict(
                text=f"<b>{ren_pct:.0f}%</b><br>renewable",
                x=0.5, y=0.5,
                font=dict(size=14, color="#1a1a2e"),
                showarrow=False
            )]
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    # ── SOLAR & WIND PROFILES ─────────────────────────────────────
    col_sol, col_win = st.columns(2)

    with col_sol:
        st.markdown(
            '<p class="section-title">☀️ Solar Generation Profile (MW)</p>',
            unsafe_allow_html=True
        )
        fig_sol = go.Figure(go.Scatter(
            x=hour_labels,
            y=(solar_cf_arr * 6600).round(0),
            mode="lines",
            fill="tozeroy",
            line=dict(color="#ffd600", width=2),
            fillcolor="rgba(255,214,0,0.15)",
            hovertemplate="%{x}<br>%{y:,.0f} MW<extra></extra>"
        ))
        fig_sol.update_layout(
            height=200, plot_bgcolor="white",
            paper_bgcolor="white",
            margin=dict(l=50,r=10,t=10,b=40),
            showlegend=False,
            xaxis=dict(
                showgrid=False,
                tickfont=dict(size=9), tickangle=45
            ),
            yaxis=dict(
                gridcolor="#f0f0f0",
                tickfont=dict(size=9),
                tickformat=",", title="MW"
            )
        )
        st.plotly_chart(fig_sol, use_container_width=True)

    with col_win:
        st.markdown(
            '<p class="section-title">💨 Wind Generation Profile (MW)</p>',
            unsafe_allow_html=True
        )
        fig_win = go.Figure(go.Scatter(
            x=hour_labels,
            y=(wind_cf_arr * 2822).round(0),
            mode="lines",
            fill="tozeroy",
            line=dict(color="#66bb6a", width=2),
            fillcolor="rgba(102,187,106,0.15)",
            hovertemplate="%{x}<br>%{y:,.0f} MW<extra></extra>"
        ))
        fig_win.update_layout(
            height=200, plot_bgcolor="white",
            paper_bgcolor="white",
            margin=dict(l=50,r=10,t=10,b=40),
            showlegend=False,
            xaxis=dict(
                showgrid=False,
                tickfont=dict(size=9), tickangle=45
            ),
            yaxis=dict(
                gridcolor="#f0f0f0",
                tickfont=dict(size=9),
                tickformat=",", title="MW"
            )
        )
        st.plotly_chart(fig_win, use_container_width=True)

    # ── FLEET TABLE ───────────────────────────────────────────────
    st.markdown(
        '<p class="section-title">'
        '🏭 Generator Fleet — AEMO Registered Capacity'
        '</p>',
        unsafe_allow_html=True
    )
    generators_df = pd.DataFrame([
        {"Station":"Orana Solar",    "Fuel":"Solar",
         "Capacity (MW)":6600,  "SRMC ($/MWh)":3,   "Merit #":1},
        {"Station":"Orana Wind",     "Fuel":"Wind",
         "Capacity (MW)":2822,  "SRMC ($/MWh)":5,   "Merit #":2},
        {"Station":"Snowy Hydro",    "Fuel":"Hydro",
         "Capacity (MW)":2356,  "SRMC ($/MWh)":12,  "Merit #":3},
        {"Station":"Eraring Coal",   "Fuel":"Coal",
         "Capacity (MW)":2880,  "SRMC ($/MWh)":35,  "Merit #":4},
        {"Station":"Bayswater Coal", "Fuel":"Coal",
         "Capacity (MW)":2640,  "SRMC ($/MWh)":38,  "Merit #":5},
        {"Station":"Mt Piper Coal",  "Fuel":"Coal",
         "Capacity (MW)":1400,  "SRMC ($/MWh)":42,  "Merit #":6},
        {"Station":"Tallawarra Gas", "Fuel":"Gas",
         "Capacity (MW)":760,   "SRMC ($/MWh)":85,  "Merit #":7},
        {"Station":"Uranquinty Gas", "Fuel":"Gas",
         "Capacity (MW)":664,   "SRMC ($/MWh)":90,  "Merit #":8},
        {"Station":"Colongra Peaker","Fuel":"Gas",
         "Capacity (MW)":724,   "SRMC ($/MWh)":180, "Merit #":9},
    ])
    st.dataframe(
        generators_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Capacity (MW)": st.column_config.ProgressColumn(
                "Capacity (MW)",
                min_value=0, max_value=7000,
                format="%d MW"
            ),
            "SRMC ($/MWh)": st.column_config.ProgressColumn(
                "SRMC ($/MWh)",
                min_value=0, max_value=200,
                format="$%d"
            ),
        }
    )

    with st.expander("🔍 View raw hourly dispatch data"):
        st.dataframe(
            results["dispatch"].round(1),
            use_container_width=True
        )


# ══════════════════════════════════════════════════════════════════
# TAB 2 — BATTERY & STORAGE
# ══════════════════════════════════════════════════════════════════
with tab2:
    st.header("🔋 Module 2: Battery & Renewable Storage")
    st.markdown(
        "**Waratah Super Battery — 1,096 MW / 4,380 MWh** "
        "&nbsp;|&nbsp; DUID: WTAHB1 "
        "&nbsp;|&nbsp; Round trip efficiency: 92%"
    )

    # ── BATTERY KPI CARDS ─────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    b1,b2,b3,b4,b5,b6 = st.columns(6)

    with b1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">💰 System cost saving</div>
            <div class="kpi-value">${cost_saving/1e3:.1f}K</div>
            <div class="kpi-sub">vs no battery</div>
        </div>""", unsafe_allow_html=True)

    with b2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">⬇️ Peak reduction</div>
            <div class="kpi-value">{peak_reduction:,.0f} MW</div>
            <div class="kpi-sub">evening peak shaved</div>
        </div>""", unsafe_allow_html=True)

    with b3:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">⚡ Total charged</div>
            <div class="kpi-value">{total_charged:,.0f}</div>
            <div class="kpi-sub">MWh absorbed</div>
        </div>""", unsafe_allow_html=True)

    with b4:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">🔌 Total discharged</div>
            <div class="kpi-value">{total_discharged:,.0f}</div>
            <div class="kpi-sub">MWh injected</div>
        </div>""", unsafe_allow_html=True)

    with b5:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">📉 Efficiency loss</div>
            <div class="kpi-value">{efficiency_loss:,.0f}</div>
            <div class="kpi-sub">MWh lost as heat</div>
        </div>""", unsafe_allow_html=True)

    with b6:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">🔋 Max SOC</div>
            <div class="kpi-value">{battery_soc.max():,.0f}</div>
            <div class="kpi-sub">MWh peak stored</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── BATTERY OPERATION CHART ───────────────────────────────────
    st.markdown(
        '<p class="section-title">'
        '🔋 Battery Charging / Discharging / SOC'
        '</p>',
        unsafe_allow_html=True
    )

    fig_bat = go.Figure()

    fig_bat.add_trace(go.Bar(
        name="Charging (absorbing from grid)",
        x=hour_labels,
        y=[-v for v in battery_charge.values],
        marker_color="#2196f3",
        opacity=0.8,
        hovertemplate=(
            "<b>Charging</b><br>"
            "Hour: %{x}<br>"
            "Rate: %{customdata:,.0f} MW<extra></extra>"
        ),
        customdata=battery_charge.values
    ))

    fig_bat.add_trace(go.Bar(
        name="Discharging (injecting to grid)",
        x=hour_labels,
        y=battery_discharge.values,
        marker_color="#66bb6a",
        opacity=0.8,
        hovertemplate=(
            "<b>Discharging</b><br>"
            "Hour: %{x}<br>"
            "Rate: %{y:,.0f} MW<extra></extra>"
        )
    ))

    fig_bat.add_trace(go.Scatter(
        name="State of Charge (MWh)",
        x=hour_labels,
        y=battery_soc.values,
        mode="lines+markers",
        line=dict(color="#ff9800", width=3),
        marker=dict(size=6, color="#ff9800"),
        yaxis="y2",
        hovertemplate=(
            "<b>SOC</b><br>"
            "Hour: %{x}<br>"
            "Stored: %{y:,.0f} MWh<extra></extra>"
        )
    ))

    fig_bat.add_hline(y=0, line_color="#cccccc", line_width=1)

    fig_bat.update_layout(
        barmode="relative", height=380,
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=60,r=80,t=20,b=60),
        legend=dict(
            orientation="h",y=-0.25,x=0,
            font=dict(size=11)
        ),
        xaxis=dict(
            title="Hour of day",
            showgrid=False, tickfont=dict(size=10)
        ),
        yaxis=dict(
            title="Power (MW)",
            gridcolor="#f0f0f0",
            tickfont=dict(size=10), tickformat=","
        ),
        yaxis2=dict(
    title=dict(
        text="State of Charge (MWh)",
        font=dict(color="#ff9800")    # ← correct modern syntax
    ),
    overlaying="y", side="right",
    tickfont=dict(size=10), tickformat=",",
    range=[0, 4380*1.1],
    showgrid=False,
    tickcolor="#ff9800",
),
        hovermode="x unified"
    )
    st.plotly_chart(fig_bat, use_container_width=True)

    st.info(
        "💡 **Reading this chart:** "
        "Blue bars = battery charging (pulling from grid). "
        "Green bars = battery discharging (pushing to grid). "
        "Orange line = state of charge (fuel gauge). "
        "Battery charges overnight cheap and "
        "discharges at evening peak replacing expensive gas."
    )

    # ── GENERATION STACK WITH BATTERY ─────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<p class="section-title">'
        '🔋 Hourly Generation Stack — With Battery'
        '</p>',
        unsafe_allow_html=True
    )

    fig_stack_bat = go.Figure()
    for fuel in ["solar","wind","hydro","coal","gas"]:
        if fuel in dispatch_bat_fuel.columns:
            fig_stack_bat.add_trace(go.Bar(
                name=fuel.capitalize(),
                x=hour_labels,
                y=dispatch_bat_fuel[fuel].round(0),
                marker_color=COLOURS[fuel],
                hovertemplate=(
                    f"<b>{fuel.capitalize()}</b><br>"
                    f"%{{x}}<br>%{{y:,.0f}} MW<extra></extra>"
                )
            ))

    fig_stack_bat.add_trace(go.Bar(
        name="Battery discharge",
        x=hour_labels,
        y=battery_discharge.round(0).values,
        marker_color="#ff9800",
        hovertemplate=(
            "<b>Battery</b><br>"
            "%{x}<br>%{y:,.0f} MW<extra></extra>"
        )
    ))

    fig_stack_bat.add_trace(go.Scatter(
        name="Demand",
        x=hour_labels,
        y=demand_bat.values,
        mode="lines+markers",
        line=dict(color="#e53935", width=2.5, dash="dash"),
        marker=dict(size=4, color="#e53935"),
        hovertemplate=(
            "<b>Demand</b><br>"
            "%{x}<br>%{y:,.0f} MW<extra></extra>"
        )
    ))

    fig_stack_bat.update_layout(
        barmode="stack", height=320,
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=50,r=20,t=20,b=60),
        legend=dict(
            orientation="h",y=-0.25,x=0,
            font=dict(size=11)
        ),
        xaxis=dict(showgrid=False, tickfont=dict(size=10)),
        yaxis=dict(
            title="MW", gridcolor="#f0f0f0",
            tickfont=dict(size=10), tickformat=","
        ),
        hovermode="x unified"
    )
    st.plotly_chart(fig_stack_bat, use_container_width=True)

    # ── COST COMPARISON ───────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<p class="section-title">'
        '💰 Hourly Cost — With vs Without Battery'
        '</p>',
        unsafe_allow_html=True
    )

    fig_cost = go.Figure()

    fig_cost.add_trace(go.Scatter(
        name="Without battery",
        x=hour_labels,
        y=cost_base_hourly.round(0).values,
        mode="lines+markers",
        line=dict(color="#e53935", width=2.5),
        marker=dict(size=5),
        hovertemplate=(
            "<b>No battery</b><br>"
            "%{x}<br>$%{y:,.0f}<extra></extra>"
        )
    ))

    fig_cost.add_trace(go.Scatter(
        name="With Waratah Battery",
        x=hour_labels,
        y=cost_battery_hourly.round(0).values,
        mode="lines+markers",
        line=dict(color="#66bb6a", width=2.5),
        marker=dict(size=5),
        hovertemplate=(
            "<b>With battery</b><br>"
            "%{x}<br>$%{y:,.0f}<extra></extra>"
        )
    ))

    fig_cost.add_trace(go.Bar(
        name="Cost saving",
        x=hour_labels,
        y=cost_saving_hourly.round(0).values,
        marker_color="#ff9800",
        opacity=0.5,
        hovertemplate=(
            "<b>Saving</b><br>"
            "%{x}<br>$%{y:,.0f}<extra></extra>"
        )
    ))

    fig_cost.update_layout(
        height=320,
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=60,r=20,t=20,b=60),
        legend=dict(
            orientation="h",y=-0.25,x=0,
            font=dict(size=11)
        ),
        xaxis=dict(
            title="Hour of day",
            showgrid=False, tickfont=dict(size=10)
        ),
        yaxis=dict(
            title="Hourly cost ($)",
            gridcolor="#f0f0f0",
            tickfont=dict(size=10), tickformat=","
        ),
        hovermode="x unified",
        barmode="overlay"
    )
    st.plotly_chart(fig_cost, use_container_width=True)



    # ── HOUR BY HOUR TABLE ────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<p class="section-title">'
        '🔍 Hour-by-Hour Battery Operation Detail'
        '</p>',
        unsafe_allow_html=True
    )

    battery_table = pd.DataFrame({
        "Hour":                   hour_labels,
        "Demand (MW)":            demand_bat.values.round(0),
        "Solar available (MW)":   avail_solar.round(0),
        "Solar dispatched (MW)":  bat_solar_disp.round(0),
        "Solar curtailed (MW)":   bat_sol_curt.round(0),
        "Wind curtailed (MW)":    bat_win_curt.round(0),
        "Battery charging (MW)":  battery_charge.values.round(0),
        "Battery discharge (MW)": battery_discharge.values.round(0),
        "SOC (MWh)":              battery_soc.values.round(0),
        "Hourly cost ($)":        cost_battery_hourly.values.round(0),
        "Cost saving ($)":        cost_saving_hourly.values.round(0),
    })

    def battery_status(row):
        if row["Battery charging (MW)"] > 10:
            return "🔵 Charging"
        elif row["Battery discharge (MW)"] > 10:
            return "🟢 Discharging"
        else:
            return "⚪ Idle"

    battery_table["Status"] = battery_table.apply(
        battery_status, axis=1
    )

    st.dataframe(
        battery_table,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Solar curtailed (MW)": st.column_config.ProgressColumn(
                "Solar curtailed (MW)",
                min_value=0, max_value=6600,
                format="%.0f MW"
            ),
            "Battery charging (MW)": st.column_config.ProgressColumn(
                "Battery charging (MW)",
                min_value=0, max_value=1096,
                format="%.0f MW"
            ),
            "Battery discharge (MW)": st.column_config.ProgressColumn(
                "Battery discharge (MW)",
                min_value=0, max_value=1096,
                format="%.0f MW"
            ),
            "SOC (MWh)": st.column_config.ProgressColumn(
                "SOC (MWh)",
                min_value=0, max_value=4380,
                format="%.0f MWh"
            ),
            "Cost saving ($)": st.column_config.NumberColumn(
                "Cost saving ($)",
                format="$%.0f"
            ),
        }
    )

    # ── ARBITRAGE CARDS ───────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    arb1, arb2, arb3 = st.columns(3)

    gross_arbitrage = (
        total_discharged * 90
    ) - (total_charged * 35)

    with arb1:
        st.markdown(f"""
        <div style="background:#e3f2fd; border-radius:8px;
                    padding:16px; border:1px solid #90caf9;">
            <div style="font-weight:600; color:#1565c0;
                        margin-bottom:8px;">
                🔵 Charging Phase (00:00–06:00)
            </div>
            <div style="font-size:12px; color:#1a237e;">
                Battery absorbs
                <b>{total_charged:,.0f} MWh</b>
                overnight at low coal prices (~$35/MWh).
                <br><br>
                Cost to charge =
                ${total_charged * 35 / 1e3:,.0f}K
            </div>
        </div>
        """, unsafe_allow_html=True)

    with arb2:
        st.markdown(f"""
        <div style="background:#e8f5e9; border-radius:8px;
                    padding:16px; border:1px solid #a5d6a7;">
            <div style="font-weight:600; color:#2e7d32;
                        margin-bottom:8px;">
                🟢 Discharging Phase (17:00–20:00)
            </div>
            <div style="font-size:12px; color:#1b5e20;">
                Battery injects
                <b>{total_discharged:,.0f} MWh</b>
                at evening peak replacing gas (~$90/MWh).
                <br><br>
                Value of discharge =
                ${total_discharged * 90 / 1e3:,.0f}K
            </div>
        </div>
        """, unsafe_allow_html=True)

    with arb3:
        st.markdown(f"""
        <div style="background:#fff8e1; border-radius:8px;
                    padding:16px; border:1px solid #ffe082;">
            <div style="font-weight:600; color:#e65100;
                        margin-bottom:8px;">
                💰 Arbitrage Revenue
            </div>
            <div style="font-size:12px; color:#bf360c;">
                Gross arbitrage =
                <b>${gross_arbitrage/1e3:,.0f}K</b>
                <br>
                Efficiency loss (8%) =
                ${efficiency_loss * 35 / 1e3:,.0f}K
                <br><br>
                System cost saving =
                <b>${cost_saving/1e3:,.1f}K</b>
            </div>
        </div>
        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
# TAB 3 — CAPACITY EXPANSION (coming Step 7)
# ══════════════════════════════════════════════════════════════════

with tab3:
    st.header("🏗️ Module 3: Capacity Expansion Planning")
    st.markdown(
        "**Future NSW scenario** — Eraring + Bayswater retired "
        "&nbsp;|&nbsp; Demand +20% from electrification "
        "&nbsp;|&nbsp; Least-cost investment plan "
        "&nbsp;|&nbsp; Source: AEMO ISP 2024"
    )

    # ── SCENARIO CARDS ────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    sc1, sc2, sc3 = st.columns(3)

    with sc1:
        st.markdown("""
        <div style="background:#fff5f5; border-radius:8px;
                    padding:16px; border-left:4px solid #e53935;">
            <div style="font-weight:600; color:#e53935;
                        margin-bottom:8px;">🏭 Coal Retiring</div>
            <div style="font-size:12px; color:#444;">
                <b>Eraring:</b> 2,880 MW retired<br>
                <b>Bayswater:</b> 2,640 MW retired<br>
                <b>Total removed:</b> 5,520 MW<br><br>
                Largest coal closure in Australian history
            </div>
        </div>""", unsafe_allow_html=True)

    with sc2:
        st.markdown("""
        <div style="background:#fff8e1; border-radius:8px;
                    padding:16px; border-left:4px solid #ff9800;">
            <div style="font-weight:600; color:#e65100;
                        margin-bottom:8px;">📈 Demand Growing</div>
            <div style="font-size:12px; color:#444;">
                <b>Today:</b> 10,100 MW peak<br>
                <b>Future:</b> 12,120 MW peak<br>
                <b>Growth:</b> +20% (+2,020 MW)<br><br>
                Driven by EVs and heat pumps
            </div>
        </div>""", unsafe_allow_html=True)

    with sc3:
        st.markdown(f"""
        <div style="background:#e8f5e9; border-radius:8px;
                    padding:16px; border-left:4px solid #66bb6a;">
            <div style="font-weight:600; color:#2e7d32;
                        margin-bottom:8px;">⚡ Investment Gap</div>
            <div style="font-size:12px; color:#444;">
                <b>Existing capacity:</b> 8,526 MW<br>
                <b>Future peak:</b> 12,120 MW<br>
                <b>Gap to fill:</b> 3,594 MW<br><br>
                Optimizer finds cheapest solution
            </div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── KPI CARDS ─────────────────────────────────────────────────
    e1,e2,e3,e4,e5,e6 = st.columns(6)

    with e1:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">☀️ New solar</div>
            <div class="kpi-value">{results_exp['new_solar_mw']:,.0f}</div>
            <div class="kpi-sub">MW built</div>
        </div>""", unsafe_allow_html=True)

    with e2:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">💨 New wind</div>
            <div class="kpi-value">{results_exp['new_wind_mw']:,.0f}</div>
            <div class="kpi-sub">MW built</div>
        </div>""", unsafe_allow_html=True)

    with e3:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">🔋 New battery</div>
            <div class="kpi-value">{results_exp['new_battery_mw']:,.0f}</div>
            <div class="kpi-sub">MW / {results_exp['new_battery_mwh']:,.0f} MWh</div>
        </div>""", unsafe_allow_html=True)

    with e4:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">🔌 Line upgrade</div>
            <div class="kpi-value">{results_exp['line_upgrade_mw']:,.0f}</div>
            <div class="kpi-sub">MW added to Orana line</div>
        </div>""", unsafe_allow_html=True)

    with e5:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">🌿 Renewable share</div>
            <div class="kpi-value">{results_exp['renewable_pct']:.1f}%</div>
            <div class="kpi-sub">future scenario</div>
        </div>""", unsafe_allow_html=True)

    with e6:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">💰 Total investment</div>
            <div class="kpi-value">${results_exp['total_capex']/1e9:.2f}B</div>
            <div class="kpi-sub">annual capex</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── CHART 1: WHAT TO BUILD ────────────────────────────────────
    st.markdown(
        '<p class="section-title">🏗️ New Build Decisions (MW)</p>',
        unsafe_allow_html=True
    )

    build_items = [
        ("New Solar",    results_exp["new_solar_mw"],    "#ffd600"),
        ("New Wind",     results_exp["new_wind_mw"],     "#66bb6a"),
        ("New Battery",  results_exp["new_battery_mw"],  "#ff9800"),
        ("New Gas OCGT", results_exp["new_gas_mw"],      "#f4a261"),
        ("Line Upgrade", results_exp["line_upgrade_mw"], "#2196f3"),
    ]

    fig_build = go.Figure(go.Bar(
        x=[b[0] for b in build_items],
        y=[b[1] for b in build_items],
        marker_color=[b[2] for b in build_items],
        text=[f"{b[1]:,.0f} MW" for b in build_items],
        textposition="outside",
        hovertemplate=(
            "<b>%{x}</b><br>"
            "%{y:,.0f} MW<extra></extra>"
        )
    ))
    fig_build.update_layout(
        height=320,
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=50,r=20,t=40,b=40),
        showlegend=False,
        xaxis=dict(showgrid=False, tickfont=dict(size=11)),
        yaxis=dict(
            title="MW", gridcolor="#f0f0f0",
            tickfont=dict(size=10), tickformat=","
        )
    )
    st.plotly_chart(fig_build, use_container_width=True)

    # ── CHART 2: INVESTMENT BREAKDOWN ─────────────────────────────
    col_inv1, col_inv2 = st.columns(2)

    with col_inv1:
        st.markdown(
            '<p class="section-title">💰 Investment Breakdown</p>',
            unsafe_allow_html=True
        )
        inv_map = [
            ("Solar",        results_exp["solar_capex"],        "#ffd600"),
            ("Wind",         results_exp["wind_capex"],         "#66bb6a"),
            ("Battery",      results_exp["battery_capex"],      "#ff9800"),
            ("Gas OCGT",     results_exp["gas_capex"],          "#f4a261"),
            ("Transmission", results_exp["transmission_capex"], "#2196f3"),
        ]
        inv_labels = [i[0] for i in inv_map if i[1] > 0]
        inv_values = [i[1] for i in inv_map if i[1] > 0]
        inv_colors = [i[2] for i in inv_map if i[1] > 0]

        fig_inv = go.Figure(go.Pie(
            labels=inv_labels,
            values=inv_values,
            hole=0.55,
            marker=dict(
                colors=inv_colors,
                line=dict(color="white", width=2)
            ),
            textinfo="label+percent",
            textfont=dict(size=11),
            hovertemplate=(
                "<b>%{label}</b><br>"
                "$%{value:,.0f}<br>"
                "%{percent}<extra></extra>"
            )
        ))
        fig_inv.update_layout(
            height=280, paper_bgcolor="white",
            margin=dict(l=10,r=10,t=20,b=10),
            showlegend=False,
            annotations=[dict(
                text=(
                    f"<b>${results_exp['total_capex']/1e9:.1f}B</b>"
                    f"<br>total"
                ),
                x=0.5, y=0.5,
                font=dict(size=13, color="#1a1a2e"),
                showarrow=False
            )]
        )
        st.plotly_chart(fig_inv, use_container_width=True)

    with col_inv2:
        st.markdown(
            '<p class="section-title">📋 Investment Detail</p>',
            unsafe_allow_html=True
        )
        inv_df = pd.DataFrame([
            {
                "Technology":   "New Solar",
                "Capacity":     f"{results_exp['new_solar_mw']:,.0f} MW",
                "Unit Cost":    "$96,000/MW/yr",
                "Annual Capex": f"${results_exp['solar_capex']/1e6:.0f}M",
            },
            {
                "Technology":   "New Wind",
                "Capacity":     f"{results_exp['new_wind_mw']:,.0f} MW",
                "Unit Cost":    "$170,000/MW/yr",
                "Annual Capex": f"${results_exp['wind_capex']/1e6:.0f}M",
            },
            {
                "Technology":   "New Battery",
                "Capacity":     f"{results_exp['new_battery_mw']:,.0f} MW",
                "Unit Cost":    "$660,000/MW/yr",
                "Annual Capex": f"${results_exp['battery_capex']/1e6:.0f}M",
            },
            {
                "Technology":   "New Gas OCGT",
                "Capacity":     f"{results_exp['new_gas_mw']:,.0f} MW",
                "Unit Cost":    "$80,000/MW/yr",
                "Annual Capex": f"${results_exp['gas_capex']/1e6:.0f}M",
            },
            {
                "Technology":   "Transmission",
                "Capacity":     f"{results_exp['line_upgrade_mw']:,.0f} MW",
                "Unit Cost":    "$150,000/MW/yr",
                "Annual Capex": f"${results_exp['transmission_capex']/1e6:.0f}M",
            },
            {
                "Technology":   "TOTAL",
                "Capacity":     "—",
                "Unit Cost":    "—",
                "Annual Capex": f"${results_exp['total_capex']/1e9:.2f}B",
            },
        ])
        st.dataframe(
            inv_df,
            use_container_width=True,
            hide_index=True
        )
        st.caption(
            "Source: AEMO ISP 2024 Input & Assumptions Workbook."
        )

    # ── CHART 3: FUTURE GENERATION STACK ─────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<p class="section-title">'
        '🔋 Future Generation Stack (MW)'
        '</p>',
        unsafe_allow_html=True
    )

    hour_labels_exp  = [f"{h.hour:02d}:00" for h in hours_exp]
    dispatch_exp_fuel = results_exp["dispatch_by_fuel"]

    fig_exp_stack = go.Figure()
    for fuel in ["solar","wind","hydro","coal","gas"]:
        if fuel in dispatch_exp_fuel.columns:
            if dispatch_exp_fuel[fuel].sum() > 0:
                fig_exp_stack.add_trace(go.Bar(
                    name=fuel.capitalize(),
                    x=hour_labels_exp,
                    y=dispatch_exp_fuel[fuel].round(0),
                    marker_color=COLOURS.get(fuel,"#aaaaaa"),
                    hovertemplate=(
                        f"<b>{fuel.capitalize()}</b><br>"
                        f"%{{x}}<br>%{{y:,.0f}} MW<extra></extra>"
                    )
                ))

    fig_exp_stack.add_trace(go.Scatter(
        name="Future demand",
        x=hour_labels_exp,
        y=demand_exp.values,
        mode="lines+markers",
        line=dict(color="#e53935", width=2.5, dash="dash"),
        marker=dict(size=4, color="#e53935"),
        hovertemplate=(
            "<b>Future demand</b><br>"
            "%{x}<br>%{y:,.0f} MW<extra></extra>"
        )
    ))
    fig_exp_stack.update_layout(
        barmode="stack", height=320,
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=50,r=20,t=20,b=60),
        legend=dict(
            orientation="h",y=-0.25,x=0,
            font=dict(size=11)
        ),
        xaxis=dict(showgrid=False, tickfont=dict(size=10)),
        yaxis=dict(
            title="MW", gridcolor="#f0f0f0",
            tickfont=dict(size=10), tickformat=","
        ),
        hovermode="x unified"
    )
    st.plotly_chart(fig_exp_stack, use_container_width=True)

    # ── CHART 4: TODAY VS FUTURE ──────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<p class="section-title">'
        '📊 Installed Capacity — Today vs Future'
        '</p>',
        unsafe_allow_html=True
    )

    today_cap = {
        "Coal":    6920,
        "Gas":     2148,
        "Hydro":   2356,
        "Solar":   6600,
        "Wind":    2822,
        "Battery": 0,
    }
    future_cap = {
        "Coal":    1400,
        "Gas":     2148 + results_exp["new_gas_mw"],
        "Hydro":   2356,
        "Solar":   results_exp["total_solar"],
        "Wind":    results_exp["total_wind"],
        "Battery": results_exp["new_battery_mw"],
    }

    tech_list   = list(today_cap.keys())
    today_vals  = [today_cap[t]  for t in tech_list]
    future_vals = [future_cap[t] for t in tech_list]
    bar_colors  = [
        "#4a4a4a","#f4a261","#2196f3",
        "#ffd600","#66bb6a","#ff9800"
    ]

    fig_compare = go.Figure()
    fig_compare.add_trace(go.Bar(
        name="Today",
        x=tech_list, y=today_vals,
        marker_color=bar_colors,
        opacity=0.5,
        hovertemplate=(
            "<b>Today — %{x}</b><br>"
            "%{y:,.0f} MW<extra></extra>"
        )
    ))
    fig_compare.add_trace(go.Bar(
        name="Future",
        x=tech_list, y=future_vals,
        marker_color=bar_colors,
        opacity=1.0,
        hovertemplate=(
            "<b>Future — %{x}</b><br>"
            "%{y:,.0f} MW<extra></extra>"
        )
    ))
    fig_compare.update_layout(
        barmode="group", height=320,
        plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=50,r=20,t=20,b=60),
        legend=dict(
            orientation="h",y=-0.2,x=0,
            font=dict(size=11)
        ),
        xaxis=dict(showgrid=False, tickfont=dict(size=11)),
        yaxis=dict(
            title="Installed Capacity (MW)",
            gridcolor="#f0f0f0",
            tickfont=dict(size=10), tickformat=","
        )
    )
    st.plotly_chart(fig_compare, use_container_width=True)

    # ── TRANSMISSION CARDS ────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    t1, t2, t3 = st.columns(3)

    with t1:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">🔌 Line before upgrade</div>
            <div class="kpi-value">{results_exp['line_original_mw']:,.0f} MW</div>
            <div class="kpi-sub">Sydney-Orana today</div>
        </div>""", unsafe_allow_html=True)

    with t2:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">🔌 Line after upgrade</div>
            <div class="kpi-value">{results_exp['line_upgraded_mw']:,.0f} MW</div>
            <div class="kpi-sub">Sydney-Orana future</div>
        </div>""", unsafe_allow_html=True)

    with t3:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">💰 Transmission cost</div>
            <div class="kpi-value">${results_exp['transmission_capex']/1e6:.0f}M</div>
            <div class="kpi-sub">annual capex</div>
        </div>""", unsafe_allow_html=True)

    # ── MODEL NOTE ────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.info(
        "📌 **Model note:** This is a 24-hour snapshot model "
        "using 17 January 2024 as a representative peak demand day. "
        "A production PLEXOS LT Plan would run across 8,760 hours "
        "capturing seasonal variation and multi-day wind droughts. "
        "Results show directional investment signals consistent with "
        "AEMO ISP 2024 findings. "
        "Capital costs sourced from AEMO ISP 2024 Input & "
        "Assumptions Workbook."
    )

    # ── PLEXOS MAPPING TABLE ──────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<p class="section-title">🔗 PyPSA → PLEXOS Mapping</p>',
        unsafe_allow_html=True
    )
    mapping_df = pd.DataFrame([
        {
            "PyPSA":         "p_nom_extendable=True",
            "PLEXOS":        "Generator → Expansion Enabled",
            "What it does":  "Allows optimizer to build new capacity"
        },
        {
            "PyPSA":         "p_nom_max=15000",
            "PLEXOS":        "Generator → Max Units to Build",
            "What it does":  "Caps maximum new capacity per technology"
        },
        {
            "PyPSA":         "capital_cost = annual/8760",
            "PLEXOS":        "Generator → Build Cost ($/MW)",
            "What it does":  "Annualised cost per MW of new capacity"
        },
        {
            "PyPSA":         "p_nom_opt",
            "PLEXOS":        "LT Plan Results → Installed Capacity",
            "What it does":  "MW the optimizer decided to build"
        },
        {
            "PyPSA":         "s_nom_extendable=True",
            "PLEXOS":        "Line → Expansion Enabled",
            "What it does":  "Allows transmission line upgrade"
        },
        {
            "PyPSA":         "Retired coal not added",
            "PLEXOS":        "Generator → Retirement Date",
            "What it does":  "Removes retiring units from model"
        },
    ])
    st.dataframe(
        mapping_df,
        use_container_width=True,
        hide_index=True
    )

    with st.expander("🔍 View raw expansion dispatch data"):
        st.dataframe(
            results_exp["dispatch"].round(1),
            use_container_width=True
        )

# ══════════════════════════════════════════════════════════════════
# TAB 4 — SCENARIO ANALYSIS (coming Step 8)
# ══════════════════════════════════════════════════════════════════
with tab4:
    st.header("🌍 Module 4: Scenario Analysis")
    st.markdown(
        "Policy scenario comparison — "
        "Base vs High Gas vs High Renewables"
        "&nbsp;|&nbsp; "
        "Mirrors PLEXOS ISP scenario methodology"
    )

    scenarios  = [base_sc, high_gas_sc, high_ren_sc]
    sc_names   = ["Base", "High Gas", "High Renewables"]
    sc_colors  = ["#4a4a4a", "#f4a261", "#66bb6a"]

    # ── SCENARIO DESCRIPTION CARDS ────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    sd1, sd2, sd3 = st.columns(3)

    desc_cards = [
        {
            "icon":  "🏭",
            "name":  "Base",
            "color": "#4a4a4a",
            "bg":    "#f5f5f5",
            "border":"#9e9e9e",
            "lines": [
                "Today's real NSW grid",
                "Coal: 6,920 MW running",
                "Solar: 6,600 MW",
                "Wind: 2,822 MW",
                "Demand: 10,100 MW peak",
            ]
        },
        {
            "icon":  "🔥",
            "name":  "High Gas",
            "color": "#e65100",
            "bg":    "#fff8e1",
            "border":"#f4a261",
            "lines": [
                "Coal replaced by gas",
                "Gas: 9,068 MW total",
                "Solar: 6,600 MW kept",
                "Wind: 2,822 MW kept",
                "Firm but high emissions",
            ]
        },
        {
            "icon":  "🌿",
            "name":  "High Renewables",
            "color": "#2e7d32",
            "bg":    "#e8f5e9",
            "border":"#66bb6a",
            "lines": [
                "Coal fully retired",
                "Solar: 12,308 MW",
                "Wind: 10,822 MW",
                "Battery: 696 MW",
                "Gas backup: 2,148 MW",
            ]
        },
        
    ]

    for col, card in zip([sd1,sd2,sd3], desc_cards):
        lines_html = "".join(
            f"• {line}<br>" for line in card["lines"]
        )
        with col:
            st.markdown(f"""
            <div style="background:{card['bg']};
                        border-radius:8px; padding:16px;
                        border-left:4px solid {card['border']};">
                <div style="font-weight:600;
                            color:{card['color']};
                            margin-bottom:8px;
                            font-size:13px;">
                    {card['icon']} {card['name']}
                </div>
                <div style="font-size:11px; color:#444;
                            line-height:1.8;">
                    {lines_html}
                </div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── METRICS COMPARISON ROW ────────────────────────────────────
    st.markdown(
        '<p class="section-title">📊 Key Metrics Comparison</p>',
        unsafe_allow_html=True
    )
    st.markdown("<br>", unsafe_allow_html=True)

    # Header row
    h0, h1, h2, h3, h4 = st.columns([2,1,1,1,1])
    with h0:
        st.markdown(
            "<div style='font-size:12px; color:#adb5bd; "
            "padding:4px 0;'>Metric</div>",
            unsafe_allow_html=True
        )
    for col, name, color in zip(
        [h1,h2,h3,h4], sc_names, sc_colors
    ):
        with col:
            st.markdown(
                f"<div style='font-size:12px; "
                f"font-weight:600; color:{color}; "
                f"text-align:center; padding:4px 0;'>"
                f"{name}</div>",
                unsafe_allow_html=True
            )

    st.markdown(
        "<hr style='margin:4px 0; border-color:#f0f0f0;'>",
        unsafe_allow_html=True
    )

    # Metric rows
    metrics = [
        ("💰 Total cost",        "total_cost",      "${:,.0f}"),
        ("⚡ Avg $/MWh",         "avg_price",       "${:.2f}"),
        ("🌿 Renewable %",       "renewable_pct",   "{:.1f}%"),
        ("💨 Emissions tCO2",    "emissions_tco2",  "{:,.0f}"),
        ("☀️ Solar curtailed",   "solar_curtailed", "{:,.0f} MWh"),
        ("💨 Wind curtailed",    "wind_curtailed",  "{:,.0f} MWh"),
    ]

    for label, key, fmt in metrics:
        m0,m1,m2,m3,m4 = st.columns([2,1,1,1,1])
        with m0:
            st.markdown(
                f"<div style='font-size:12px; "
                f"color:var(--color-text-secondary); "
                f"padding:6px 0;'>{label}</div>",
                unsafe_allow_html=True
            )
        for col, sc, color in zip(
            [m1,m2,m3,m4], scenarios, sc_colors
        ):
            try:
                formatted = fmt.format(sc[key])
            except Exception:
                formatted = str(sc[key])
            with col:
                st.markdown(
                    f"<div style='font-size:13px; "
                    f"font-weight:600; color:{color}; "
                    f"padding:6px 0; "
                    f"text-align:center;'>"
                    f"{formatted}</div>",
                    unsafe_allow_html=True
                )
        st.markdown(
            "<hr style='margin:2px 0; "
            "border-color:#f9f9f9;'>",
            unsafe_allow_html=True
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── CHART 1: TOTAL COST ───────────────────────────────────────
    st.markdown(
        '<p class="section-title">💰 Total System Cost ($)</p>',
        unsafe_allow_html=True
    )

    fig_cost_sc = go.Figure(go.Bar(
        x=sc_names,
        y=[sc["total_cost"] for sc in scenarios],
        marker_color=sc_colors,
        text=[
            f"${sc['total_cost']/1e6:.1f}M"
            for sc in scenarios
        ],
        textposition="outside",
        hovertemplate=(
            "<b>%{x}</b><br>"
            "$%{y:,.0f}<extra></extra>"
        )
    ))
    fig_cost_sc.update_layout(
        height=300,
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=50,r=20,t=40,b=40),
        showlegend=False,
        xaxis=dict(
            showgrid=False,
            tickfont=dict(size=12)
        ),
        yaxis=dict(
            title="Total cost ($)",
            gridcolor="#f0f0f0",
            tickfont=dict(size=10),
            tickformat=","
        )
    )
    st.plotly_chart(fig_cost_sc, use_container_width=True)
    st.caption(
        "High Gas costs more than Base because gas SRMC $90/MWh "
        "is higher than coal $38/MWh. "
        "High Renewables is cheapest — solar and wind have zero fuel cost."
    )

    # ── CHART 2: RENEWABLE SHARE + EMISSIONS ─────────────────────
    col_ren, col_emi = st.columns(2)

    with col_ren:
        st.markdown(
            '<p class="section-title">🌿 Renewable Share (%)</p>',
            unsafe_allow_html=True
        )
        fig_ren = go.Figure(go.Bar(
            x=sc_names,
            y=[sc["renewable_pct"] for sc in scenarios],
            marker_color=sc_colors,
            text=[
                f"{sc['renewable_pct']:.1f}%"
                for sc in scenarios
            ],
            textposition="outside",
            hovertemplate=(
                "<b>%{x}</b><br>"
                "%{y:.1f}%<extra></extra>"
            )
        ))
        fig_ren.update_layout(
            height=280,
            plot_bgcolor="white",
            paper_bgcolor="white",
            margin=dict(l=50,r=20,t=30,b=40),
            showlegend=False,
            xaxis=dict(
                showgrid=False,
                tickfont=dict(size=10)
            ),
            yaxis=dict(
                title="Renewable share (%)",
                gridcolor="#f0f0f0",
                tickfont=dict(size=10),
                range=[0,105]
            )
        )
        st.plotly_chart(fig_ren, use_container_width=True)

    with col_emi:
        st.markdown(
            '<p class="section-title">💨 CO2 Emissions (tCO2)</p>',
            unsafe_allow_html=True
        )
        fig_emi = go.Figure(go.Bar(
            x=sc_names,
            y=[sc["emissions_tco2"] for sc in scenarios],
            marker_color=sc_colors,
            text=[
                f"{sc['emissions_tco2']/1000:.1f}k"
                for sc in scenarios
            ],
            textposition="outside",
            hovertemplate=(
                "<b>%{x}</b><br>"
                "%{y:,.0f} tCO2<extra></extra>"
            )
        ))
        fig_emi.update_layout(
            height=280,
            plot_bgcolor="white",
            paper_bgcolor="white",
            margin=dict(l=50,r=20,t=30,b=40),
            showlegend=False,
            xaxis=dict(
                showgrid=False,
                tickfont=dict(size=10)
            ),
            yaxis=dict(
                title="CO2 Emissions (tCO2)",
                gridcolor="#f0f0f0",
                tickfont=dict(size=10),
                tickformat=","
            )
        )
        st.plotly_chart(fig_emi, use_container_width=True)

    # ── CHART 3: GENERATION STACKS ────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<p class="section-title">'
        '🔋 Generation Stack — All Scenarios'
        '</p>',
        unsafe_allow_html=True
    )

    gs1, gs2, gs3= st.columns(3)
    COLOURS_SC = {
        "coal":  "#4a4a4a",
        "gas":   "#f4a261",
        "hydro": "#2196f3",
        "solar": "#ffd600",
        "wind":  "#66bb6a",
        "slack": "#e53935",
    }

    for col, sc in zip([gs1,gs2,gs3], scenarios):
        hour_labels_sc = [
            f"{h.hour:02d}:00"
            for h in sc["hours"]
        ]
        fig_sc = go.Figure()

        for fuel in ["solar","wind","hydro","coal","gas"]:
            df = sc["dispatch_by_fuel"]
            if fuel in df.columns:
                if df[fuel].sum() > 0:
                    fig_sc.add_trace(go.Bar(
                        name=fuel.capitalize(),
                        x=hour_labels_sc,
                        y=df[fuel].round(0),
                        marker_color=COLOURS_SC[fuel],
                        showlegend=False,
                        hovertemplate=(
                            f"<b>{fuel.capitalize()}</b><br>"
                            f"%{{x}}<br>"
                            f"%{{y:,.0f}} MW<extra></extra>"
                        )
                    ))

        fig_sc.add_trace(go.Scatter(
            name="Demand",
            x=hour_labels_sc,
            y=sc["demand"].values,
            mode="lines",
            line=dict(
                color="#e53935", width=2, dash="dash"
            ),
            showlegend=False,
            hovertemplate=(
                "<b>Demand</b><br>"
                "%{x}<br>%{y:,.0f} MW<extra></extra>"
            )
        ))

        fig_sc.update_layout(
            title=dict(
                text=sc["scenario"],
                font=dict(size=11),
                x=0.5
            ),
            barmode="stack",
            height=250,
            plot_bgcolor="white",
            paper_bgcolor="white",
            margin=dict(l=30,r=5,t=35,b=50),
            showlegend=False,
            xaxis=dict(
                showgrid=False,
                tickfont=dict(size=7),
                tickvals=hour_labels_sc[::6],
                ticktext=hour_labels_sc[::6]
            ),
            yaxis=dict(
                gridcolor="#f0f0f0",
                tickfont=dict(size=7),
                tickformat=","
            )
        )
        with col:
            st.plotly_chart(
                fig_sc,
                use_container_width=True
            )

    # Shared legend for generation stacks
    leg1,leg2,leg3,leg4,leg5 = st.columns(5)
    legend_items = [
        ("Solar",  "#ffd600"),
        ("Wind",   "#66bb6a"),
        ("Hydro",  "#2196f3"),
        ("Coal",   "#4a4a4a"),
        ("Gas",    "#f4a261"),
    ]
    for col, (label, color) in zip(
        [leg1,leg2,leg3,leg4,leg5], legend_items
    ):
        with col:
            st.markdown(
                f"<div style='text-align:center; "
                f"font-size:11px; color:#666;'>"
                f"<span style='background:{color}; "
                f"padding:2px 8px; border-radius:3px; "
                f"color:white;'>{label}</span></div>",
                unsafe_allow_html=True
            )

    # ── CHART 4: HOURLY COST ──────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<p class="section-title">'
        '💰 Hourly System Cost — All Scenarios'
        '</p>',
        unsafe_allow_html=True
    )

    fig_hc = go.Figure()
    for sc, color in zip(scenarios, sc_colors):
        hour_labels_sc = [
            f"{h.hour:02d}:00"
            for h in sc["hours"]
        ]
        fig_hc.add_trace(go.Scatter(
            name=sc["scenario"],
            x=hour_labels_sc,
            y=sc["hourly_cost"].round(0).values,
            mode="lines+markers",
            line=dict(color=color, width=2.5),
            marker=dict(size=5),
            hovertemplate=(
                f"<b>{sc['scenario']}</b><br>"
                f"%{{x}}<br>"
                f"$%{{y:,.0f}}<extra></extra>"
            )
        ))

    fig_hc.update_layout(
        height=300,
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=60,r=20,t=20,b=60),
        legend=dict(
            orientation="h",y=-0.25,x=0,
            font=dict(size=11)
        ),
        xaxis=dict(
            title="Hour of day",
            showgrid=False,
            tickfont=dict(size=10)
        ),
        yaxis=dict(
            title="Hourly cost ($)",
            gridcolor="#f0f0f0",
            tickfont=dict(size=10),
            tickformat=","
        ),
        hovermode="x unified"
    )
    st.plotly_chart(fig_hc, use_container_width=True)
    st.caption(
        "High Gas most expensive every hour — gas runs 24/7 at $90/MWh. "
        "High Renewables cheapest during solar hours — zero fuel cost. "
        
    )

    # ── CHART 5: INSTALLED CAPACITY ───────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<p class="section-title">'
        '⚡ Installed Capacity by Technology (MW)'
        '</p>',
        unsafe_allow_html=True
    )

    tech_names = [
        "Solar","Wind","Coal","Gas","Hydro","Battery"
    ]
    fig_cap = go.Figure()

    for sc, sc_col in zip(scenarios, sc_colors):
        cap_vals = [
            sc["solar_mw"],
            sc["wind_mw"],
            sc["coal_mw"],
            sc["gas_mw"],
            2356,
            sc["battery_mw"],
        ]
        fig_cap.add_trace(go.Bar(
            name=sc["scenario"],
            x=tech_names,
            y=cap_vals,
            marker_color=sc_col,
            hovertemplate=(
                f"<b>{sc['scenario']} — %{{x}}</b><br>"
                f"%{{y:,.0f}} MW<extra></extra>"
            )
        ))

    fig_cap.update_layout(
        barmode="group",
        height=320,
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=50,r=20,t=20,b=60),
        legend=dict(
            orientation="h",y=-0.2,x=0,
            font=dict(size=11)
        ),
        xaxis=dict(
            showgrid=False,
            tickfont=dict(size=11)
        ),
        yaxis=dict(
            title="Installed Capacity (MW)",
            gridcolor="#f0f0f0",
            tickfont=dict(size=10),
            tickformat=","
        )
    )
    st.plotly_chart(fig_cap, use_container_width=True)

    # ── FULL SUMMARY TABLE ────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<p class="section-title">📋 Full Scenario Summary</p>',
        unsafe_allow_html=True
    )

    summary_df = pd.DataFrame([
        {
            "Metric":
                "Peak demand (MW)",
            "Base":
                f"{base_sc['peak_demand']:,.0f}",
            "High Gas":
                f"{high_gas_sc['peak_demand']:,.0f}",
            "High Renewables":
                f"{high_ren_sc['peak_demand']:,.0f}",
            
        },
        {
            "Metric":
                "Total system cost ($)",
            "Base":
                f"${base_sc['total_cost']:,.0f}",
            "High Gas":
                f"${high_gas_sc['total_cost']:,.0f}",
            "High Renewables":
                f"${high_ren_sc['total_cost']:,.0f}",
           
        },
        {
            "Metric":
                "Avg spot price ($/MWh)",
            "Base":
                f"${base_sc['avg_price']:.2f}",
            "High Gas":
                f"${high_gas_sc['avg_price']:.2f}",
            "High Renewables":
                f"${high_ren_sc['avg_price']:.2f}",
            
        },
        {
            "Metric":
                "Renewable share (%)",
            "Base":
                f"{base_sc['renewable_pct']:.1f}%",
            "High Gas":
                f"{high_gas_sc['renewable_pct']:.1f}%",
            "High Renewables":
                f"{high_ren_sc['renewable_pct']:.1f}%",
            
        },
        {
            "Metric":
                "CO2 emissions (tCO2)",
            "Base":
                f"{base_sc['emissions_tco2']:,.0f}",
            "High Gas":
                f"{high_gas_sc['emissions_tco2']:,.0f}",
            "High Renewables":
                f"{high_ren_sc['emissions_tco2']:,.0f}",
           
        },
        {
            "Metric":
                "Solar installed (MW)",
            "Base":
                f"{base_sc['solar_mw']:,.0f}",
            "High Gas":
                f"{high_gas_sc['solar_mw']:,.0f}",
            "High Renewables":
                f"{high_ren_sc['solar_mw']:,.0f}",
            
        },
        {
            "Metric":
                "Wind installed (MW)",
            "Base":
                f"{base_sc['wind_mw']:,.0f}",
            "High Gas":
                f"{high_gas_sc['wind_mw']:,.0f}",
            "High Renewables":
                f"{high_ren_sc['wind_mw']:,.0f}",
            
        },
        {
            "Metric":
                "Coal installed (MW)",
            "Base":
                f"{base_sc['coal_mw']:,.0f}",
            "High Gas":
                f"{high_gas_sc['coal_mw']:,.0f}",
            "High Renewables":
                f"{high_ren_sc['coal_mw']:,.0f}",
            
        },
        {
            "Metric":
                "Gas installed (MW)",
            "Base":
                f"{base_sc['gas_mw']:,.0f}",
            "High Gas":
                f"{high_gas_sc['gas_mw']:,.0f}",
            "High Renewables":
                f"{high_ren_sc['gas_mw']:,.0f}",
            
        },
        {
            "Metric":
                "Battery (MW)",
            "Base":
                f"{base_sc['battery_mw']:,.0f}",
            "High Gas":
                f"{high_gas_sc['battery_mw']:,.0f}",
            "High Renewables":
                f"{high_ren_sc['battery_mw']:,.0f}",
            
        },
        {
            "Metric":
                "Solar curtailed (MWh)",
            "Base":
                f"{base_sc['solar_curtailed']:,.0f}",
            "High Gas":
                f"{high_gas_sc['solar_curtailed']:,.0f}",
            "High Renewables":
                f"{high_ren_sc['solar_curtailed']:,.0f}",
            
        },
        {
            "Metric":
                "Wind curtailed (MWh)",
            "Base":
                f"{base_sc['wind_curtailed']:,.0f}",
            "High Gas":
                f"{high_gas_sc['wind_curtailed']:,.0f}",
            "High Renewables":
                f"{high_ren_sc['wind_curtailed']:,.0f}",
            
        },
    ])

    st.dataframe(
        summary_df,
        use_container_width=True,
        hide_index=True
    )

    # ── PLEXOS ISP MAPPING ────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<p class="section-title">'
        '🔗 PyPSA → PLEXOS ISP Mapping'
        '</p>',
        unsafe_allow_html=True
    )

    isp_df = pd.DataFrame([
        {
            "This Model":   "Base scenario",
            "PLEXOS / ISP": "ISP Current Policies scenario",
            "What changes": "No new policy — existing fleet only"
        },
        {
            "This Model":   "High Gas scenario",
            "PLEXOS / ISP": "Gas-led recovery pathway",
            "What changes": "Coal replaced by gas — firm but emissions"
        },
        {
            "This Model":   "High Renewables",
            "PLEXOS / ISP": "ISP Step Change scenario",
            "What changes": "Strong climate policy, high renewables"
        },
        
        {
            "This Model":   "Scenario parameters dict",
            "PLEXOS / ISP": "PLEXOS Scenario membership",
            "What changes": "Each scenario changes generator fleet"
        },
        {
            "This Model":   "Total cost comparison",
            "PLEXOS / ISP": "PLEXOS Net Market Benefit",
            "What changes": "Measures economic value of each scenario"
        },
        {
            "This Model":   "Emissions = coal×0.9 + gas×0.5",
            "PLEXOS / ISP": "PLEXOS Emissions report",
            "What changes": "tCO2 by fuel type per interval"
        },
    ])

    st.dataframe(
        isp_df,
        use_container_width=True,
        hide_index=True
    )

    # ── KEY INSIGHT BOX ───────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.info(
        "💡 **Key insight from this analysis:** "
        "Moving from Base to High Gas INCREASES costs and emissions "
        "— proving gas is not a transition solution. "
        "High Renewables is the CHEAPEST scenario despite large "
        "solar and wind investment — zero fuel cost dominates. "
        
        "cost increase from demand growth. "
        "This mirrors AEMO's ISP 2024 finding that the Step Change "
        "scenario — renewable-led transition — is the lowest cost "
        "pathway for Australia's energy system."
    )

    st.markdown("<br>", unsafe_allow_html=True)
    st.caption(
        "Emissions factors: Coal 0.9 tCO2/MWh, Gas 0.5 tCO2/MWh "
        "— consistent with AEMO dispatch emissions intensity estimates. "
        "Cost comparison shows operating cost only — "
        "capital costs modelled separately in Module 3."
    )
# ══════════════════════════════════════════════════════════════════
# TAB 5 — RAW DATA
# ══════════════════════════════════════════════════════════════════
with tab5:
    st.header("📋 Raw Data")

    st.subheader("Base Dispatch (MW) — No Battery")
    st.dataframe(
        results["dispatch"].round(1),
        use_container_width=True
    )

    st.subheader("Battery Operation (MW)")
    bat_raw = pd.DataFrame({
        "Charging (MW)":    battery_charge.round(1).values,
        "Discharging (MW)": battery_discharge.round(1).values,
        "SOC (MWh)":        battery_soc.round(1).values,
        "Net (MW)":         (
            battery_discharge -
            battery_charge
        ).round(1).values,
    }, index=hour_labels)
    bat_raw.index.name = "Hour"
    st.dataframe(bat_raw, use_container_width=True)

    st.subheader("Hourly Cost Comparison ($)")
    cost_raw = pd.DataFrame({
        "Without battery ($)": cost_base_hourly.round(0).values,
        "With battery ($)":    cost_battery_hourly.round(0).values,
        "Saving ($)":          cost_saving_hourly.round(0).values,
    }, index=hour_labels)
    cost_raw.index.name = "Hour"
    st.dataframe(cost_raw, use_container_width=True)


# ── FOOTER ─────────────────────────────────────────────────────────
st.markdown("""
<div class="footer">
    Data: AEMO NEM Registration & Exemption List (June 2026)
    &nbsp;|&nbsp;
    Model: PyPSA linear optimal dispatch
    &nbsp;|&nbsp;
    Solver: HiGHS
    &nbsp;|&nbsp;
    Built for NSW Energy Data & Analytics portfolio
</div>
""", unsafe_allow_html=True)