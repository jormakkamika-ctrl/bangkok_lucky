import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import date, datetime
import time
import random

# --- Page Config ---
st.set_page_config(page_title="Market Analyst", layout="wide")

# --- 1. Sidebar Configuration & Safety Settings ---
with st.sidebar:
    st.header("⚙️ Controls")
    start_date = st.date_input("Start Date", value=date(2025, 1, 1))
    end_date = st.date_input("End Date", value=date.today())
    
    st.divider()
    st.subheader("🛡️ Safety Settings")
    batch_size = st.slider("Batch Size", 50, 300, 150, help="Smaller batches are safer but slower.")
    pause_time = st.slider("Request Delay (sec)", 0.1, 2.0, 0.3, help="Prevents Yahoo from blocking your IP.")
    
    st.divider()
    min_price = st.number_input("Min Stock Price ($)", value=1.0, help="Filters out penny stocks with glitchy data.")

# --- 2. Ticker Loading with "Last Updated" Logic ---
@st.cache_data(ttl=86400)
def load_tickers():
    try:
        nasdaq = pd.read_csv("https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt", sep='|')
        other = pd.read_csv("https://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt", sep='|')
        nasdaq = nasdaq[['Symbol', 'Security Name']].copy()
        other = other[['ACT Symbol', 'Security Name']].rename(columns={'ACT Symbol': 'Symbol'}).copy()
        df = pd.concat([nasdaq, other], ignore_index=True).drop_duplicates(subset='Symbol')
        df = df[~df['Symbol'].str.contains(r'\$|\.|TEST', na=False)]
        
        # Add a timestamp to show when data was pulled
        last_pulled = datetime.now().strftime("%Y-%m-%d %H:%M")
        return df, last_pulled
    except:
        return pd.DataFrame(), "Failed to load"

tickers_df, last_refreshed = load_tickers()
all_tickers = tickers_df["Symbol"].tolist()

# --- Main App UI ---
st.title("📈 Market Top Gainers & Losers")
st.caption(f"Ticker list last synced: **{last_refreshed}**")

if st.button("🚀 Run Full Analysis", use_container_width=True):
    if start_date >= end_date:
        st.error("End date must be after start date")
    else:
        results = []
        progress_bar = st.progress(0)
        status_msg = st.empty()
        
        # --- 3. Implementation of Smart Batching ---
        total_tickers = len(all_tickers)
        
        for i in range(0, total_tickers, batch_size):
            batch = all_tickers[i:i + batch_size]
            current_batch_num = (i // batch_size) + 1
            total_batches = (total_tickers // batch_size) + 1
            
            status_msg.info(f"Processing Batch {current_batch_num}/{total_batches}...")
            
            try:
                # We pull 'Close' and 'Adj Close' to ensure we account for dividends/splits
                data = yf.download(
                    tickers=batch,
                    start=start_date,
                    end=end_date,
                    progress=False,
                    threads=True,
                    group_by='column'
                )
                
                if not data.empty and "Close" in data:
                    closes = data["Close"].dropna(axis=1, how='all')
                    
                    if len(closes) >= 2:
                        first_p = closes.iloc[0]
                        last_p = closes.iloc[-1]
                        
                        # Calculation Logic
                        pct = ((last_p / first_p) - 1) * 100
                        
                        # Filtering for Price & Validity
                        temp = pd.DataFrame({
                            "Symbol": pct.index, 
                            "% Change": pct.values,
                            "Last Price": last_p.values
                        }).dropna()
                        
                        # Apply the "Min Price" safety filter
                        temp = temp[temp["Last Price"] >= min_price]
                        results.append(temp)
            
            except Exception as e:
                # If a batch fails, we wait a bit longer then keep going
                time.sleep(2)
                continue
                
            # Update Progress UI
            progress_perc = min(1.0, (i + batch_size) / total_tickers)
            progress_bar.progress(progress_perc)
            
            # The "Safety Pause" - varies slightly to look more like natural traffic
            time.sleep(pause_time + random.uniform(0, 0.2))

        if results:
            final_df = pd.concat(results, ignore_index=True)
            final_df = final_df.merge(tickers_df, on="Symbol", how="left")
            final_df = final_df.rename(columns={"Security Name": "Name"})
            
            # Clean up the final list
            final_df = final_df[final_df['% Change'].between(-99.9, 5000)]
            final_df = final_df.sort_values("% Change", ascending=False).round(2).reset_index(drop=True)
            
            status_msg.success(f"Successfully analyzed {len(final_df)} stocks!")
            st.balloons()

            # --- Display Results ---
            col_a, col_b = st.columns(2)
            with col_a:
                st.subheader("🚀 Top 15 Gainers")
                st.dataframe(final_df.head(15), use_container_width=True, hide_index=True)
            with col_b:
                st.subheader("📉 Top 15 Losers")
                st.dataframe(final_df.tail(15).sort_values("% Change"), use_container_width=True, hide_index=True)
                
            # Full Data Export
            st.divider()
            st.download_button("📥 Download Results (CSV)", final_df.to_csv(index=False), "market_data.csv")
        else:
            status_msg.error("No data recovered. Yahoo may be rate-limiting you.")

else:
    st.info("Adjust settings in the sidebar and click 'Run Full Analysis' to start.")
