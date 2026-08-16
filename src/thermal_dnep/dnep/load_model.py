import pandas as pd
import numpy as np

from thermal_dnep.utils.dates import jalali_to_gregorian


def load_hourly_demand(parquet_path: str) -> pd.DataFrame:
    """
    خواندن فایل بار ساعتی.
    تاریخ شمسی (مثلاً 1401/12/17) به میلادی تبدیل می‌شود.
    """
    df = pd.read_parquet(parquet_path)

    required = {
        "Date",
        "Hour",
        "bus",
        "BaseLoadBus_MW",
        "CoolingLoadBus_MW",
        "HeatingLoadBus_MW",
    }

    missing = required - set(df.columns)

    if missing:
        raise ValueError(f"ستون‌های مفقود در فایل بار: {missing}")

    # تبدیل تاریخ شمسی به میلادی
    df["Date"] = df["Date"].apply(jalali_to_gregorian)
    df["Date"] = pd.to_datetime(df["Date"])

    return df


def compute_electrical_load(
    demand_df: pd.DataFrame,
    electrification_level: float = 0.30,
) -> pd.DataFrame:
    """
    محاسبه بار الکتریکی پایه.
    سرمایش و گرمایش خام حفظ می‌شوند؛ تبدیل با COP متغیر در مدل انجام می‌شود.
    """
    df = demand_df.copy()

    df["TotalElecLoad_MW"] = df["BaseLoadBus_MW"].copy()
    df["AlphaHeat"] = electrification_level

    return df


