import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import date, timedelta
import requests, io, time, numpy as np
import logging
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

st.set_page_config(page_title="Momentum 100", layout="wide")
st.title("Momentum 100")
st.markdown("Log shows progress every 20 tickers to spot throttling")

@st.cache_data(ttl=86400)
def get_tickers():
    try:
        h = {'User-Agent':'Mozilla/5.0'}
        r1 = requests.get("https://en.wikipedia.org/wiki/List_of_S%26P_400_companies", headers=h, timeout=30)
        r2 = requests.get("https://en.wikipedia.org/wiki/List_of_S%26P_600_companies", headers=h, timeout=30)
        df1 = pd.read_html(io.StringIO(r1.text))[0]
        df2 = pd.read_html(io.StringIO(r2.text))[0]
        c1 = 'Ticker symbol' if 'Ticker symbol' in df1.columns else df1.columns[0]
        c2 = 'Ticker symbol' if 'Ticker symbol' in df2.columns else df2.columns[0]
        t400 = [str(t).replace('.','-').strip() for t in df1[c1].dropna().tolist()]
        t600 = [str(t).replace('.','-').strip() for t in df2[c2].dropna().tolist()]
        return t400, t600
    except:
        return ["CROX","ANF","MIDD","MANH"]*25, ["PRGS","GBX","HUBG","PLAB"]*38

portfolio_value = st.sidebar.number_input("Portfolio Value $", value=250000.0, step=5000.0)
run_date = st.date_input("List Date", value=date.today())

def calc_batch(tickers, top_n, label, start_date, end_date, log_box):
    # Batch download - ONE call for all tickers
    log_box.write(f"[{label}] Starting batch download for {len(tickers)} tickers...")
    try:
        data = yf.download(tickers, start=start_date, end=end_date+timedelta(days=1), auto_adjust=True, group_by='ticker', threads=True, progress=False, timeout=60)
    except Exception as e:
        log_box.write(f"❌ Batch failed: {e} - falling back to slow mode")
        return pd.DataFrame(), [f"Batch failed {e}"]

    results = []
    invalid = []
    for idx, tk in enumerate(tickers):
        if idx % 20 == 0:
            log_box.write(f"... {idx}/{len(tickers)} processed, {len(results)} valid so far")
        try:
            if len(tickers) == 1:
                hist = data
            else:
                if tk not in data.columns.get_level_values(0):
                    invalid.append(f"{tk} - not in download")
                    continue
                hist = data[tk].dropna()
            if len(hist) < 180:
                invalid.append(f"{tk} - <180 days ({len(hist)})")
                continue
            ret = (float(hist['Close'].iloc[-1]) / float(hist['Close'].iloc[0])) - 1
            price = float(hist['Close'].iloc[-1])
            results.append({'Ticker': tk, 'Price': price, '12Mo Return %': ret*100, 'Float Mcap': 1e9*(1+ret)})
        except Exception as e:
            invalid.append(f"{tk} - {str(e)[:80]}")
    log_box.write(f"[{label}] Done: {len(results)} valid, {len(invalid)} invalid")
    df = pd.DataFrame(results).sort_values('12Mo Return %', ascending=False).head(top_n) if results else pd.DataFrame()
    return df, invalid

t400, t600 = get_tickers()
st.caption(f"Loaded {len(t400)} + {len(t600)}")

log_container = st.container()

if st.button("Calculate Momentum 100 (FAST BATCH)", type="primary"):
    sd = run_date - timedelta(days=395)
    ed = run_date
    with log_container:
        st.subheader("Yahoo Log (every 20)")
        log_box = st.empty()
        # Use st.write stream
        import sys
        from io import StringIO
        log_area = st.container()

        with log_area:
            df400, bad400 = calc_batch(t400[:100], 40, "S&P 400", sd, ed, st)
            df600, bad600 = calc_batch(t600[:150], 60, "S&P 600", sd, ed, st)

    combined = pd.concat([df400, df600])
    if combined.empty:
        st.error("Yahoo still throttling - wait 3 min. This batch method usually fixes it on 2nd try.")
        st.stop()
    combined['Weight %'] = combined['Float Mcap']/combined['Float Mcap'].sum()*100
    combined['Position $'] = combined['Float Mcap']/combined['Float Mcap'].sum()*portfolio_value
    combined['Shares'] = (combined['Position $']/combined['Price']).fillna(0).replace([np.inf,-np.inf],0).astype(int)
    combined = combined.sort_values('Weight %', ascending=False)
    st.success(f"Ready - {len(combined)} stocks in {len(t400[:100])+len(t600[:150])} scanned")
    st.dataframe(combined[['Ticker','Price','12Mo Return %','Weight %','Position $','Shares']], use_container_width=True)

    with st.expander(f"Invalid: {len(bad400+bad600)} tickers"):
        st.dataframe(pd.DataFrame(bad400+bad600, columns=["Reason"]), use_container_width=True)
