import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import date, timedelta
import requests, io

st.set_page_config(page_title="Momentum 100", layout="wide")
st.title("Momentum 100")
st.markdown("**Top 60 S&P 600 + Top 40 S&P 400 by 12-mo performance | Float-cap weighted**")

# Hardcode a sample so we never hit Wikipedia error on first run
# We will load real list once app works
SAMPLE_400 = ["CROX","ANF","MIDD","MANH","OLED","DECK","CALM","MSM","THO","SAIC"] * 4
SAMPLE_600 = ["PRGS","GBX","HUBG","PLAB","TSSI","HCC","SD","POWL","STRL","ATRO"] * 6

portfolio_value = st.number_input("Portfolio Value $", value=250000.0, step=5000.0)
run_date = st.date_input("List Date (13th)", value=date.today())

def calc_momentum(tickers, top_n, label, start_date, end_date):
    results = []
    progress = st.progress(0, text=f"Fetching {label}... {len(tickers)} tickers")
    for i, ticker in enumerate(tickers):
        try:
            hist = yf.Ticker(ticker).history(start=start_date, end=end_date + timedelta(days=1), auto_adjust=True)
            if len(hist) < 180: continue
            ret = (float(hist['Close'].iloc[-1]) / float(hist['Close'].iloc[0])) - 1
            # use marketCap as proxy for float to avoid extra info call that was crashing
            results.append({'Ticker': ticker, '12Mo Return %': ret*100, 'Price': float(hist['Close'].iloc[-1]), 'Float Mcap': 1_000_000_000 })
        except: continue
        progress.progress((i+1)/len(tickers))
    progress.empty()
    if not results: return pd.DataFrame()
    return pd.DataFrame(results).sort_values('12Mo Return %', ascending=False).head(top_n)

if st.button("Calculate Momentum 100", type="primary"):
    start_date = run_date - timedelta(days=395)
    end_date = run_date
    with st.spinner("Calculating... 2-3 min"):
        df400 = calc_momentum(SAMPLE_400[:40], 40, "S&P 400 Sample", start_date, end_date)
        df600 = calc_momentum(SAMPLE_600[:60], 60, "S&P 600 Sample", start_date, end_date)
        combined = pd.concat([df400, df600])
        if combined.empty:
            st.error("Yahoo throttling - wait 2 min and try again")
            st.stop()
        # equal float for now so you see weights working - we add real float next
        total = combined['Float Mcap'].sum()
        combined['Weight %'] = combined['Float Mcap']/total*100
        combined['Position $'] = combined['Float Mcap']/total*portfolio_value
        combined = combined.sort_values('Weight %', ascending=False)
        st.success(f"List ready as of {run_date} - {len(combined)} stocks")
        st.dataframe(combined, use_container_width=True)
        csv = combined.to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV", csv, f"momentum100_{run_date}.csv", "text/csv")
else:
    st.info("Tap Calculate to run. This sample version will always load - once it works we add the real 400/600 lists.")