def aggregate_to_representative_periods(
    demand_df: pd.DataFrame,
    n_periods_per_year: int = 4,
) -> dict:
    """
    کاهش ساعات هر سال به n دوره نماینده با استفاده از KMeans.

    هر ساعت از سال یک نمونه برای خوشه‌بندی است.

    ویژگی‌های مورد استفاده برای خوشه‌بندی:

        1. TotalElecLoad_MW
        2. CoolingLoadBus_MW
        3. HeatingLoadBus_MW

    هر خوشه دارای یک مرکز است که سه مقدار بار نماینده را
    در خود نگه می‌دارد.

    وزن هر خوشه برابر نسبت تعداد ساعات عضو آن خوشه
    به کل ساعات همان سال است.

    نکته مهم:
    ساعات واقعی عضو خوشه فقط برای محاسبه وزن و نگهداری اطلاعات
    ذخیره می‌شوند و دیگر به عنوان TIME_INDEX مدل استفاده نمی‌شوند.

    ساختار اصلی خروجی periods حفظ شده است.
    """

    from sklearn.cluster import KMeans

    df = demand_df.copy()

    # ------------------------------------------------------------
    # سال میلادی
    # ------------------------------------------------------------
    df["Year"] = df["Date"].dt.year

    periods = {}

    years = sorted(df["Year"].unique())

    for year in years:

        # --------------------------------------------------------
        # داده‌های همان سال
        # --------------------------------------------------------
        df_year = df[df["Year"] == year].copy()

        # --------------------------------------------------------
        # شناسه یکتا برای هر ساعت
        # --------------------------------------------------------
        df_year["DateHour"] = (
            df_year["Date"].dt.strftime("%Y-%m-%d")
            + "_"
            + df_year["Hour"].astype(str)
        )

        # --------------------------------------------------------
        # ساخت یک رکورد برای هر ساعت کل سیستم
        #
        # هر ردیف = یک ساعت از سال
        # --------------------------------------------------------
        hourly_features = (
            df_year.groupby("DateHour")
            .agg(
                TotalElecLoad_MW=("TotalElecLoad_MW", "sum"),
                CoolingLoadBus_MW=("CoolingLoadBus_MW", "sum"),
                HeatingLoadBus_MW=("HeatingLoadBus_MW", "sum"),
                Date=("Date", "first"),
                Hour=("Hour", "first"),
            )
            .sort_values(["Date", "Hour"])
        )

        # --------------------------------------------------------
        # ویژگی‌های KMeans
        # --------------------------------------------------------
        feature_columns = [
            "TotalElecLoad_MW",
            "CoolingLoadBus_MW",
            "HeatingLoadBus_MW",
        ]

        hourly_features = hourly_features.dropna(
            subset=feature_columns
        )

        if hourly_features.empty:
            continue

        # --------------------------------------------------------
        # تعداد خوشه‌ها
        # --------------------------------------------------------
        n_clusters = min(
            n_periods_per_year,
            len(hourly_features),
        )

        # --------------------------------------------------------
        # ماتریس ویژگی
        # --------------------------------------------------------
        X = hourly_features[feature_columns].values

        # --------------------------------------------------------
        # KMeans
        # --------------------------------------------------------
        kmeans = KMeans(
            n_clusters=n_clusters,
            random_state=42,
            n_init=10,
        )

        labels = kmeans.fit_predict(X)

        hourly_features["Cluster"] = labels

        # --------------------------------------------------------
        # مراکز خوشه‌ها
        # --------------------------------------------------------
        cluster_centers = pd.DataFrame(
            kmeans.cluster_centers_,
            columns=feature_columns,
        )

        # --------------------------------------------------------
        # ساخت دوره‌های نماینده
        # --------------------------------------------------------
        for pid in range(n_clusters):

            mask = hourly_features["Cluster"] == pid

            cluster_data = hourly_features.loc[mask].copy()

            if cluster_data.empty:
                continue

            # ----------------------------------------------------
            # ساعات واقعی عضو خوشه
            #
            # فقط برای اطلاعات و محاسبه وزن نگهداری می‌شوند.
            # این لیست دیگر TIME_INDEX مدل نیست.
            # ----------------------------------------------------
            member_hours = cluster_data["Hour"].tolist()

            # member_dates = cluster_data["DateHour"].tolist()
            member_dates = cluster_data.index.tolist()
            # ----------------------------------------------------
            # وزن خوشه
            # ----------------------------------------------------
            weight = len(cluster_data) / len(hourly_features)

            # ----------------------------------------------------
            # مرکز خوشه
            #
            # این سه مقدار، بار نماینده کل سیستم هستند.
            # ----------------------------------------------------
            center = cluster_centers.iloc[pid]

            load_profile = {
                "TotalElecLoad_MW": float(
                    center["TotalElecLoad_MW"]
                ),
                "CoolingLoadBus_MW": float(
                    center["CoolingLoadBus_MW"]
                ),
                "HeatingLoadBus_MW": float(
                    center["HeatingLoadBus_MW"]
                ),
            }

            # ----------------------------------------------------
            # پروفایل باس‌ها در این خوشه
            #
            # برای هر باس، میانگین بار ساعات عضو خوشه محاسبه می‌شود.
            # ----------------------------------------------------
            df_cluster = df_year[
                df_year["DateHour"].isin(member_dates)
            ]

            bus_load_profile = (
                df_cluster.groupby("bus")
                .agg(
                    BaseLoadBus_MW=(
                        "BaseLoadBus_MW",
                        "mean",
                    ),
                    TotalElecLoad_MW=(
                        "TotalElecLoad_MW",
                        "mean",
                    ),
                    CoolingLoadBus_MW=(
                        "CoolingLoadBus_MW",
                        "mean",
                    ),
                    HeatingLoadBus_MW=(
                        "HeatingLoadBus_MW",
                        "mean",
                    ),
                )
            )

            # ----------------------------------------------------
            # برای سازگاری با ساختار قبلی:
            #
            # hours همچنان ساعات واقعی عضو خوشه است.
            #
            # اما representative_hour مشخص می‌کند که این خوشه
            # فقط یک timestep نماینده در مدل دارد.
            # ----------------------------------------------------
            periods[(year, pid)] = {
                "year": year,

                # ساعات واقعی عضو خوشه
                "hours": member_hours,

                # تعداد اعضای خوشه
                "n_hours": len(cluster_data),

                # تاریخ/ساعت واقعی اعضای خوشه
                "member_dates": member_dates,

                # وزن خوشه
                "weight": weight,

                # مرکز خوشه
                "load_profile": load_profile,

                # پروفایل بار در سطح باس
                "bus_load_profile": bus_load_profile,

                # فقط یک timestep نماینده
                "representative_hour": 0,
            }

    # ------------------------------------------------------------
    # گزارش خلاصه خوشه‌بندی
    # ------------------------------------------------------------
    print()
    print("=" * 70)
    print("REPRESENTATIVE PERIOD SUMMARY")
    print("=" * 70)

    for year in years:

        year_periods = [
            (yp, pdata)
            for yp, pdata in periods.items()
            if yp[0] == year
        ]

        if not year_periods:
            continue

        total_hours = sum(
            pdata["n_hours"]
            for _, pdata in year_periods
        )

        print(
            f"  Year {year}: "
            f"{len(year_periods)} periods, "
            f"{total_hours:,} hours"
        )

        for (y, pid), pdata in sorted(year_periods):

            print(
                f"      Period {pid}: "
                f"{pdata['n_hours']:,} hours, "
                f"weight={pdata['weight']:.4f}"
            )

    print("=" * 70)
    print()

    return periods