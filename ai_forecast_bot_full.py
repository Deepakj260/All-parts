
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from dateutil.relativedelta import relativedelta

st.set_page_config(page_title="AI Forecast Bot", layout="wide")
st.title("📈 AI Forecast Bot with CAGR-based Prediction (Seasonal Adjusted)")

# File upload
hist_file = st.file_uploader("📄 Upload 2-Year History File (Firm + Lifting)", type="xlsx")
if hist_file:
    df = pd.read_excel(hist_file, sheet_name='Sheet1')
    df['Month'] = pd.to_datetime(df['Month'])
    df.sort_values(['Part No', 'Month'], inplace=True)

    df['Fiscal_Year'] = df['Month'].apply(lambda d: f"{d.year}-{d.year+1}" if d.month >= 4 else f"{d.year-1}-{d.year}")
    df['Month_Num'] = df['Month'].dt.month

    # Compute month-wise CAGR between 2023–2025
    seasonal = df[df['Fiscal_Year'].isin(['2023-2024', '2024-2025'])].groupby(['Part No', 'Fiscal_Year', 'Month_Num'])['Actual Lifting Qty'].mean().unstack(level=1)

    def month_cagr(start, end):
        if pd.notnull(start) and pd.notnull(end) and start > 0:
            return (end / start) - 1
        return 0

    seasonal['MoM_CAGR'] = seasonal.apply(lambda row: month_cagr(row.get('2023-2024'), row.get('2024-2025')), axis=1)

    st.success("✅ History file loaded. Forecasting with seasonal adjustment up to March 2027.")

    forecast_months = pd.date_range(start='2025-04-01', end='2027-03-01', freq='MS')
    forecast_data = []

    # Identify parts with last 8 months actual lifting = 0
    last_date = df['Month'].max()
    recent_8_months = df[df['Month'] >= (last_date - pd.DateOffset(months=8))]
    parts_abs = recent_8_months.groupby('Part No')['Actual Lifting Qty'].sum()
    parts_abs = parts_abs[parts_abs == 0].index.tolist()

    for part_no, group in df.groupby('Part No'):
        if group.empty:
            continue

        supplying_country = group['Supplying country'].iloc[-1].lower()
        adj = 1.05
        if 'usa' in supplying_country:
            adj = 1.032
        elif 'eastern' in supplying_country:
            adj = 1.045

        latest = group[group['Fiscal_Year'] == '2024-2025'].set_index('Month_Num')
        avg_by_month = latest.groupby('Month_Num')['Actual Lifting Qty'].mean()

        for m in forecast_months:
            month_num = m.month
            base = avg_by_month.get(month_num, 0)
            seasonal_growth = seasonal.loc[(part_no, month_num)]['MoM_CAGR'] if (part_no, month_num) in seasonal.index else 0

            # Forecast value = base + (base * seasonal CAGR)
            forecast_val = base * (1 + seasonal_growth)

            # Absolute logic: if part is obsolete due to zero lifting in 8 months
            if part_no in parts_abs:
                forecast_val = 0

            # Override for obsolete part
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
