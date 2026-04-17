import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import date
import time
import random

# --- Page Config ---
st.set_page_config(page_title="Market Analyst Pro", layout="wide", page_icon="📊")

# --- 1. Load Tickers (Cached) ---
@st.cache_data(ttl=86400)
def load_tickers():
    try:
        nasdaq = pd.read_csv("https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt", sep='|')
        other = pd.read_csv("https://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt", sep='|')
        nasdaq = nasdaq[['Symbol', 'Security Name']].copy()
        other = other[['ACT Symbol', 'Security Name']].rename(columns={'ACT Symbol': 'Symbol'}).copy()
        df = pd.concat([nasdaq, other], ignore_index=True).drop_duplicates(subset='Symbol')
        # Clean out non-standard tickers
        df = df[~df['Symbol'].str.contains(r'\$|\.|TEST', na=False)]
        return df
    except:
        return pd.DataFrame()

tickers_df = load_tickers()
all_tickers = tickers_df["Symbol"].tolist()

# --- 2. Sidebar Controls ---
with st.sidebar:
    st.header("⚙️ Settings")
    start_date = st.date_input("Start Date", value=date(2025, 1, 1))
    end_date = st.date_input("End Date", value=date.today())
    
    st.divider()
    st.subheader("Filters")
    min_price = st.slider("Min Price ($)", 0.0, 20.0, 1.0)
    max_gain = st.number_input("Max Gain % (Cap)", value=1000, help="Filters out massive split-related errors.")
    
    st.divider()
    batch_size = st.select_slider("Speed/Accuracy Balance", options=[50, 100, 200, 500], value=100)
    st.caption("Lower batch size = Higher accuracy for splits.")

# --- 3. Main UI ---
st.title("📈 Market Top Gainers & Losers")
st.info(f"Ready to scan **{len(all_tickers):,}** US Symbols. Data is split-adjusted.")

if st.button("🚀 Run Analysis", use_container_width=True):
    if start_date >= end_date:
        st.error("End date must be after start date.")
    else:
        results = []
        progress_bar = st.progress(0)
        status = st.empty()
        
        for i in range(0, len(all_tickers), batch_size):
            batch = all_tickers[i:i + batch_size]
            status.text(f"Crunching batch {i//batch_size + 1}...")
            
            try:
                # auto_adjust=True fixes LICN 4500% gains by back-adjusting old prices
                data = yf.download(
                    tickers=batch,
                    start=start_date,
                    end=end_date,
                    auto_adjust=True, 
                    progress=False,
                    threads=True
                )
                
                if not data.empty and "Close" in data:
                    closes = data["Close"]
                    
                    # If only one ticker is returned, it's a Series; otherwise a DataFrame
                    if isinstance(closes, pd.Series):
                        # Handle single-ticker results if they happen
                        closes = closes.to_frame()

                    for ticker in closes.columns:
                        series = closes[ticker].dropna()
                        if len(series) >= 2:
                            start_p = series.iloc[0]
                            end_p = series.iloc[-1]
                            
                            # Standard % Change Math
                            pct = ((end_p / start_p) - 1) * 100
                            
                            # Filter out penny stocks and extreme outliers (likely data errors)
                            if start_p >= min_price and pct <= max_gain:
                                results.append({
                                    "Symbol": ticker,
                                    "% Change": pct,
                                    "Start Price": round(start_p, 2),
                                    "End Price": round(end_p, 2)
                                })
            except:
                continue
            
            progress_bar.progress(min(1.0, (i + batch_size) / len(all_tickers)))
            time.sleep(0.1)

        if results:
            final_df = pd.DataFrame(results)
            final_df = final_df.merge(tickers_df, on="Symbol", how="left")
            final_df = final_df.rename(columns={"Security Name": "Company Name"})
            final_df = final_df.sort_values("% Change", ascending=False).reset_index(drop=True)

            status.success(f"Verified {len(final_df)} symbols!")
            st.balloons()

            # --- Layout ---
            c1, c2 = st.columns(2)
            
            col_config = {
                "% Change": st.column_config.NumberColumn(format="%.2f%%"),
                "Start Price": st.column_config.NumberColumn(format="$%.2f"),
                "End Price": st.column_config.NumberColumn(format="$%.2f")
            }

            with c1:
                st.subheader("🔥 Top 15 Gainers")
                st.dataframe(final_df.head(15), use_container_width=True, hide_index=True, column_config=col_config)
            
            with c2:
                st.subheader("🧊 Top 15 Losers")
                st.dataframe(final_df.tail(15).sort_values("% Change"), use_container_width=True, hide_index=True, column_config=col_config)
            
            st.divider()
            st.subheader("📊 All Data")
            st.dataframe(final_df, use_container_width=True, column_config=col_config)
            
            csv = final_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Full Report", data=csv, file_name="market_report.csv")
        else:
            st.warning("No data found. Try reducing the 'Min Price' or expanding the date range.")
