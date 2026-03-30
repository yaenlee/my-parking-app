import streamlit as st
import requests
import pandas as pd
import urllib3
import os
import concurrent.futures  # 🚀 導入多執行緒庫

# --- [1] 環境與安全性設定 ---
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(
    page_title="停車監控中心", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# --- [2] 初始化 Session State ---
if 'vehicle_list' not in st.session_state:
    st.session_state.vehicle_list = []

# --- [3] Callback 函式 ---
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

# --- [4] 核心查詢：單一城市小幫手 ---
def fetch_city_data(city, url, car, t_type, headers):
    """這是一個獨立的任務，負責問一個城市"""
    try:
        # 增加 timeout 到 10 秒，避免被某個慢速政府網站卡死
        resp = requests.get(url.format(car=car, type=t_type), headers=headers, timeout=10, verify=False)
        if resp.status_code == 200:
            data = resp.json()
            bills = data.get('Bills', [])
            amt = sum(b.get('Amount', 0) for b in bills)
            return city, f"🔴 {amt}元" if amt > 0 else "🟢 無", amt
        elif resp.status_code == 404:
            return city, "🟢 無", 0
    except:
        pass
    return city, "❌ 異常", 0

# --- [5] 核心查詢：多執行緒調度中心 ---
def fetch_data_fast(car_no, type_code):
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

    # 🚀 同時啟動 5 個執行緒 (Threads)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        # 建立任務
        future_to_city = {
            executor.submit(fetch_city_data, city, url, clean_car, type_code, headers): city 
            for city, url in CITY_CONFIG.items()
        }
        
        # 收集結果 (誰先跑完誰就先回來)
        for future in concurrent.futures.as_completed(future_to_city):
            city, status, amt = future.result()
            res[city] = status
            car_total += amt
            
    return res, car_total

# --- [6] UI 側邊欄 ---
with st.sidebar:
    st.header("⚙️ 監控清單管理")
    st.text_input("➕ 新增車號", key="temp_input", placeholder="例如: ABC-1234", on_change=None)
    
    c1, c2 = st.columns(2)
    with c1:
        st.button("確認新增", on_click=add_car_callback, use_container_width=True, type="primary")
    with c2:
        st.button("清空清單", on_click=clear_list_callback, use_container_width=True)
    
    st.divider()
    selected_targets = st.multiselect("🎯 選擇查詢對象", options=st.session_state.vehicle_list, default=st.session_state.vehicle_list)
    car_type = st.radio("車種", ["汽車", "機車"], horizontal=True)
    t_code = 'C' if car_type == "汽車" else 'M'
    start_btn = st.button("🚀 執行高速掃描", use_container_width=True)

    with st.expander("⚖️ 免責聲明"):
        st.caption("本程式為第三方介接工具，不儲存個資，正確資訊請以官網為準。")

# --- [7] 主畫面 ---
st.title("🚗 五都停車費高速監控中心")

if start_btn:
    if not selected_targets:
        st.warning("請先新增車號。")
    else:
        all_results = []
        grand_total = 0
        
        with st.spinner('⚡ 正在多執行緒同步查詢中...'):
            for car in selected_targets:
                # 調用加速版的查詢函式
                res, total = fetch_data_fast(car, t_code)
                all_results.append(res)
                grand_total += total
        
        m1, m2 = st.columns(2)
        m1.metric("監控數量", f"{len(selected_targets)} 台")
        m2.metric("待繳總額", f"{grand_total} 元", delta=f"{grand_total}元" if grand_total > 0 else None, delta_color="inverse")
        
        st.dataframe(pd.DataFrame(all_results).set_index("車號"), use_container_width=True) 
        if grand_total > 0: st.error("📢 偵測到未繳費項目！")
        else: st.success("✅ 狀態正常。")
else:
    st.info("💡 手機用戶：點擊左上角 『 > 』 展開選單。本版本已啟用「多執行緒加速」，查詢更快速！")

st.divider()
st.caption(f"Performance: Parallel Fetch Enabled | {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}")
