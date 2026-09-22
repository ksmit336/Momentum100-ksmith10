import streamlit as st
import pandas as pd
from datetime import date, timedelta, datetime
import requests
import io
import re
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed

st.set_page_config(page_title="Momentum 100", layout="wide")

st.markdown("""
<style>
.block-container {max-width:100%!important; padding-top:1rem; padding-left:2rem; padding-right:2rem;}
</style>
""", unsafe_allow_html=True)

if "running" not in st.session_state:
    st.session_state.running = False
if "result" not in st.session_state:
    st.session_state.result = None

st.title("Momentum 100 - Alpaca Fast")

@st.cache_data(ttl=86400)
def get_tickers():
    try:
        h = {"User-Agent": "Mozilla/5.0"}
        r1 = requests.get("https://en.wikipedia.org/wiki/List_of_S%26P_400_companies", headers=h, timeout=30)
        r2 = requests.get("https://en.wikipedia.org/wiki/List_of_S%26P_600_companies", headers=h, timeout=30)
        df1 = pd.read_html(io.StringIO(r1.text))[0]
        df2 = pd.read_html(io.StringIO(r2.text))[0]
        c1 = "Ticker symbol" if "Ticker symbol" in df1.columns else df1.columns[0]
        c2 = "Ticker symbol" if "Ticker symbol" in df2.columns else df2.columns[0]
        raw400 = [str(t).strip() for t in df1[c1].dropna().tolist()]
        raw600 = [str(t).strip() for t in df2[c2].dropna().tolist()]
        def clean(lst):
            out = []
            for t in lst:
                t = t.upper().replace(".", "-").split("-")[0]
                if "$" in t or "/" in t:
                    continue
                if not re.match(r"^[A-Z]{1,5}$", t):
                    continue
                out.append(t)
            return list(dict.fromkeys(out))
        return clean(raw400), clean(raw600)
    except Exception:
        return ["CROX", "ANF", "MIDD"] * 20, ["PRGS", "GBX", "HUBG"] * 30

API_KEY = st.secrets.get("ALPACA_API_KEY", "")
SECRET_KEY = st.secrets.get("ALPACA_SECRET_KEY", "")

t400, t600 = get_tickers()
st.caption(f"Universe {len(t400)} + {len(t600)} | IEX feed")

c1, c2 = st.columns([1, 2])
with c1:
    portfolio_value = st.number_input("Portfolio Value $", value=250000.0, step=5000.0, format="%.0f")
    run_date = st.date_input("List Date", value=date.today())
with c2:
    st.write("")

error_box = st.empty()
warn_box = st.empty()
log_box = st.empty()

def calc_alpaca(tickers, top_n, label, sd, ed):
    results = []
    invalid = []
    prog = st.progress(0, text=f"Fetching {label}...")
    client = StockHistoricalDataClient(API_KEY, SECRET_KEY)
    for batch_idx in range(0, len(tickers), 50):
        batch = tickers[batch_idx:batch_idx+50]
        if batch_idx % 20 == 0:
            log_box.write(f"{label} {batch_idx}/{len(tickers)} valid {len(results)}")
        remaining = batch[:]
        while remaining:
            try:
                req = StockBarsRequest(
                    symbol_or_symbols=remaining,
                    timeframe=TimeFrame.Day,
                    start=sd,
                    end=ed + timedelta(days=1),
                    adjustment="all",
                    feed=DataFeed.IEX
                )
                bars = client.get_stock_bars(req).df
                if bars.empty:
                    for tk in remaining:
                        invalid.append(f"{tk} - no bars")
                    break
                for tk in remaining:
                    if tk not in bars.index.get_level_values(0):
                        invalid.append(f"{tk} - not returned")
                        continue
                    hist = bars.loc[tk]
                    if len(hist) < 180:
                        invalid.append(f"{tk} - <180d")
                        continue
                    ret = (float(hist["close"].iloc[-1]) / float(hist["close"].iloc[0])) - 1
                    price = float(hist["close"].iloc[-1])
                    results.append({"Ticker": tk, "Price": price, "12Mo Return %": ret * 100, "Float Mcap": 1e9 * (1 + ret)})
                break
            except Exception as e:
                msg = str(e)
                m = re.search(r"invalid symbol[: ]+([A-Z0-9\.\-\$]+)", msg, re.I)
                if m:
                    bad_sym = m.group(1).strip().upper().split("-")[0]
                    invalid.append(f"{bad_sym} - invalid")
                    remaining = [x for x in remaining if x!= bad_sym]
                    if not remaining:
                        break
                    continue
                if len(remaining) == 1:
                    invalid.append(f"{remaining[0]} - {msg[:80]}")
                    break
                mid = len(remaining) // 2
                remaining = remaining[:mid]
                continue
        prog.progress(min((batch_idx + 50) / len(tickers), 1.0))
    prog.empty()
    if results:
        df = pd.DataFrame(results).sort_values("12Mo Return %", ascending=False).head(top_n)
    else:
        df = pd.DataFrame()
    return df, invalid

if st.button("Calculate Momentum 100 - Alpaca", type="primary", disabled=st.session_state.running, use_container_width=True):
    if not API_KEY or not SECRET_KEY:
        error_box.error("Add keys in Secrets")
    else:
        st.session_state.running = True
        st.session_state.result = None
        error_box.empty()
        warn_box.empty()
        try:
            sd = datetime.combine(run_date - timedelta(days=395), datetime.min.time())
            ed = datetime.combine(run_date, datetime.min.time())
            df400, bad400 = calc_alpaca(t400[:100], 40, "S&P 400", sd, ed)
            df600, bad600 = calc_alpaca(t600[:150], 60, "S&P 600", sd, ed)
            if df400.empty and df600.empty:
                combined = pd.DataFrame()
            else:
                combined = pd.concat([df400, df600], ignore_index=True)
            if combined.empty:
                error_box.error("No data returned")
            else:
                combined["Weight %"] = combined["Float Mcap"] / combined["Float Mcap"].sum() * 100
                combined["Position $"] = combined["Float Mcap"] / combined["Float Mcap"].sum() * portfolio_value
                combined["Shares"] = (combined["Position $"] / combined["Price"]).astype(int)
                combined = combined.sort_values("Weight %", ascending=False).reset_index(drop=True)
                st.session_state.result = (combined, bad400 + bad600)
                error_box.empty()
                warn_box.empty()
                log_box.empty()
        except Exception as e:
            error_box.error(f"Error {e}")
        finally:
            st.session_state.running = False

if st.session_state.result:
    combined, bad = st.session_state.result
    st.divider()
    st.success(f"Ready - {len(combined)} stocks | ${portfolio_value:,.0f}")
    st.dataframe(combined[["Ticker", "Price", "12Mo Return %", "Weight %", "Position $", "Shares"]], use_container_width=True, hide_index=True, height=700)
    with st.expander(f"Invalid {len(bad)}"):
        st.dataframe(pd.DataFrame(bad, columns=["Reason"]), use_container_width=True)
    st.download_button("Download CSV", combined.to_csv(index=False).encode("utf-8"), f"momentum100_{run_date}.csv", "text/csv", type="primary", use_container_width=True)
