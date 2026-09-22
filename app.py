import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import date, timedelta
import requests, io

st.set_page_config(page_title="Momentum 100", layout="wide")
st.title("Momentum 100")
st.markdown("**Top 60 S&P 600 + Top 40 S&P 400 by 12-mo momentum | Float-cap weighted**")

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
        t400 = [str(t).replace('.', '-').strip() for t in df1[c1].dropna().tolist()]
        t600 = [str(t).replace('.', '-').strip() for t in df2[c2].dropna().tolist()]
        return t400, t600
    except Exception as e:
        st.warning(f"Using sample tickers (Wikipedia blocked): {e}")
        return ["CROX","ANF","MIDD","MANH","OLED","DECK","CALM","MSM","THO","SAIC"]*40, ["PRGS","GBX","HUBG","PLAB","TSSI","HCC","SD","POWL","STRL","ATRO"]*60

portfolio_value = st.sidebar.number_input("Portfolio Value $", value=250000.0, step=5000.0)
run_date = st.date_input("List Date (13th)", value=date.today())
st.sidebar.caption("Tip: For daily quick check use [:100] version. For official 13th list use full.")

def calc_momentum(tickers, top_n, label, start_date, end_date):
    results = []
    prog = st.progress(0, text=f"Fetching {label}... {len(tickers)} tickers")
    for i, tk in enumerate(tickers):
        try:
            ticker_obj = yf.Ticker(tk)
            hist = ticker_obj.history(start=start_date, end=end_date+timedelta(days=1), auto_adjust=True)
            if len(hist) < 180:
                continue
            ret = (float(hist['Close'].iloc[-1]) / float(hist['Close'].iloc[0])) - 1
            price = float(hist['Close'].iloc[-1])
            # Get float market cap - try multiple fields, never crash
            try:
                info = ticker_obj.get_info()
                float_shares = info.get('floatShares') or info.get('sharesOutstanding') or 0
                if float_shares == 0:
                    float_shares = info.get('marketCap', 1e9) / price if price > 0 else 1e9
                float_mcap = float_shares * price
            except:
                float_mcap = 1_000_000_000

            results.append({
                'Ticker': tk,
                'Price': price,
                '12Mo Return %': ret * 100,
                'Float Mcap': float_mcap
            })
        except:
            continue
        if i % 10 == 0:
            prog.progress((i+1)/len(tickers))
    prog.empty()
    if not results:
        return pd.DataFrame()
    return pd.DataFrame(results).sort_values('12Mo Return %', ascending=False).head(top_n)

t400, t600 = get_tickers()
st.caption(f"Universe: {len(t400)} S&P 400 + {len(t600)} S&P 600 tickers loaded")

if st.button("Calculate Momentum 100", type="primary"):
    sd = run_date - timedelta(days=395)
    ed = run_date

    with st.spinner("Calculating Momentum 100... this takes 3-6 min for full universe"):
        # FAST VERSION for iPad: use t400[:100] and t600[:150]
        # FULL VERSION: use t400 and t600
        df400 = calc_momentum(t400[:100], 40, "S&P 400", sd, ed)
        df600 = calc_momentum(t600[:150], 60, "S&P 600", sd, ed)

        combined = pd.concat([df400, df600])
        if combined.empty:
            st.error("Yahoo is throttling requests. Wait 2 minutes and tap Calculate again.")
            st.stop()

        total_mcap = combined['Float Mcap'].sum()
        combined['Weight %'] = combined['Float Mcap'] / total_mcap * 100
        combined['Position $'] = combined['Float Mcap'] / total_mcap * portfolio_value
        combined['Shares'] = (combined['Position $'] / combined['Price']).round(0).astype(int)
        combined = combined.sort_values('Weight %', ascending=False).reset_index(drop=True)

        st.success(f"Momentum 100 as of {run_date} - {len(combined)} stocks | Portfolio: ${portfolio_value:,.0f}")

        display_cols = ['Ticker', 'Price', '12Mo Return %', 'Weight %', 'Position $', 'Shares']
        st.dataframe(combined[display_cols], use_container_width=True, hide_index=True)

        # Totals
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Weight", f"{combined['Weight %'].sum():.1f}%")
        c2.metric("Total Position", f"${combined['Position $'].sum():,.0f}")
        c3.metric("Avg Momentum", f"{combined['12Mo Return %'].mean():.1f}%")

        csv = combined.to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV for orders", csv, f"momentum100_{run_date}.csv", "text/csv", type="primary")
else:
    st.info("Tap Calculate Momentum 100 to run. Add this page to Home Screen for one-tap access.")
