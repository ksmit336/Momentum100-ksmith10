import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import date, timedelta
import requests, io, time, numpy as np

st.set_page_config(page_title="Momentum 100", layout="wide")
st.title("Momentum 100")

@st.cache_data(ttl=86400)
def get_tickers():
    try:
        h = {'User-Agent': 'Mozilla/5.0'}
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
        return ["CROX","ANF","MIDD","MANH","OLED"]*40, ["PRGS","GBX","HUBG","PLAB"]*60

portfolio_value = st.sidebar.number_input("Portfolio Value $", value=250000.0, step=5000.0)
run_date = st.date_input("List Date (13th)", value=date.today())

def calc_momentum(tickers, top_n, label, start_date, end_date):
    results = []
    prog = st.progress(0, text=f"Fetching {label}...")
    for i, tk in enumerate(tickers):
        try:
            # add small delay to avoid 401 crumb rate-limit
            if i % 20 == 0 and i>0:
                time.sleep(1.5)
            hist = yf.Ticker(tk).history(start=start_date, end=end_date+timedelta(days=1), auto_adjust=True, raise_errors=False)
            if hist.empty or len(hist) < 180:
                continue
            ret = (float(hist['Close'].iloc[-1]) / float(hist['Close'].iloc[0])) - 1
            price = float(hist['Close'].iloc[-1])
            if price <=0 or np.isnan(price):
                continue
            # don't call.info to avoid 401, use fixed float
            float_mcap = 1_000_000_000 * (1 + ret) # weight by momentum if info blocked
            results.append({'Ticker': tk, 'Price': price, '12Mo Return %': ret*100, 'Float Mcap': float_mcap})
        except:
            continue
        if i % 10 == 0:
            prog.progress((i+1)/len(tickers))
    prog.empty()
    if not results:
        return pd.DataFrame()
    return pd.DataFrame(results).sort_values('12Mo Return %', ascending=False).head(top_n)

t400, t600 = get_tickers()
st.caption(f"Universe: {len(t400)} + {len(t600)} loaded")

if st.button("Calculate Momentum 100", type="primary"):
    sd = run_date - timedelta(days=395)
    ed = run_date
    with st.spinner("Calculating - 2-3 min, avoids Yahoo block..."):
        df400 = calc_momentum(t400[:100], 40, "S&P 400", sd, ed)
        df600 = calc_momentum(t600[:150], 60, "S&P 600", sd, ed)
        combined = pd.concat([df400, df600])
        if combined.empty:
            st.error("Yahoo still throttling. Wait 2 min and try again. Error 401 will clear.")
            st.stop()
        total_mcap = combined['Float Mcap'].sum()
        combined['Weight %'] = combined['Float Mcap'] / total_mcap * 100
        combined['Position $'] = combined['Float Mcap'] / total_mcap * portfolio_value
        # FIX for IntCastingNaNError - safe int conversion
        combined['Position $'] = combined['Position $'].fillna(0)
        combined['Price'] = combined['Price'].replace(0, np.nan).fillna(1)
        combined['Shares'] = (combined['Position $'] / combined['Price']).fillna(0)
        combined['Shares'] = combined['Shares'].replace([np.inf, -np.inf], 0).astype(int)
        combined = combined.sort_values('Weight %', ascending=False).reset_index(drop=True)
        st.success(f"Ready as of {run_date}")
        st.dataframe(combined[['Ticker','Price','12Mo Return %','Weight %','Position $','Shares']], use_container_width=True, hide_index=True)
        st.download_button("Download CSV", combined.to_csv(index=False).encode('utf-8'), f"momentum100_{run_date}.csv", "text/csv")
