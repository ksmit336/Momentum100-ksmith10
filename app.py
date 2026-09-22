import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import date, timedelta
import requests
import sys
import config
from emailer import send_alert_email

st.set_page_config(page_title="Momentum 100", layout="wide")

@st.cache_data(ttl=86400)
def get_sp_constituents():
    headers = {'User-Agent':'Mozilla/5.0'}
    try:
        url_400 = "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies"
        tables_400 = pd.read_html(requests.get(url_400, headers=headers, timeout=20).text)
        df_400 = tables_400[0]
        col_400 = 'Ticker symbol' if 'Ticker symbol' in df_400.columns else df_400.columns[0]
        tickers_400 = [t.replace('.', '-') for t in df_400[col_400].dropna().tolist()]

        url_600 = "https://en.wikipedia.org/wiki/List_of_S%26P_600_companies"
        tables_600 = pd.read_html(requests.get(url_600, headers=headers, timeout=20).text)
        df_600 = tables_600[0]
        col_600 = 'Ticker symbol' if 'Ticker symbol' in df_600.columns else df_600.columns[0]
        tickers_600 = [t.replace('.', '-') for t in df_600[col_600].dropna().tolist()]

        return tickers_400, tickers_600
    except Exception as e:
        st.warning(f"Using fallback list: {e}")
        return ["OLED","MIDD","MANH"]*15, ["PRGS","GBX","HUBG"]*25

def calc_momentum(tickers, top_n, label, start_date, end_date):
    results = []
    progress = st.progress(0, text=f"Fetching {label}...")
    for i, ticker in enumerate(tickers):
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(start=start_date, end=end_date + timedelta(days=1), auto_adjust=True)
            if len(hist) < 180: continue
            price_now = float(hist['Close'].iloc[-1])
            price_12m = float(hist['Close'].iloc[0])
            if price_12m == 0: continue
            ret_12m = (price_now / price_12m) - 1
            info = {}
            try: info = stock.info
            except: pass
            float_shares = info.get('floatShares') or info.get('sharesOutstanding')
            float_mcap = float_shares * price_now if float_shares else info.get('marketCap', 0)
            results.append({
                'Ticker': ticker,
                'Company': info.get('shortName', ticker),
                'Price': price_now,
                '12Mo Return %': ret_12m*100,
                'Float Mcap': float_mcap
            })
        except: continue
        if i % 5 == 0:
            progress.progress(min((i+1)/len(tickers), 1.0))
    progress.empty()
    if not results: return pd.DataFrame()
    return pd.DataFrame(results).sort_values('12Mo Return %', ascending=False).head(top_n)

# Sidebar
with st.sidebar:
    st.header("Settings")
    portfolio_value = st.number_input("Portfolio Value $ (manual)", min_value=1000.0, value=250000.0, step=5000.0)
    alert_email = st.text_input("Alert Email To", value=config.ALERT_EMAIL_TO)
    st.caption("Float-adjusted = floatShares * price (Yahoo)")

st.title("Momentum 100")
st.markdown("**Top 60 S&P 600 + Top 40 S&P 400 by 12-mo performance | Float-cap weighted**")

col1, col2 = st.columns(2)
with col1:
    run_date = st.date_input("List Date (13th)", value=date.today())
with col2:
    st.info(f"Portfolio: ${portfolio_value:,.0f}")

sp400_tickers, sp600_tickers = get_sp_constituents()
st.caption(f"Loaded {len(sp400_tickers)} S&P 400 and {len(sp600_tickers)} S&P 600 tickers as of {run_date}")

if st.button("Calculate Momentum 100", type="primary") or "--auto" in sys.argv:
    start_date = run_date - timedelta(days=395)
    end_date = run_date
    with st.spinner("Calculating - takes 2-4 min first run..."):
        df400 = calc_momentum(sp400_tickers, 40, "S&P 400", start_date, end_date)
        df600 = calc_momentum(sp600_tickers, 60, "S&P 600", start_date, end_date)
        if df400.empty and df600.empty:
            st.error("No data - Yahoo throttling, try again in 2 min")
            st.stop()
        combined = pd.concat([df400, df600], ignore_index=True)
        combined = combined[combined['Float Mcap'] > 0]
        total_float = combined['Float Mcap'].sum()
        combined['Weight %'] = combined['Float Mcap'] / total_float * 100
        combined['Position $'] = combined['Float Mcap'] / total_float * portfolio_value
        combined['Shares'] = combined['Position $'] / combined['Price']
        combined = combined.sort_values('Weight %', ascending=False)

        st.success(f"List ready as of {run_date} - {len(combined)} stocks")
        st.dataframe(combined.style.format({
            'Price': '${:.2f}', '12Mo Return %': '{:.2f}%', 'Weight %': '{:.3f}%',
            'Position $': '${:,.0f}', 'Shares': '{:.0f}'
        }), use_container_width=True)

        csv = combined.to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV", csv, f"momentum100_{run_date}.csv", "text/csv")

        if config.SENDGRID_API_KEY:
            config.ALERT_EMAIL_TO = alert_email
            ok, msg = send_alert_email(f"Momentum 100 Ready - {run_date}", combined.head(20).to_html(index=False))
            st.success(f"Email: {msg}") if ok else st.error(f"Email failed: {msg}")
        else:
            st.warning("Add SENDGRID_API_KEY in config.py to enable email alerts")
