# import pandas as pd
# import matplotlib.pyplot as plt
# # df=pd.read_parquet(r'G:\thermal_dnep\data\processed\stage4\thermal\TAZB_city_thermal.parquet')
# # print(df.columns)
# # df1=df[['JalaliYear'
# #         ,'JalaliMonth'
# #         ,'Gas_m3'
# #         ,'BaseGas_m3'
# #         ,'TemperatureDependentGas_m3'
# #         ,'ThermalGas_m3']][df.JalaliYear==1401]
# # plt.plot(df1.JalaliMonth,df1.Gas_m3,label='total')
# # plt.plot(df1.JalaliMonth,df1.BaseGas_m3,label='base')
# # plt.plot(df1.JalaliMonth,
# #          df1.TemperatureDependentGas_m3,label='T_dependent')
# # plt.plot(df1.JalaliMonth,df1.ThermalGas_m3,label='ThermalGas')

# # plt.legend()
# # plt.show()


# df=pd.read_parquet(r'G:\thermal_dnep\data\processed\stage4\thermal\TAZB_feeder_heating.parquet')
# print(df.columns)
# df2=df[['JalaliYear'
#         , 'JalaliMonth'
#         , 'Gas_m3'
#         ,'ThermalGas_m3'
#         ,'CoolingShare'
#         ,'AllocatedHeating_kWh'
#         ,'ToolPGDSCode']][df.JalaliYear==1401]
# df2_1=df2[df2.ToolPGDSCode=='TAZB6T01']
# df2_2=df2[df2.ToolPGDSCode=='TAZB6T02']
# df2_3=df2[df2.ToolPGDSCode=='TAZB6T03']
# plt.figure()
# plt.plot(df2_1.JalaliMonth,df2_1.CoolingShare,label='01')
# plt.plot(df2_2.JalaliMonth,df2_2.CoolingShare,label='02')
# plt.plot(df2_3.JalaliMonth,df2_3.CoolingShare,label='03')

# plt.figure()
# plt.plot(df2_1.JalaliMonth,df2_1.AllocatedHeating_kWh,label='01')
# plt.plot(df2_2.JalaliMonth,df2_2.AllocatedHeating_kWh,label='02')
# plt.plot(df2_3.JalaliMonth,df2_3.AllocatedHeating_kWh,label='03')
# plt.legend()
# plt.show()

# import geopandas as gpd
# import pandas as pd
# from shapely.geometry import Point
# import requests


# def get_tehran_boundary():
#     """دریافت مرز شهر تهران از OpenStreetMap"""
#     url = "https://nominatim.openstreetmap.org/search"
#     params = {
#         "q": "Tehran, Iran",
#         "format": "geojson",
#         "polygon_geojson": 1,
#         "limit": 1
#     }
#     headers = {"User-Agent": "ThermalDNEP-Research/1.0"}
    
#     response = requests.get(url, params=params, headers=headers)
#     data = response.json()
    
#     # استخراج پلی‌گون مرز تهران
#     boundary = gpd.GeoDataFrame.from_features(data["features"])
#     return boundary.set_crs(epsg=4326)


# def classify_points_in_tehran(points_df, lat_col="lat", lon_col="lon"):
#     """
#     Parameters
#     ----------
#     points_df : pd.DataFrame
#         دیتافریم شامل ستون‌های مختصات
#     lat_col, lon_col : str
#         نام ستون‌های عرض و طول جغرافیایی
    
#     Returns
#     -------
#     pd.DataFrame با ستون جدید 'in_tehran' (True/False)
#     """
#     # دریافت مرز تهران
#     tehran = get_tehran_boundary()
    
#     # تبدیل نقاط به GeoDataFrame
#     geometry = [Point(xy) for xy in zip(points_df[lon_col], points_df[lat_col])]
#     points_gdf = gpd.GeoDataFrame(points_df, geometry=geometry, crs="EPSG:4326")
    
#     # بررسی قرارگیری هر نقطه درون پلی‌گون تهران
#     # sjoin بسیار سریع‌تر از حلقه است (برای 300 نقطه < 0.1 ثانیه)
#     joined = gpd.sjoin(points_gdf, tehran, how="left", predicate="within")
    
#     result = points_df.copy()
#     result["in_tehran"] = ~joined["index_right"].isna()
#     return result


# # نمونه 300 نقطه تصادفی حول تهران
# import numpy as np
# np.random.seed(42)
# points = pd.DataFrame({
#     "lat": np.random.uniform(35.5, 35.9, 300),
#     "lon": np.random.uniform(51.2, 51.6, 300)
# })

# result = classify_points_in_tehran(points)
# print(result["in_tehran"].value_counts())
# # True: نقاط داخل تهران | False: نقاط بیرون




import pandas as pd
# df=pd.read_parquet(r'G:\thermal_dnep\data\processed\stage3\cooling\tazb_cooling_estimation.parquet')
# print(df.columns)
# print(df.head())
# df2=pd.read_parquet(r'G:\thermal_dnep\data\processed\stage4\thermal\TAZB_feeder_heating.parquet')
# print(df2.columns)
# print(df2.head())

df=pd.read_parquet(r'G:\thermal_dnep\data\processed\stage5\network\TAZB6T01_ieee33_hourly_loads.parquet')
# df2=pd.read_parquet(r'G:\thermal_dnep\data\processed\stage3\cooling\tazb_cooling_estimation.parquet')