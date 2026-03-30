import streamlit as st
import requests
import pandas as pd
import urllib3
import os
import time
import random
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

# --- [2] 建立具備高度彈性的 Session ---
def create_robust_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=3,                # 增加到 3 次重試
        backoff_factor=1.5,     # 失敗後等待更久 (1.5s, 3s, 6s)
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
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

# --- [5] 核心查詢：模擬真人行為的小幫手 ---
def fetch_city_data(session, city, url, car, t_type):
    # 🚀 加入隨機微延遲，避免美國機房的請求太過整齊而被防火牆盯上
    time.sleep(random.uniform(0.1, 0.4))
    
    # 針對各城市偽裝專屬的 Referer (來源網址)
    city_referer = {
        "台北市": "https://parking.pma.gov.taipei/",
        "新北市": "https://parking.ntpc.gov.tw/",
        "桃園市": "https://parking.tycg.gov.tw/",
        "台南市": "https://citypark.tainan.gov.tw/",
        "高雄市": "https://kpp.tbkc.gov.tw/"
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': city_referer.get(city, "https://www.google.com.tw/"),
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive'
    }
    
    try:
        resp = session.get(
            url.format(car=car, type=t_type), 
            headers=headers, 
            timeout=15, # 增加超時上限
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

# --- [6] 核心查詢：降速求穩調度中心 ---
def fetch_data_cloud_optimized(car_no, type_code):
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
    
    session = create_robust_session()

    # 🚀 將 max_workers 從 5 降到 3，避免跨境連線瞬間併發過高被擋
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(fetch_city_data, session, city, url, clean_car, type_code) 
                   for city, url in CITY_CONFIG.items()]
        
        for future in concurrent.futures.as_completed(futures):
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
    start_btn = st.button("🚀 執行穩定加速掃描", use_container_width=True)

    with st.expander("⚖️ 免責聲明"):
        st.caption("由於雲端伺服器位於海外，連線政府網站較慢。若顯示異常，請重新點擊掃描。")

# --- [8] 主畫面 ---
st.title("🚗 五都停車費監控中心 (雲端優化版)")

if start_btn:
    if not selected_targets:
        st.warning("請先新增車號。")
    else:
        all_results = []
        grand_total = 0
        
        with st.spinner('📡 正在跨海連線政府 API (降速求穩模式)...'):
            for car in selected_targets:
                res, total = fetch_data_cloud_optimized(car, t_code)
                all_results.append(res)
                grand_total += total
        
        m1, m2 = st.columns(2)
        m1.metric("監控數量", f"{len(selected_targets)} 台")
        m2.metric("待繳總額", f"{grand_total} 元", delta=f"{grand_total}元" if grand_total > 0 else None, delta_color="inverse")
        
        st.dataframe(pd.DataFrame(all_results).set_index("車號"), use_container_width=True) 
        if grand_total > 0: st.error("📢 偵測到未繳費項目！")
        else: st.success("✅ 狀態正常。")
else:
    st.info("💡 雲端部署提示：本版本已針對海外連線進行優化，減少被防火牆封鎖的機率。")

st.divider()
st.caption(f"Stability: Cloud Optimized (Workers=3) | {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}")
