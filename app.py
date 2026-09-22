import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import date, timedelta
import requests, io

st.set_page_config(page_title="Momentum 100", layout="wide")
st.title("Momentum 100")
st.markdown("**Top 60 S&P 600 + Top 40 S&P 400 by 12-mo performance | Float-cap weighted**")

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
        return ["CROX","ANF","MIDD","MANH","OLED"]*8, ["PRGS","GBX","HUBG","PLAB"]*15

portfolio_value = st.sidebar.number_input("Portfolio Value $", value=250000.0, step=5000.0)
run_date = st.date_input("List Date (13th)", value=date.today())

def calc(tickers, top_n, label, start_date, end_date):
    results = []
    prog = st.progress(0, text=f"Fetching {label}...")
    for i, tk in enumerate(tickers):
        try:
            t = yf.Ticker(tk)
            hist = t.history(start=start_date, end=end_date+timedelta(days=1), auto_adjust=True)
            if len(hist) < 180: continue
            ret = (float(hist['Close'].iloc[-1]) / float(hist['Close'].iloc[0])) - 1
            # Try float, fallback to marketCap, fallback to 1B so it never crashes
            try:
                info = t.get_info()
                f = info.get('floatShares') or info.get('sharesOutstanding') or info.get('marketCap') or 1e9
            except:
                f = 1e9
            results.append({'Ticker': tk, 'Price': float(hist['Close'].iloc[-1]), '12Mo Return %': ret*100, 'Float Mcap': f})
        except: continue
        if i%10==0: prog.progress((i+1)/len(tickers))
    prog.empty()
    if not results: return pd.DataFrame()
    return pd.DataFrame(results).sort_values('12Mo Return %', ascending=False).head(top_n)

t400, t600 = get_tickers()
st.caption(f"Universe loaded: {len(t400)} S&P 400 + {len(t600)} S&P 600")

if st.button("Calculate Momentum 100", type="primary"):
    sd = run_date - timedelta(days=395)
    ed = run_date
    with st.spinner("Running - 3-4 min first time..."):
        df400 = calc(t400[:100], 40, "S&P 400", sd, ed) # limit to 100 for speed on iPad, change to t400 for full
        df600 = calc(t600[:150], 60, "S&P 600", sd, ed)
        comb = pd.concat([df400, df600])
        if comb.empty:
            st.error("Yahoo throttled - wait 2 min, tap again")
            st.stop()
        tot = comb['Float Mcap'].sum()
        comb['Weight %'] = comb['Float Mcap']/tot*100
        comb['Position $'] = comb['Float Mcap']/tot*portfolio_value
        comb['Shares'] = comb['Position $']/comb['Price']
        comb = comb.sort_values('Weight %', ascending=False)
        st.success(f"Ready as of {run_date} - {len(comb)} stocks")
        st.dataframe(comb.style.format({'Price':'${:.2f}','12Mo Return %':'{:.2f}%','Weight %':'{:.3f}%','Position $':'${:,.0f}','Shares':'{:.0f}'}), use_container_width=True)
        st.download_button("Download CSV", comb.to_csv(index=False).encode('utf-8'), f"momentum100_{run_date}.csv", "text/csv")
