import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import date
import time

# --- 1. Page Config ---
st.set_page_config(page_title="Market Insights 2026", layout="wide")

# --- 2. THE CACHE (Zero UI inside here to satisfy Python 3.14) ---
@st.cache_data(show_spinner=False)
def load_all_us_tickers():
    try:
        # Fetching official lists
        nasdaq = pd.read_csv("https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt", sep='|')
        other = pd.read_csv("https://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt", sep='|')
        
        # Clean NASDAQ
        nasdaq = nasdaq[['Symbol', 'Security Name']].copy()
        nasdaq['Exchange'] = 'NASDAQ'
        
        # Clean NYSE/AMEX
        other = other[['ACT Symbol', 'Security Name']].rename(columns={'ACT Symbol': 'Symbol'}).copy()
        other['Exchange'] = 'NYSE/AMEX'
        
        # Combine
        df = pd.concat([nasdaq, other], ignore_index=True).drop_duplicates(subset='Symbol')
        # Filter junk symbols
        df = df[~df['Symbol'].str.contains(r'\$|\.|TEST', na=False)]
        
        # Simple Logic for Type
        df['Type'] = df['Security Name'].apply(lambda x: 'ETF' if ' ETF' in str(x) or 'Trust' in str(x) else 'Stock')
        return df
    except:
        return pd.DataFrame()

# --- 3. Initial Load ---
# We call the spinner OUTSIDE the cached function
with st.spinner("Connecting to NASDAQ/NYSE..."):
    tickers_df = load_all_us_tickers()

if tickers_df.empty:
    st.error("Data source currently unavailable. Please try again in a few minutes.")
    st.stop()

# --- 4. Sidebar UI ---
with st.sidebar:
    st.header("⚙️ Analysis Settings")
    start_date = st.date_input("Start Date", value=date(2025, 2, 18))
    end_date = st.date_input("End Date", value=date.today())
    
    st.divider()
    asset_types = st.multiselect("Asset Type", ["Stock", "ETF"], default=["Stock", "ETF"])
    min_price = st.number_input("Min Price ($) at Start", value=1.0)
    
    st.divider()
    batch_size = st.slider("Batch Size (Accuracy)", 50, 200, 100)

# Filter the list based on sidebar before scanning
filtered_tickers = tickers_df[tickers_df['Type'].isin(asset_types)]["Symbol"].tolist()

# --- 5. Main Execution ---
st.title("📈 US Market Performance Tracker")
st.caption(f"Ready to scan {len(filtered_tickers):,} symbols across all US exchanges.")

if st.button("🚀 Run Full Analysis", use_container_width=True):
    if start_date >= end_date:
        st.error("End date must be after start date.")
    else:
        results = []
        progress_bar = st.progress(0)
        status_msg = st.empty()
        
        for i in range(0, len(filtered_tickers), batch_size):
            batch = filtered_tickers[i:i + batch_size]
            status_msg.text(f"Processing batch {i//batch_size + 1}...")
            
            try:
                # auto_adjust=True fixes the LICN/SNDK split errors
                data = yf.download(batch, start=start_date, end=end_date, auto_adjust=True, progress=False)
                
                if not data.empty and "Close" in data:
                    closes = data["Close"]
                    if isinstance(closes, pd.Series): closes = closes.to_frame()

                    for ticker in closes.columns:
                        series = closes[ticker].dropna()
                        if len(series) >= 2:
                            # Verify existence at start (XDEF fix)
                            if (series.index[0].date() - start_date).days <= 7:
                                s_p = series.iloc[0]
                                e_p = series.iloc[-1]
                                
                                if s_p >= min_price:
                                    pct = ((e_p / s_p) - 1) * 100
                                    # Filter outliers
                                    if -99.9 < pct < 2000:
                                        results.append({
                                            "Symbol": ticker,
                                            "% Change": pct,
                                            "Start Price": s_p,
                                            "End Price": e_p
                                        })
            except:
                pass
            
            progress_bar.progress(min(1.0, (i + batch_size) / len(filtered_tickers)))
            time.sleep(0.1)

        if results:
            # Prepare data for display - explicitly cleaning to avoid Arrow errors
            final_df = pd.DataFrame(results).copy()
            final_df = final_df.merge(tickers_df, on='Symbol', how='left')
            
            # Formatting and final data-type cleanup
            final_df["% Change"] = final_df["% Change"].astype(float).round(2)
            final_df["Start Price"] = final_df["Start Price"].astype(float).round(2)
            final_df["End Price"] = final_df["End Price"].astype(float).round(2)
            
            status_msg.success(f"Analysis complete! {len(final_df)} symbols verified.")
            st.balloons()

            c1, c2 = st.columns(2)
            with c1:
                st.subheader("🚀 Top 15 Gainers")
                st.dataframe(final_df.sort_values("% Change", ascending=False).head(15), hide_index=True)
            with c2:
                st.subheader("📉 Top 15 Losers")
                st.dataframe(final_df.sort_values("% Change", ascending=True).head(15), hide_index=True)
            
            st.subheader("📊 Full Data Table")
            st.dataframe(final_df, use_container_width=True)
        else:
            status_msg.warning("No data returned. Adjust filters and try again.")
