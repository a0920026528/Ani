import requests
import json
from datetime import datetime, timedelta
from tabulate import tabulate

# ==================== 請填入你自己的金鑰 ====================
CWA_AUTHORIZATION_KEY = 'CWA-CC3BECC7-0AC2-4011-95DC-B378ED754694'
MOENV_API_KEY = 'e6b4be90-7f43-4c98-ab3a-f3cbe2bd9e93'
# ============================================================

# 地點映射（鄉鎮代碼請參考：https://opendata.cwa.gov.tw/opendatadoc/Opendata_City.pdf）
LOCATION_MAP = {
    '新莊區': {'tid': 'F-D0047-063', 'locationName': '新莊區', 'aqi_site': '57'},  # 新北市
    '林口區': {'tid': 'F-D0047-063', 'locationName': '林口區', 'aqi_site': '31'},
    # 可自行擴充其他鄉鎮
}

PERIODS = ['早上', '下午', '晚上']
DEFAULT_ITEMS = ['氣溫', '降雨機率', '舒適度', '空氣品質', '風力']

def parse_query(query):
    query = query.lower()
    locations = [loc for loc in LOCATION_MAP if loc in query]
    if not locations:
        locations = list(LOCATION_MAP.keys())  # 預設

    if any(w in query for w in ['明日', '明天']):
        periods = ['明日']
    else:
        periods = ['今日']

    items = [item for item in DEFAULT_ITEMS if item in query]
    if not items:
        items = DEFAULT_ITEMS

    return {'locations': locations, 'periods': periods, 'items': items}

def get_town_weather(location_name):
    """
    改用最新版 36小時鄉鎮預報 F-D0047-093
    """
    url = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-D0047-093"
    params = {
        'Authorization': CWA_AUTHORIZATION_KEY,
        'locationName': location_name,
        'elementName': 'Wx,PoP12h,MinT,MaxT,CI,WS',  # PoP12h 還是12小時為單位
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if data['success'] != 'true':
        raise Exception("氣象API回傳失敗")
    
    location = data['records']['locations'][0]['location'][0]
    return location

def extract_period_data(weather_elements, today=True):
    """
    配合 F-D0047-093 的 12小時時段（每12小時一筆，共7筆）
    時段定義（startTime）：
    0: 今天 06-18
    1: 今天 18-明天06
    2: 明天 06-18
    3: 明天 18-後天06
    ...
    """
    result = {'早上': {}, '下午': {}, '晚上': {}}
    
    # 建立 elementName → time 列表
    element_dict = {el['elementName']: el['time'] for el in weather_elements}
    
    if today:
        morning_idx = 0   # 今天早上 06-18
        evening_idx = 1   # 今天下午 + 晚上 18-明天06（共用）
    else:
        morning_idx = 2   # 明天早上
        evening_idx = 3   # 明天下午 + 晚上

    # 早上
    m = morning_idx
    result['早上']['氣溫'] = f"{element_dict['MinT'][m]['dataValue']}～{element_dict['MaxT'][m]['dataValue']}°C"
    pop = element_dict['PoP12h'][m]['dataValue']
    result['早上']['降雨機率'] = f"{pop}%" if pop != "-1" else "0%"
    result['早上']['舒適度'] = element_dict['CI'][m]['dataValue']
    result['早上']['天氣現象'] = element_dict['Wx'][m]['measures'][1]['value']  # 中文
    result['早上']['風力'] = f"{element_dict['WS'][m]['dataValue']}級"

    # 下午 & 晚上（共用同一個12小時時段）
    e = evening_idx
    temp = f"{element_dict['MinT'][e]['dataValue']}～{element_dict['MaxT'][e]['dataValue']}°C"
    pop = element_dict['PoP12h'][e]['dataValue']
    pop_str = f"{pop}%" if pop != "-1" else "0%"
    result['下午']['氣溫'] = result['晚上']['氣溫'] = temp
    result['下午']['降雨機率'] = result['晚上']['降雨機率'] = pop_str
    result['下午']['舒適度'] = result['晚上']['舒適度'] = element_dict['CI'][e]['dataValue']
    result['下午']['天氣現象'] = result['晚上']['天氣現象'] = element_dict['Wx'][e]['measures'][1]['value']
    result['下午']['風力'] = result['晚上']['風力'] = f"{element_dict['WS'][e]['dataValue']}級"

    return result
def get_aqi_data(site_id):
    url = "https://data.moenv.gov.tw/api/v2/aqx_p_432"
    params = {'api_key': MOENV_API_KEY, 'format': 'json', 'limit': 1000}
    try:
        data = requests.get(url, params=params, timeout=10).json()
        for r in data['records']:
            if r['siteid'] == site_id:
                return f"AQI {r['aqi']} ({r['status']})"
    except:
        pass
    return "AQI 資料取得失敗"

def query_weather(user_query):
    parsed = parse_query(user_query)
    locations = parsed['locations']
    periods = parsed['periods']
    items = parsed['items']

    table = []
    headers = ['地區', '日期', '時段'] + items

    for loc in locations:
        info = LOCATION_MAP[loc]
        town_data = get_town_weather(info['locationName'])

        for period in periods:
            is_today = (period == '今日')
            period_data = extract_period_data(town_data['weatherElement'], today=is_today)

            aqi = get_aqi_data(info['aqi_site'])

            for time_slot in PERIODS:
                row = [loc, period, time_slot]
                slot_data = period_data[time_slot]
                for item in items:
                    if item == '空氣品質':
                        row.append(aqi)
                    elif item == '氣溫':
                        row.append(slot_data.get('氣溫', '-'))
                    elif item == '降雨機率':
                        row.append(slot_data.get('降雨機率', '-'))
                    elif item == '舒適度':
                        row.append(slot_data.get('舒適度', '-'))
                    elif item == '風力':
                        row.append(slot_data.get('風力', '-'))
                    else:
                        row.append('-')
                table.append(row)

    print(tabulate(table, headers=headers, tablefmt='grid'))

# ==================== 互動測試 ====================
if __name__ == "__main__":
    print("新北市天氣查詢小幫手（支援新莊、林口）")
    while True:
        q = input("\n請問想查什麼？（例如：新莊今天氣溫和空氣 / 林口明天降雨）或輸入 quit 離開：")
        if q.lower() in ['quit', 'exit', 'q']:
            break
        try:
            query_weather(q)
        except Exception as e:
            print(f"發生錯誤：{e}")
