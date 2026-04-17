import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from datetime import date
import time

st.title("📈 All US Stocks & ETFs – Top Gainers/Losers")
st.caption("🔗 Shareable with friends • Data from Yahoo Finance")

# --- Load full ticker list from official NASDAQ (no CSV needed) ---
@st.cache_data(ttl=86400)  # cache for 24 hours
def load_tickers():
    try:
        nasdaq = pd.read_csv("https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt", sep='|')
        other = pd.read_csv("https://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt", sep='|')
        nasdaq = nasdaq[['Symbol', 'Security Name']].copy()
        other = other[['ACT Symbol', 'Security Name']].rename(columns={'ACT Symbol': 'Symbol'}).copy()
        df = pd.concat([nasdaq, other], ignore_index=True).drop_duplicates(subset='Symbol')
        return df
    except:
        st.error("Could not load ticker list")
        return pd.DataFrame()

tickers_df = load_tickers()
all_tickers = tickers_df["Symbol"].tolist()

st.info(f"Loaded **{len(all_tickers):,}** US stocks & ETFs")

col1, col2 = st.columns(2)
start_date = col1.date_input("Start Date", value=date(2025, 1, 1))
end_date   = col2.date_input("End Date", value=date.today())

if st.button("🚀 Calculate % Change (30–90 seconds)"):
    if start_date >= end_date:
        st.error("End date must be after start date")
    else:
        with st.spinner(f"Fetching prices for ~10,000 tickers… (this may take 30–90 seconds)"):
            batch_size = 120
            results = []
            progress_bar = st.progress(0)
            
            for i in range(0, len(all_tickers), batch_size):
                batch = all_tickers[i:i + batch_size]
                try:
                    data = yf.download(
                        tickers=batch,
                        start=start_date,
                        end=end_date,
                        progress=False,
                        threads=True,
                        auto_adjust=True,
                        timeout=30
                    )
                    if not data.empty and "Close" in data.columns:
                        closes = data["Close"].dropna(how="all")
                        if len(closes) >= 2:
                            pct = (closes.iloc[-1] / closes.iloc[0] - 1) * 100
                            temp = pd.DataFrame({"Symbol": pct.index, "% Change": pct.values})
                            results.append(temp)
                except Exception:
                    pass  # skip bad batches quietly
                progress_bar.progress(min(1.0, (i + batch_size) / len(all_tickers)))
                time.sleep(0.3)

            if results:
                final_df = pd.concat(results, ignore_index=True)
                final_df = final_df.merge(tickers_df[["Symbol", "Security Name"]], on="Symbol", how="left")
                final_df = final_df.rename(columns={"Security Name": "Name"})
                final_df = final_df.sort_values("% Change", ascending=False).round(2).reset_index(drop=True)
                
                st.success("✅ Done!")
                
                c1, c2 = st.columns(2)
                c1.subheader("🚀 Top 15 Gainers")
                c1.dataframe(final_df.head(15), use_container_width=True)
                c2.subheader("📉 Top 15 Losers")
                c2.dataframe(final_df.tail(15).sort_values("% Change"), use_container_width=True)
                
                st.subheader("Full sortable table")
                st.dataframe(final_df, use_container_width=True)
            else:
                st.error("Yahoo rate limit hit. Wait 1–2 minutes and try again.")

st.caption("⚠️ For friends: First load can be slow. Same date pair becomes faster after the first use.")
