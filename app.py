import streamlit as st
import pandas as pd
from datetime import date, timedelta, datetime
import requests, io
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

st.set_page_config(page_title="Momentum 100 - Alpaca", layout="wide")

if 'running' not in st.session_state:
    st.session_state.running = False

st.title("Momentum 100 - Alpaca Fast")

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
        return ["CROX","ANF","MIDD","MANH"]*25, ["PRGS","GBX","HUBG"]*50

API_KEY = st.secrets.get("ALPACA_API_KEY", "")
SECRET_KEY = st.secrets.get("ALPACA_SECRET_KEY", "")

portfolio_value = st.sidebar.number_input("Portfolio Value $", value=250000.0, step=5000.0)
run_date = st.date_input("List Date", value=date.today())

# Placeholders
error_placeholder = st.empty()
warning_placeholder = st.empty()
log_placeholder = st.empty()

def calc_alpaca(tickers, top_n, label, start_date, end_date, log_box):
    results = []
    invalid = []
    prog = st.progress(0, text=f"Fetching {label}...")
    client = StockHistoricalDataClient(API_KEY, SECRET_KEY)
    for batch_idx in range(0, len(tickers), 50):
        batch = tickers[batch_idx:batch_idx+50]
        if batch_idx % 20 == 0:
            log_box.write(f"[{label}] Processing {batch_idx}/{len(tickers)} - {len(results)} valid so far...")
        try:
            req = StockBarsRequest(symbol_or_symbols=batch, timeframe=TimeFrame.Day, start=start_date, end=end_date+timedelta(days=1), adjustment='all')
            bars = client.get_stock_bars(req).df
            if bars.empty:
                for tk in batch:
                    invalid.append(f"{tk} - no bars")
                continue
            for tk in batch:
                try:
                    if tk not in bars.index.get_level_values(0):
                        invalid.append(f"{tk} - not returned")
                        continue
                    hist = bars.loc[tk]
                    if len(hist) < 180:
                        invalid.append(f"{tk} - <180 days")
                        continue
                    ret = (float(hist['close'].iloc[-1]) / float(hist['close'].iloc[0])) - 1
                    price = float(hist['close'].iloc[-1])
                    results.append({'Ticker': tk, 'Price': price, '12Mo Return %': ret*100, 'Float Mcap': 1e9*(1+ret)})
                except Exception as e:
                    invalid.append(f"{tk} - {str(e)[:60]}")
        except Exception as e:
            warning_placeholder.warning(f"Batch {batch_idx//50+1} retry: {str(e)[:100]}")
            for tk in batch:
                invalid.append(f"{tk} - batch error")
        prog.progress(min((batch_idx+50)/len(tickers), 1.0))
    prog.empty()
    log_box.write(f"[{label}] Done: {len(results)} valid, {len(invalid)} invalid")
    df = pd.DataFrame(results).sort_values('12Mo Return %', ascending=False).head(top_n) if results else pd.DataFrame()
    return df, invalid

t400, t600 = get_tickers()
st.caption(f"Universe {len(t400)} + {len(t600)}")

# BUTTON ALWAYS VISIBLE - disabled only while running
button_disabled = st.session_state.running
if st.button("Calculate Momentum 100 - Alpaca", type="primary", disabled=button_disabled):
    if not API_KEY or not SECRET_KEY:
        error_placeholder.error("Add Alpaca keys in Streamlit > Settings > Secrets first! See instructions.")
        st.session_state.running = False
    else:
        st.session_state.running = True
        error_placeholder.empty()
        warning_placeholder.empty()
        try:
            sd = datetime.combine(run_date - timedelta(days=395), datetime.min.time())
            ed = datetime.combine(run_date, datetime.min.time())
            df400, bad400 = calc_alpaca(t400[:100], 40, "S&P 400", sd, ed, log_placeholder)
            df600, bad600 = calc_alpaca(t600[:150], 60, "S&P 600", sd, ed, log_placeholder)
            combined = pd.concat([df400, df600])
            if combined.empty:
                error_placeholder.error("No data returned - check Alpaca keys")
            else:
                combined['Weight %'] = combined['Float Mcap']/combined['Float Mcap'].sum()*100
                combined['Position $'] = combined['Float Mcap']/combined['Float Mcap'].sum()*portfolio_value
                combined['Shares'] = (combined['Position $']/combined['Price']).astype(int)
                combined = combined.sort_values('Weight %', ascending=False).reset_index(drop=True)
                # Clear warnings/errors on success
                error_placeholder.empty()
                warning_placeholder.empty()
                log_placeholder.empty()
                st.success(f"Ready - {len(combined)} stocks")
                st.dataframe(combined[['Ticker','Price','12Mo Return %','Weight %','Position $','Shares']], use_container_width=True)
                with st.expander(f"Invalid tickers: {len(bad400+bad600)}"):
                    st.dataframe(pd.DataFrame(bad400+bad600, columns=["Ticker - Reason"]), use_container_width=True)
                st.download_button("Download CSV", combined.to_csv(index=False).encode('utf-8'), f"momentum100_{run_date}.csv", "text/csv", type="primary")
        except Exception as e:
            error_placeholder.error(f"Error: {e}")
        finally:
            st.session_state.running = False
            st.rerun()
