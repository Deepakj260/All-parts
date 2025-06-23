import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from dateutil.relativedelta import relativedelta

st.set_page_config(page_title="AI Forecast Bot", layout="wide")
st.title("📈 AI Forecast Bot with CAGR-based Prediction")

# File upload
hist_file = st.file_uploader("📄 Upload 2-Year History File (Firm + Lifting)", type="xlsx")
if hist_file:
    df = pd.read_excel(hist_file, sheet_name='Sheet1')
    df['Month'] = pd.to_datetime(df['Month'])
    df.sort_values(['Part No', 'Month'], inplace=True)

    df['Fiscal_Year'] = df['Month'].apply(lambda d: f"{d.year}-{d.year+1}" if d.month >= 4 else f"{d.year-1}-{d.year}")

    # Compute CAGR 2023–2025
    fy_totals = df[df['Fiscal_Year'].isin(['2023-2024', '2024-2025'])].groupby(['Part No', 'Fiscal_Year'])['Actual Lifting Qty'].sum().unstack()

    def calculate_cagr(start, end, years=1):
        if pd.notnull(start) and pd.notnull(end) and start > 0:
            return ((end / start) ** (1 / years)) - 1
        return None

    fy_totals['CAGR_2023_2025'] = fy_totals.apply(lambda row: calculate_cagr(row.get('2023-2024'), row.get('2024-2025')), axis=1)

    st.success("✅ History file loaded. Forecasting initiated up to March 2027.")

    # Forecast months
    forecast_months = pd.date_range(start='2025-04-01', end='2027-03-01', freq='MS')
    forecast_data = []

    for part_no, group in df.groupby('Part No'):
        cagr = fy_totals.loc[part_no]['CAGR_2023_2025'] if part_no in fy_totals.index else None
        if pd.isna(cagr):
            continue

        latest_year_data = group[group['Fiscal_Year'] == '2024-2025']
        if latest_year_data.empty:
            continue

        monthly_avg = latest_year_data['Actual Lifting Qty'].mean()
        if monthly_avg == 0 or pd.isna(monthly_avg):
            continue

        supplying_country = group['Supplying country'].iloc[-1].lower()
        if 'usa' in supplying_country:
            adj = 1.032
        elif 'eastern' in supplying_country:
            adj = 1.045
        else:
            adj = 1.05

        growth_rate = (1 + cagr) ** (1 / 12)
        forecast_val = monthly_avg

        for m in forecast_months:
            if part_no == 7500000831 and m >= pd.to_datetime('2025-07-01'):
                forecast_val = 0

            forecast_data.append({
                'Part No': part_no,
                'Month': m,
                'Forecasted Actual Lifting': round(forecast_val),
                'Inflation-adjusted Qty': round(forecast_val * adj)
            })
            forecast_val *= growth_rate

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
