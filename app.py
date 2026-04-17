import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import date
import time

# --- 1. Page Config ---
st.set_page_config(page_title="Market Insights Pro", layout="wide", page_icon="📈")

# --- 2. Data Loading (Official Exchange Lists) ---
@st.cache_data(ttl=86400)
def load_all_us_tickers():
    try:
        # Puts together every ticker on NASDAQ, NYSE, and AMEX
        nasdaq = pd.read_csv("https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt", sep='|')
        other = pd.read_csv("https://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt", sep='|')
        
        n_df = nasdaq[['Symbol', 'Security Name']].copy()
        o_df = other[['ACT Symbol', 'Security Name']].rename(columns={'ACT Symbol': 'Symbol'}).copy()
        
        full_df = pd.concat([n_df, o_df], ignore_index=True).drop_duplicates(subset='Symbol')
        # Filter out junk symbols like 'AAPL$' or 'TEST'
        full_df = full_df[~full_df['Symbol'].str.contains(r'\$|\.|TEST', na=False)]
        
        # Simple Logic to identify ETFs
        full_df['Asset Type'] = full_df['Security Name'].apply(
            lambda x: 'ETF' if any(word in str(x) for word in [' ETF', 'Trust', 'Invesco', 'iShares', 'Vanguard']) else 'Stock'
        )
        return full_df
    except:
        return pd.DataFrame()

# --- 3. Sidebar Configuration ---
with st.sidebar:
    st.header("⚙️ Settings")
    start_date = st.date_input("Start Date", value=date(2025, 2, 18))
    end_date = st.date_input("End Date", value=date.today())
    
    st.divider()
    selected_types = st.multiselect("Asset Type", ["Stock", "ETF"], default=["Stock", "ETF"])
    min_price = st.number_input("Min Price ($) at Start", value=5.0)
    
    st.divider()
    st.caption("Using Python 3.12 Optimized Engine")

# --- 4. Main App Logic ---
st.title("📊 US Market: Top Performance")

# Use a standard text call (Safe for 3.12/3.14)
status_load = st.text("📡 Syncing with Exchange Servers...")
tickers_df = load_all_us_tickers()
status_load.empty()

if not tickers_df.empty:
    # Pre-filter symbols to save processing time
    all_symbols = tickers_df[tickers_df['Asset Type'].isin(selected_types)]["Symbol"].tolist()
    
    if st.button("🚀 Run Market Analysis", use_container_width=True):
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        batch_size = 150 
        
        for i in range(0, len(all_symbols), batch_size):
            batch = all_symbols[i:i + batch_size]
            status_text.text(f"Scanning symbols {i} to {min(i+batch_size, len(all_symbols))}...")
            
            try:
                # auto_adjust=True fixes the LICN/SNDK split errors
                data = yf.download(batch, start=start_date, end=end_date, auto_adjust=True, progress=False)
                
                if not data.empty and "Close" in data:
                    closes = data["Close"]
                    if isinstance(closes, pd.Series): closes = closes.to_frame()

                    for ticker in closes.columns:
                        price_series = closes[ticker].dropna()
                        
                        # ARMOR 1: Stability Check (Minimum 5 days of data)
                        if len(price_series) >= 5:
                            actual_start = price_series.index[0].date()
                            
                            # ARMOR 2: The XDEF Fix (Inception Guard)
                            # Only count stocks that actually traded within 3 days of your Start Date
                            if abs((actual_start - start_date).days) <= 3:
                                s_p = float(price_series.iloc[0])
                                e_p = float(price_series.iloc[-1])
                                
                                if s_p >= min_price:
                                    pct = ((e_p / s_p) - 1) * 100
                                    
                                    # ARMOR 3: The Glitch Guard (Floor & Ceiling)
                                    # Removes most phantom splits/data errors
                                    if -95.0 < pct < 2500:
                                        
                                        # ARMOR 4: The Warrant/Unit Guard
                                        name_lookup = tickers_df[tickers_df['Symbol'] == ticker]['Security Name'].values
                                        sec_name = str(name_lookup[0]).upper() if len(name_lookup) > 0 else "UNKNOWN"
                                        
                                        if any(bad in sec_name for bad in ['WARRANT', 'RIGHTS', 'TEST', 'UNIT', 'WT']):
                                            continue
                                            
                                        results.append({
                                            "Symbol": str(ticker),
                                            "Performance": round(pct, 2),
                                            "Price_Start": round(s_p, 2),
                                            "Price_End": round(e_p, 2),
                                            "Security Name": sec_name
                                        })
            except:
                continue
            
            progress_bar.progress(min(1.0, (i + batch_size) / len(all_symbols)))
        
        status_text.empty()
        
        if results:
            final_df = pd.DataFrame(results)
            st.success(f"Verified {len(final_df)} symbols successfully.")
            
            # --- Results Display ---
            col1, col2 = st.columns(2)
            
            # Table configuration for a professional look
            table_config = {
                "Performance": st.column_config.NumberColumn("Change %", format="%.2f%%"),
                "Price_Start": st.column_config.NumberColumn("Start ($)"),
                "Price_End": st.column_config.NumberColumn("End ($)")
            }

            with col1:
                st.subheader("🚀 Top 15 Gainers")
                st.dataframe(final_df.sort_values("Performance", ascending=False).head(15), 
                             hide_index=True, column_config=table_config, use_container_width=True)
            
            with col2:
                st.subheader("📉 Top 15 Losers")
                st.dataframe(final_df.sort_values("Performance", ascending=True).head(15), 
                             hide_index=True, column_config=table_config, use_container_width=True)
            
            st.divider()
            st.subheader("📊 Full Market Table")
            st.dataframe(final_df, use_container_width=True, column_config=table_config)
            
            # Allow friends to download the clean data
            csv = final_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Data", data=csv, file_name=f"market_report_{start_date}.csv")
        else:
            st.warning("No data found. Try lowering the 'Min Price' or adjusting the date range.")
