import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point
import requests
from pathlib import Path
import matplotlib.pyplot as plt
from transliterate import translit


CITY_NAME_MAP = {
    "تهران": "Tehran",
    "اصفهان": "Isfahan",
    "مشهد": "Mashhad",
    "شیراز": "Shiraz",
    "تبریز": "Tabriz",
    "کرج": "Karaj",
    "قم": "Qom",
    "اهواز": "Ahvaz",
    "رشت": "Rasht",
    "کرمانشاه": "Kermanshah",
}

# --------------------------------------------------
# مسیر نسبی روت پروژه
# --------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[3]
CITY_BOUNDARY_DIR = PROJECT_ROOT / "data" / "raw" / "city"


def get_city_boundary(
    city_name: str,
    country: str = "Iran",
    cache_dir: Path = None,
):
    """
    دریافت مرز یک شهر از OpenStreetMap با پشتیبانی از cache.
    
    Parameters
    ----------
    city_name : str
        نام شهر به انگلیسی، مثلاً "Tehran", "Isfahan", "Mashhad"
    country : str
        نام کشور برای جلوگیری از ابهام
    cache_dir : Path
        پوشه ذخیره‌سازی فایل‌های کش
    
    Returns
    -------
    gpd.GeoDataFrame
        پلی‌گون مرز شهر
    """
    city_name = normalize_city_name(city_name)
    if cache_dir is None:
        cache_dir = CITY_BOUNDARY_DIR
    
    # نام فایل کش بر اساس نام شهر (حروف کوچک، بدون فاصله)
    safe_name = city_name.strip().lower().replace(" ", "_")
    cache_file = Path(cache_dir) / f"{safe_name}_boundary.geojson"
    
    # --------------------------------------------------
    # خواندن از کش در صورت وجود
    # --------------------------------------------------
    if cache_file.exists():
        print(f"✅ خواندن مرز {city_name} از کش: {cache_file}")
        return gpd.read_file(cache_file)
    
    # --------------------------------------------------
    # دانلود از OpenStreetMap
    # --------------------------------------------------
    print(f"⬇️ دانلود مرز {city_name} از OpenStreetMap...")
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": f"{city_name}, {country}",
        "format": "geojson",
        "polygon_geojson": 1,
        "limit": 1
    }
    headers = {"User-Agent": "ThermalDNEP-Research/1.0"}
    
    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    data = response.json()
    
    if not data.get("features"):
        raise ValueError(
            f"مرزی برای '{city_name}, {country}' یافت نشد. "
            "نام شهر را به انگلیسی و صحیح وارد کنید."
        )
    
    boundary = gpd.GeoDataFrame.from_features(data["features"])
    boundary = boundary.set_crs(epsg=4326)
    
    # --------------------------------------------------
    # ذخیره در کش
    # --------------------------------------------------
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    boundary.to_file(cache_file, driver="GeoJSON")
    print(f"💾 مرز {city_name} ذخیره شد در: {cache_file}")
    
    return boundary


def classify_points_in_city(
    points_df: pd.DataFrame,
    city_name: str,
    country: str = "Iran",
    lat_col: str = "lat",
    lon_col: str = "lon",
    cache_dir: Path = None,
):
    """
    تشخیص نقاط داخل یک شهر مشخص.
    
    Returns
    -------
    (pd.DataFrame, gpd.GeoDataFrame)
        دیتافریم با ستون 'in_city' و مرز شهر
    """
    columns0=points_df.columns
    points_df = points_df.rename(columns=str.lower)
    city_boundary = get_city_boundary(city_name, country, cache_dir)
    
    geometry = [Point(xy) for xy in zip(points_df[lon_col], points_df[lat_col])]
    points_gdf = gpd.GeoDataFrame(
        points_df, 
        geometry=geometry, 
        crs="EPSG:4326"
    )
    
    joined = gpd.sjoin(points_gdf, city_boundary, how="left", predicate="within")
    
    result = points_df.copy()
    result.columns=columns0
    result["in_city"] = ~joined["index_right"].isna()
    
    return result, city_boundary

def in_city(  
    points_df: pd.DataFrame,
    city_name: str):
    result, _ = classify_points_in_city(points_df, city_name)
    return result[result.in_city].drop(columns='in_city')


def normalize_city_name(city_name: str) -> str:
    """تبدیل نام فارسی به انگلیسی با fallback به transliteration"""
    # بررسی در دیکشنری
    if city_name in CITY_NAME_MAP:
        return CITY_NAME_MAP[city_name]
    
    # تلاش برای transliteration
    try:
        english_name = translit(city_name, 'fa', reversed=True)
        return english_name
    except:
        # اگر هیچکدام کار نکرد، همان نام را برگردان
        return city_name




def plot_city_and_points(
    points_df: pd.DataFrame,
    city_boundary: gpd.GeoDataFrame,
    city_name: str,
    lat_col: str = "lat",
    lon_col: str = "lon",
    figsize: tuple = (12, 10),
):
    """رسم بصری مرز شهر و نقاط"""
    fig, ax = plt.subplots(figsize=figsize)
    
    city_boundary.plot(
        ax=ax,
        color="lightyellow",
        edgecolor="darkred",
        linewidth=2,
        label=f"مرز {city_name}"
    )
    
    inside = points_df[points_df["in_city"] == True]
    outside = points_df[points_df["in_city"] == False]
    
    if not inside.empty:
        ax.scatter(
            inside[lon_col], inside[lat_col],
            c="green", marker="o", s=30, alpha=0.7,
            label=f"داخل شهر ({len(inside)} نقطه)"
        )
    
    if not outside.empty:
        ax.scatter(
            outside[lon_col], outside[lat_col],
            c="red", marker="x", s=50, linewidths=2, alpha=0.7,
            label=f"خارج شهر ({len(outside)} نقطه)"
        )
    
    ax.set_title(f"نقاط داخل و خارج {city_name}", fontsize=14, fontweight="bold")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.legend(loc="best", fontsize=11)
    ax.grid(True, alpha=0.3, linestyle="--")
    
    plt.tight_layout()
    plt.show()



# import numpy as np

# # --------------------------------------------------
# # تهران
# # --------------------------------------------------
# points_tehran = pd.DataFrame({
#     "lat": np.random.uniform(35.5, 35.9, 300),
#     "Lon": np.random.uniform(51.2, 51.6, 300),
# })

# result_th, boundary_th = classify_points_in_city(points_tehran, "تهران")
# plot_city_and_points(result_th, boundary_th, "Tehran")


# # --------------------------------------------------
# # اصفهان
# # --------------------------------------------------
# points_isfahan = pd.DataFrame({
#     "lat": np.random.uniform(32.5, 32.8, 200),
#     "lon": np.random.uniform(51.5, 51.8, 200),
# })

# result_es, boundary_es = classify_points_in_city(points_isfahan, "Isfahan")
# plot_city_and_points(result_es, boundary_es, "Isfahan")