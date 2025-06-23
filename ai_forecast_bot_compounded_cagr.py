
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from dateutil.relativedelta import relativedelta

st.set_page_config(page_title="AI Forecast Bot", layout="wide")
st.title("📈 AI Forecast Bot with Adjusted CAGR Forecasting")

hist_file = st.file_uploader("📄 Upload 2-Year History File (Firm + Lifting)", type="xlsx")
if hist_file:
    df = pd.read_excel(hist_file, sheet_name='Sheet1')
    df['Month'] = pd.to_datetime(df['Month'])
    df.sort_values(['Part No', 'Month'], inplace=True)

    df['Fiscal_Year'] = df['Month'].apply(lambda d: f"{d.year}-{d.year+1}" if d.month >= 4 else f"{d.year-1}-{d.year}")
    df['Month_Num'] = df['Month'].dt.month

    # Fiscal totals for CAGR calc
    annual_totals = df.groupby(['Part No', 'Fiscal_Year'])['Actual Lifting Qty'].sum().unstack()

    def compute_cagr(start, end, years=1):
        if pd.notnull(start) and pd.notnull(end) and start > 0:
            return (end / start)**(1 / years) - 1
        return 0

    cagr_df = pd.DataFrame()
    cagr_df['2023-2024'] = annual_totals.get('2023-2024', 0)
    cagr_df['2024-2025'] = annual_totals.get('2024-2025', 0)
    cagr_df['CAGR'] = cagr_df.apply(lambda row: compute_cagr(row['2023-2024'], row['2024-2025'], 1), axis=1)
    cagr_df['CAGR'] = cagr_df['CAGR'].apply(lambda x: min(x, 1.5))  # limit spike to 150%

    st.success("✅ Historical CAGR calculated. Proceeding with forecast up to March 2027.")

    forecast_months = pd.date_range(start='2025-04-01', end='2027-03-01', freq='MS')
    forecast_data = []

    last_date = df['Month'].max()
    recent_8 = df[df['Month'] >= (last_date - pd.DateOffset(months=8))]
    parts_abs = recent_8.groupby('Part No')['Actual Lifting Qty'].sum()
    parts_abs = parts_abs[parts_abs == 0].index.tolist()

    for part_no, group in df.groupby('Part No'):
        if group.empty:
            continue

        cagr = cagr_df.loc[part_no]['CAGR'] if part_no in cagr_df.index else 0

        supplying_country = group['Supplying country'].iloc[-1].lower()

        inflation_map = {'usa': 0.032, 'eastern': 0.045, 'default': 0.05}
        inf_rate = inflation_map.get('default')
        for key in inflation_map:
            if key in supplying_country:
                inf_rate = inflation_map[key]
                break

        # Apply inflation only if correlated with CAGR
        use_inflation = abs(cagr - inf_rate) <= 0.03
        adj = 1 + inf_rate if use_inflation else 1.0

        monthly_avg = group[(group['Fiscal_Year'] == '2024-2025')].groupby('Month_Num')['Actual Lifting Qty'].mean()

        for m_idx, m in enumerate(forecast_months):
            years_since_base = m.year - 2025
            month_num = m.month
            base = monthly_avg.get(month_num, 0)
            forecast_val = base * ((1 + cagr) ** years_since_base)

            if part_no in parts_abs:
                forecast_val = 0

            if part_no == 7500000831 and m >= pd.to_datetime('2025-07-01'):
                forecast_val = 0

            forecast_data.append({
                'Part No': part_no,
                'Month': m,
                'Forecasted Actual Lifting': round(forecast_val),
                'Inflation-adjusted Qty': round(forecast_val * adj)
            })

    forecast_df = pd.DataFrame(forecast_data)

    tab1, tab2 = st.tabs(["Single Part Forecast", "All Part Forecasts"])

    with tab1:
        part_list = sorted(forecast_df['Part No'].unique())
        part_selected = st.selectbox("🔎 Select a Part No to View Forecast", part_list)

        part_hist = df[df['Part No'] == part_selected][['Month', 'Actual Lifting Qty']].copy()
        part_fore = forecast_df[forecast_df['Part No'] == part_selected][['Month', 'Forecasted Actual Lifting', 'Inflation-adjusted Qty']].copy()

        st.subheader(f"📄 Forecast for Part No: {part_selected}")
        st.dataframe(part_fore)

        st.subheader("📊 Forecast Visualization")
        fig, ax = plt.subplots()
        ax.plot(part_hist['Month'], part_hist['Actual Lifting Qty'], label='Historical Actual')
        ax.plot(part_fore['Month'], part_fore['Forecasted Actual Lifting'], label='Forecasted Qty', linestyle='--')
        ax.plot(part_fore['Month'], part_fore['Inflation-adjusted Qty'], label='Inflation-adjusted Qty', linestyle=':')
        ax.set_xlabel("Month")
        ax.set_ylabel("Quantity")
        ax.legend()
        st.pyplot(fig)

        st.markdown("### 📅 Download Forecast")
        part_export = pd.concat([part_hist.rename(columns={'Actual Lifting Qty': 'Qty'}),
                                 part_fore.rename(columns={'Forecasted Actual Lifting': 'Qty'})])
        part_export = part_export.sort_values('Month')
        part_export['Part No'] = part_selected
        download = part_export[['Part No', 'Month', 'Qty']]
        st.download_button(
            "Download Excel",
            data=download.to_csv(index=False),
            file_name=f"Forecast_{part_selected}.csv",
            mime="text/csv"
        )

    with tab2:
        st.subheader("📆 Forecast for All Parts (2025–2027)")
        st.dataframe(forecast_df)

        all_download = forecast_df.sort_values(['Part No', 'Month'])
        st.download_button(
            label="📅 Download All Forecasts",
            data=all_download.to_csv(index=False),
            file_name="All_Parts_Forecast_2025_2027.csv",
            mime="text/csv"
        )
else:
    st.info("👆 Upload your historical firm and lifting data to get started.")
