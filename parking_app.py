import streamlit as st
import requests
import pandas as pd
import urllib3
import os
import concurrent.futures
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- [1] 環境與安全性設定 ---
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(
    page_title="停車監控中心", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# --- [2] 建立具備「自動重試」功能的 Session ---
def create_retry_session():
    session = requests.Session()
    # 設定重試策略：總共重試 2 次，針對 500/502/503/504 等伺服器錯誤自動重發
    retry_strategy = Retry(
        total=2,
        backoff_factor=1,  # 失敗後等待 1 秒再試
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

# --- [3] 初始化 Session State ---
if 'vehicle_list' not in st.session_state:
    st.session_state.vehicle_list = []

# --- [4] Callback 函式 ---
def add_car_callback():
    raw_input = st.session_state.temp_input.upper().strip()
    if raw_input:
        new_cars = raw_input.replace(',', ' ').replace('，', ' ').replace('\n', ' ').split()
        for car in new_cars:
            car = car.strip()
            if car and car not in st.session_state.vehicle_list:
                st.session_state.vehicle_list.append(car)
        st.session_state.temp_input = "" 

def clear_list_callback():
    st.session_state.vehicle_list = []

# --- [5] 核心查詢：單一城市任務 ---
def fetch_city_data(session, city, url, car, t_type, headers):
    try:
        # 使用具備重試機制的 session 進行請求
        resp = session.get(
            url.format(car=car, type=t_type), 
            headers=headers, 
            timeout=12, 
            verify=False
        )
        if resp.status_code == 200:
            data = resp.json()
            bills = data.get('Bills', [])
            amt = sum(b.get('Amount', 0) for b in bills)
            return city, f"🔴 {amt}元" if amt > 0 else "🟢 無", amt
        elif resp.status_code == 404:
            return city, "🟢 無", 0
    except Exception:
        pass
    return city, "❌ 異常", 0

# --- [6] 核心查詢：加速調度中心 ---
def fetch_data_robust(car_no, type_code):
    clean_car = car_no.replace('-', '').strip()
    res = {"車號": car_no}
    car_total = 0
    
    CITY_CONFIG = {
        "台北市": "https://trafficapi.pma.gov.taipei/Parking/PayBill/CarID/{car}/CarType/{type}",
        "新北市": "https://trafficapi.traffic.ntpc.gov.tw/Parking/PayBill/CarID/{car}/CarType/{type}",
        "桃園市": "https://bill-epark.tycg.gov.tw/Parking/PayBill/CarID/{car}/CarType/{type}",
        "台南市": "https://citypark.tainan.gov.tw/Parking/PayBill/CarID/{car}/CarType/{type}",
        "高雄市": "https://kpp.tbkc.gov.tw/Parking/PayBill/CarID/{car}/CarType/{type}"
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    }

    # 建立重試 Session
    session = create_retry_session()

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_city = {
            executor.submit(fetch_city_data, session, city, url, clean_car, type_code, headers): city 
            for city, url in CITY_CONFIG.items()
        }
        
        for future in concurrent.futures.as_completed(future_to_city):
            city, status, amt = future.result()
            res[city] = status
            car_total += amt
            
    return res, car_total

# --- [7] UI 側邊欄 ---
with st.sidebar:
    st.header("⚙️ 監控清單管理")
    st.text_input("➕ 新增車號 (可批量)", key="temp_input", placeholder="例如: ABC-1234")
    
    c1, c2 = st.columns(2)
    with c1:
        st.button("確認新增", on_click=add_car_callback, use_container_width=True, type="primary")
    with c2:
        st.button("清空清單", on_click=clear_list_callback, use_container_width=True)
    
    st.divider()
    selected_targets = st.multiselect("🎯 選擇查詢對象", options=st.session_state.vehicle_list, default=st.session_state.vehicle_list)
    car_type = st.radio("車種", ["汽車", "機車"], horizontal=True)
    t_code = 'C' if car_type == "汽車" else 'M'
    start_btn = st.button("🚀 執行高速穩定掃描", use_container_width=True)

    with st.expander("⚖️ 免責聲明"):
        st.caption("本工具已啟用自動重試機制以提升穩定性。若顯示異常，請稍後再試。")

# --- [8] 主畫面 ---
st.title("🚗 五都停車費監控中心 (穩定加速版)")

if start_btn:
    if not selected_targets:
        st.warning("請先新增車號。")
    else:
        all_results = []
        grand_total = 0
        
        with st.spinner('📡 正在連線政府 API (含自動重試機制)...'):
            for car in selected_targets:
                res, total = fetch_data_robust(car, t_code)
                all_results.append(res)
                grand_total += total
        
        m1, m2 = st.columns(2)
        m1.metric("監控數量", f"{len(selected_targets)} 台")
        m2.metric("待繳總額", f"{grand_total} 元", delta=f"{grand_total}元" if grand_total > 0 else None, delta_color="inverse")
        
        st.dataframe(pd.DataFrame(all_results).set_index("車號"), use_container_width=True) 
        if grand_total > 0: st.error("📢 偵測到未繳費項目！")
        else: st.success("✅ 狀態正常。")
else:
    st.info("💡 提示：本版本已優化連線穩定性，若政府伺服器短暫忙碌，程式會自動嘗試重新連線。")

st.divider()
st.caption(f"Stability: Retry Strategy Enabled | {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}")
