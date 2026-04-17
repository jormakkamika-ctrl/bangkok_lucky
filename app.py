import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import date
import time

# --- Page Config ---
st.set_page_config(page_title="US Market Screen", layout="wide")

# --- 1. Robust Ticker Loading (All Exchanges) ---
@st.cache_data(ttl=86400)
def load_all_us_tickers():
    try:
        # These two files together cover basically everything traded in the US
        nasdaq = pd.read_csv("https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt", sep='|')
        other = pd.read_csv("https://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt", sep='|')
        
        nasdaq = nasdaq[['Symbol', 'Security Name']].copy()
        nasdaq['Exchange'] = 'NASDAQ'
        
        other = other[['ACT Symbol', 'Security Name']].rename(columns={'ACT Symbol': 'Symbol'}).copy()
        other['Exchange'] = 'OTHER (NYSE/AMEX)'
        
        df = pd.concat([nasdaq, other], ignore_index=True).drop_duplicates(subset='Symbol')
        # Filter out warrants, test symbols, and rights
        df = df[~df['Symbol'].str.contains(r'\$|\.|TEST', na=False)]
        
        # Add a placeholder for Sector/Industry (see note below)
        df['Type'] = df['Security Name'].apply(lambda x: 'ETF' if ' ETF' in str(x) or 'Trust' in str(x) else 'Stock')
        return df
    except:
        return pd.DataFrame()

tickers_df = load_all_us_tickers()

# --- 2. Sidebar Filters ---
with st.sidebar:
    st.header("⚙️ Filter Criteria")
    start_date = st.date_input("Start Date", value=date(2025, 2, 18))
    end_date = st.date_input("End Date", value=date.today())
    
    st.divider()
    asset_type = st.multiselect("Asset Type", ["Stock", "ETF"], default=["Stock", "ETF"])
    min_price = st.number_input("Min Price at Start ($)", value=1.0)
    
    st.info("💡 Tip: To filter by Industry, use a specific screener tool. Fetching industry data for 10k+ stocks in real-time is too slow for a free app.")

# Filter list before running
filtered_df = tickers_df[tickers_df['Type'].isin(asset_type)]
tickers_to_scan = filtered_df["Symbol"].tolist()

# --- 3. Main Analysis ---
st.title("📈 All US Market Performance")
st.caption(f"Loaded **{len(tickers_df):,}** symbols across NASDAQ, NYSE, and AMEX.")

if st.button("🚀 Run Analysis", use_container_width=True):
    results = []
    progress_bar = st.progress(0)
    batch_size = 150 # Safe batch size
    
    for i in range(0, len(tickers_to_scan), batch_size):
        batch = tickers_to_scan[i:i + batch_size]
        try:
            # Fetch data with auto_adjust to fix the split issue (LICN/SNDK)
            data = yf.download(batch, start=start_date, end=end_date, auto_adjust=True, progress=False)
            
            if not data.empty and "Close" in data:
                closes = data["Close"]
                if isinstance(closes, pd.Series): closes = closes.to_frame()

                for ticker in closes.columns:
                    series = closes[ticker].dropna()
                    if len(series) >= 2:
                        # Ensure the stock existed at the start of your range (XDEF fix)
                        if (series.index[0].date() - start_date).days <= 7:
                            s_p = series.iloc[0]
                            e_p = series.iloc[-1]
                            
                            if s_p >= min_price:
                                pct = ((e_p / s_p) - 1) * 100
                                if -99.9 < pct < 5000:
                                    results.append({
                                        "Symbol": ticker,
                                        "% Change": pct,
                                        "Start Price": s_p,
                                        "End Price": e_p
                                    })
        except:
            pass
        
        progress_bar.progress(min(1.0, (i + batch_size) / len(tickers_to_scan)))
        time.sleep(0.1)

    if results:
        # CLEANING FOR DISPLAY (Fixes RuntimeError)
        final_df = pd.DataFrame(results)
        final_df = final_df.merge(tickers_df[['Symbol', 'Security Name', 'Type', 'Exchange']], on='Symbol', how='left')
        
        # Round and Format
        final_df["% Change"] = final_df["% Change"].round(2)
        final_df["Start Price"] = final_df["Start Price"].round(2)
        final_df["End Price"] = final_df["End Price"].round(2)
        
        # DISPLAY
        st.success("✅ Done!")
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🚀 Top 15 Gainers")
            st.dataframe(final_df.sort_values("% Change", ascending=False).head(15), hide_index=True)
        with c2:
            st.subheader("📉 Top 15 Losers")
            st.dataframe(final_df.sort_values("% Change", ascending=True).head(15), hide_index=True)
            
        st.subheader("📊 Full Results")
        # Final safety check for the dataframe display
        st.dataframe(final_df.reset_index(drop=True), use_container_width=True)
