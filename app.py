import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import date
import time

# --- 1. Page Config ---
st.set_page_config(page_title="Market Insights Pro", layout="wide", page_icon="📈")

# --- 2. Data Loading (Safe for Python 3.12) ---
@st.cache_data(ttl=86400)
def load_all_us_tickers():
    try:
        # Load official exchange lists
        nasdaq = pd.read_csv("https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt", sep='|')
        other = pd.read_csv("https://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt", sep='|')
        
        n_df = nasdaq[['Symbol', 'Security Name']].copy()
        o_df = other[['ACT Symbol', 'Security Name']].rename(columns={'ACT Symbol': 'Symbol'}).copy()
        
        full_df = pd.concat([n_df, o_df], ignore_index=True).drop_duplicates(subset='Symbol')
        # Clean out warrants/test symbols
        full_df = full_df[~full_df['Symbol'].str.contains(r'\$|\.|TEST', na=False)]
        
        # Identify ETFs vs Stocks
        full_df['Asset Type'] = full_df['Security Name'].apply(
            lambda x: 'ETF' if any(word in str(x) for word in [' ETF', 'Trust', 'Invesco', 'iShares', 'Vanguard']) else 'Stock'
        )
        return full_df
    except Exception as e:
        st.error(f"Failed to load ticker list: {e}")
        return pd.DataFrame()

# --- 3. Sidebar UI ---
with st.sidebar:
    st.header("⚙️ Configuration")
    start_date = st.date_input("Start Date", value=date(2025, 2, 18))
    end_date = st.date_input("End Date", value=date.today())
    
    st.divider()
    st.subheader("Filters")
    selected_types = st.multiselect("Asset Categories", ["Stock", "ETF"], default=["Stock", "ETF"])
    min_price = st.number_input("Min Price at Start ($)", value=1.0, step=0.5)
    
    st.divider()
    st.info("Batching is set to 150 for balance between speed and split-accuracy.")

# --- 4. Main App Logic ---
st.title("📊 US Market: Gainers & Losers")
st.caption(f"Analyzing all US Exchanges (NASDAQ, NYSE, AMEX). Using Python 3.12 Environment.")

# Initial Data Pull
with st.spinner("Fetching ticker master-list..."):
    tickers_df = load_all_us_tickers()

if not tickers_df.empty:
    # Filter the master list before scanning
    filtered_list = tickers_df[tickers_df['Asset Type'].isin(selected_types)]["Symbol"].tolist()
    
    if st.button("🚀 Run Analysis (All US Stocks & ETFs)", use_container_width=True):
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        batch_size = 150
        
        for i in range(0, len(filtered_list), batch_size):
            batch = filtered_list[i:i + batch_size]
            status_text.text(f"Processing batch {i//batch_size + 1} of {len(filtered_list)//batch_size + 1}...")
            
            try:
                # auto_adjust=True handles splits (Fixes LICN/SNDK errors)
                data = yf.download(batch, start=start_date, end=end_date, auto_adjust=True, progress=False)
                
                if not data.empty and "Close" in data:
                    closes = data["Close"]
                    if isinstance(closes, pd.Series): closes = closes.to_frame()

                    for ticker in closes.columns:
    # Get price and volume for this specific ticker
    price_series = closes[ticker].dropna()
    
    if len(price_series) >= 5: # Require at least 5 days of data for stability
        actual_start_date = price_series.index[0].date()
        
        # 1. THE INCEPTION GUARD: Must exist within 3 days of your start date
        if abs((actual_start_date - start_date).days) <= 3:
            s_p = float(price_series.iloc[0])
            e_p = float(price_series.iloc[-1])
            
            if s_p >= min_price:
                pct = ((e_p / s_p) - 1) * 100
                
                # 2. THE GLITCH GUARD: 
                # If a stock 'drops' 99% but the start price was huge ($2800), 
                # or if a stock 'gains' 5000%, it's almost certainly a split/data error.
                if -95.0 < pct < 1000.0:
                    
                    # 3. THE WARRANT/TEST GUARD:
                    sec_name = str(tickers_df[tickers_df['Symbol'] == ticker]['Security Name'].values[0]).upper()
                    if any(bad in sec_name for bad in ['WARRANT', 'RIGHTS', 'TEST', 'UNIT']):
                        continue
                        
                    results.append({
                        "Symbol": str(ticker),
                        "Pct_Change": round(pct, 2),
                        "Price_Start": round(s_p, 2),
                        "Price_End": round(e_p, 2)
                    })
            except:
                continue # Skip failing batches
            
            progress_bar.progress(min(1.0, (i + batch_size) / len(filtered_list)))
        
        status_text.empty()
        
        if results:
            # Create Final Table
            final_df = pd.DataFrame(results).merge(tickers_df, on='Symbol', how='left')
            
            st.success(f"Successfully verified {len(final_df)} symbols.")
            st.balloons()
            
            # --- Layout Display ---
            col1, col2 = st.columns(2)
            
            # Formatting config for tables
            table_config = {
                "Pct_Change": st.column_config.NumberColumn("Performance", format="%.2f%%"),
                "Price_Start": st.column_config.NumberColumn("Start ($)"),
                "Price_End": st.column_config.NumberColumn("End ($)")
            }

            with col1:
                st.subheader("🚀 Top 15 Gainers")
                st.dataframe(
                    final_df.sort_values("Pct_Change", ascending=False).head(15), 
                    hide_index=True, column_config=table_config, use_container_width=True
                )
            
            with col2:
                st.subheader("📉 Top 15 Losers")
                st.dataframe(
                    final_df.sort_values("Pct_Change", ascending=True).head(15), 
                    hide_index=True, column_config=table_config, use_container_width=True
                )
            
            st.divider()
            st.subheader("📊 Full Sortable Dataset")
            st.dataframe(final_df, use_container_width=True, column_config=table_config)
            
            # Download Button
            csv = final_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Report (CSV)", data=csv, file_name=f"market_movers_{start_date}.csv")
        else:
            st.warning("No data found for the selected filters.")
else:
    st.error("The ticker database is currently offline. Please refresh.")
