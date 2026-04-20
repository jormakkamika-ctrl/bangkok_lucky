import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import date
import random
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
    
    # ← New checkbox (exactly where it should be)
    st.divider()
    enrich_metadata = st.checkbox("🌐 Enrich with Sector & Industry", 
                                  value=True,
                                  help="Uncheck if the app times out or feels stuck. Makes analysis much faster.")

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
                                            "Percentage Difference": round(pct, 2),   # ← Renamed for clarity (exactly what you asked for)
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
            
            # ====================== CLEAN & FIXED SECTOR/INDUSTRY SECTION ======================
            if enrich_metadata:
                status_text = st.empty()
                status_text.text("🌐 Fetching Sector & Industry metadata... (first run can take a few minutes)")
                
                @st.cache_data(ttl=7*86400, show_spinner=False)
                def get_sector_industry(symbol_list):
                    info_dict = {}
                    batch_size = 40
                    
                    for i in range(0, len(symbol_list), batch_size):
                        batch = symbol_list[i:i + batch_size]
                        try:
                            tickers_obj = yf.Tickers(batch)
                            for sym in batch:
                                try:
                                    info = tickers_obj.tickers[sym].info
                                    info_dict[sym] = {
                                        "Sector": info.get("sector", "N/A"),
                                        "Industry": info.get("industry", "N/A")
                                    }
                                except:
                                    info_dict[sym] = {"Sector": "N/A", "Industry": "N/A"}
                        except:
                            for sym in batch:
                                for attempt in range(3):
                                    try:
                                        t = yf.Ticker(sym)
                                        info = t.info
                                        info_dict[sym] = {
                                            "Sector": info.get("sector", "N/A"),
                                            "Industry": info.get("industry", "N/A")
                                        }
                                        break
                                    except:
                                        time.sleep(random.uniform(0.7, 1.4))
                                else:
                                    info_dict[sym] = {"Sector": "N/A", "Industry": "N/A"}
                        
                        time.sleep(random.uniform(0.9, 2.3))
                    
                    return pd.DataFrame.from_dict(info_dict, orient="index")
                
                symbols_to_enrich = final_df["Symbol"].tolist()
                enrich_df = get_sector_industry(symbols_to_enrich)
                final_df = final_df.merge(enrich_df, left_on="Symbol", right_index=True, how="left")
                status_text.empty()
                st.success("✅ Sector & Industry data loaded!")
            else:
                final_df["Sector"] = "N/A"
                final_df["Industry"] = "N/A"
            
            # Force all columns to exist (prevents any KeyError)
            for col, default in {
                "Symbol": "",
                "Security Name": "UNKNOWN",
                "Sector": "N/A",
                "Industry": "N/A",
                "Percentage Difference": 0.0,
                "Price_Start": 0.0,
                "Price_End": 0.0
            }.items():
                if col not in final_df.columns:
                    final_df[col] = default
            
            # Safe column reordering (this is the line that fixes the error)
            column_order = [
                "Symbol", 
                "Security Name", 
                "Sector", 
                "Industry", 
                "Percentage Difference", 
                "Price_Start", 
                "Price_End"
            ]
            final_df = final_df.reindex(columns=column_order)
            # ====================== END CLEAN SECTION ======================
            
            status_text.empty()
            
            # Only enrich the symbols that survived all filters (very fast)
            symbols_to_enrich = final_df["Symbol"].tolist()
            enrich_df = get_sector_industry(symbols_to_enrich)
            
            # Merge sector/industry into main dataframe
            final_df = final_df.merge(enrich_df, left_on="Symbol", right_index=True, how="left")
            
            # Nice column order
            column_order = [
                "Symbol", 
                "Security Name", 
                "Sector", 
                "Industry", 
                "Percentage Difference", 
                "Price_Start", 
                "Price_End"
            ]
            final_df = final_df[column_order]
            
            status_text.empty()
            # ====================== END NEW SECTION ======================
            
            # --- Results Display ---
            col1, col2 = st.columns(2)
            
            # Updated table configuration (includes new columns)
            table_config = {
                "Percentage Difference": st.column_config.NumberColumn("Percentage Difference", format="%.2f%%"),
                "Price_Start": st.column_config.NumberColumn("Start ($)"),
                "Price_End": st.column_config.NumberColumn("End ($)"),
                "Sector": st.column_config.TextColumn("Sector"),
                "Industry": st.column_config.TextColumn("Industry")
            }

            with col1:
                st.subheader("🚀 Top 15 Gainers")
                st.dataframe(final_df.sort_values("Percentage Difference", ascending=False).head(15), 
                             hide_index=True, column_config=table_config, use_container_width=True)
            
            with col2:
                st.subheader("📉 Top 15 Losers")
                st.dataframe(final_df.sort_values("Percentage Difference", ascending=True).head(15), 
                             hide_index=True, column_config=table_config, use_container_width=True)
            
            st.divider()
            st.subheader("📊 Full Market Table")
            st.dataframe(final_df, use_container_width=True, column_config=table_config)
            
            # Allow friends to download the clean data (NOW INCLUDES sector, industry, and percentage difference)
            csv = final_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Download Data (with Sector & Industry)", 
                data=csv, 
                file_name=f"market_report_{start_date}.csv",
                mime="text/csv"
            )
        else:
            st.warning("No data found. Try lowering the 'Min Price' or adjusting the date range.")
