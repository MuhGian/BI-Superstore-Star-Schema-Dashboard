import os
import streamlit as st
import pandas as pd
import json
import io
import matplotlib.pyplot as plt

st.set_page_config(
    page_title="BI Superstore Star Schema",
    page_icon="📊",
    layout="wide"
)

# =========================================================
# HELPERS
# =========================================================
def clean_postal(x):
    if pd.isna(x):
        return "Unknown"
    s = str(x).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s

@st.cache_data
def load_and_prepare_raw(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    # Parse dates (DD/MM/YYYY)
    df["Order Date"] = pd.to_datetime(df["Order Date"], dayfirst=True, errors="coerce")
    df["Ship Date"]  = pd.to_datetime(df["Ship Date"],  dayfirst=True, errors="coerce")

    # Postal Code -> string
    df["Postal Code"] = df["Postal Code"].apply(clean_postal)

    # Drop logical duplicates (ignore Row ID)
    cols_no_rowid = [c for c in df.columns if c != "Row ID"]
    df = df.loc[~df.duplicated(subset=cols_no_rowid, keep="first")].copy()

    return df

@st.cache_data
def build_star_schema(df: pd.DataFrame):
    # Resolve product name inconsistencies: most frequent name per Product ID
    name_counts = (
        df.groupby(["Product ID", "Product Name"])
          .size()
          .reset_index(name="n")
          .sort_values(["Product ID", "n", "Product Name"], ascending=[True, False, True])
    )
    mode_name = (
        name_counts.drop_duplicates("Product ID")[["Product ID", "Product Name"]]
                  .set_index("Product ID")["Product Name"]
    )

    # dim_date (cover both order & ship dates)
    min_all = min(df["Order Date"].min(), df["Ship Date"].min())
    max_all = max(df["Order Date"].max(), df["Ship Date"].max())
    date_range = pd.date_range(min_all, max_all, freq="D")

    dim_date = pd.DataFrame({"full_date": date_range})
    dim_date["date_key"] = dim_date["full_date"].dt.strftime("%Y%m%d").astype(int)
    dim_date["day"] = dim_date["full_date"].dt.day
    dim_date["month"] = dim_date["full_date"].dt.month
    dim_date["month_name"] = dim_date["full_date"].dt.strftime("%B")
    dim_date["quarter"] = dim_date["full_date"].dt.quarter
    dim_date["year"] = dim_date["full_date"].dt.year
    dim_date["week_of_year"] = dim_date["full_date"].dt.isocalendar().week.astype(int)

    date_to_key = dict(zip(dim_date["full_date"].dt.date, dim_date["date_key"]))

    # dim_customer
    dim_customer = (
        df[["Customer ID", "Customer Name", "Segment"]]
          .drop_duplicates()
          .sort_values("Customer ID")
          .reset_index(drop=True)
    )
    dim_customer.insert(0, "customer_key", range(1, len(dim_customer) + 1))
    cust_to_key = dict(zip(dim_customer["Customer ID"], dim_customer["customer_key"]))

    # dim_product
    dim_product = (
        df[["Product ID", "Category", "Sub-Category"]]
          .drop_duplicates()
          .sort_values("Product ID")
          .reset_index(drop=True)
          .rename(columns={"Sub-Category": "sub_category"})
    )
    dim_product["product_name"] = dim_product["Product ID"].map(mode_name)
    dim_product.insert(0, "product_key", range(1, len(dim_product) + 1))
    prod_to_key = dict(zip(dim_product["Product ID"], dim_product["product_key"]))

    # dim_region
    geo_cols = ["Country", "Region", "State", "City", "Postal Code"]
    dim_region = (
        df[geo_cols]
          .drop_duplicates()
          .sort_values(geo_cols)
          .reset_index(drop=True)
    )
    dim_region.insert(0, "region_key", range(1, len(dim_region) + 1))

    geo_to_key = {}
    for row in dim_region.itertuples(index=False):
        # (region_key, Country, Region, State, City, Postal Code)
        region_key = row[0]
        geo_tuple = tuple(row[1:])
        geo_to_key[geo_tuple] = region_key

    # dim_ship_mode
    dim_ship_mode = (
        df[["Ship Mode"]]
          .drop_duplicates()
          .sort_values("Ship Mode")
          .reset_index(drop=True)
          .rename(columns={"Ship Mode": "ship_mode"})
    )
    dim_ship_mode.insert(0, "ship_mode_key", range(1, len(dim_ship_mode) + 1))
    ship_to_key = dict(zip(dim_ship_mode["ship_mode"], dim_ship_mode["ship_mode_key"]))

    # fact_sales (grain: 1 row = 1 order line)
    fact = df.copy()
    fact["order_date_key"] = fact["Order Date"].dt.date.map(date_to_key)
    fact["ship_date_key"]  = fact["Ship Date"].dt.date.map(date_to_key)
    fact["customer_key"] = fact["Customer ID"].map(cust_to_key)
    fact["product_key"]  = fact["Product ID"].map(prod_to_key)
    fact["ship_mode_key"] = fact["Ship Mode"].map(ship_to_key)

    geo_tuples = list(zip(fact["Country"], fact["Region"], fact["State"], fact["City"], fact["Postal Code"]))
    fact["region_key"] = [geo_to_key[t] for t in geo_tuples]

    fact_sales = fact[[
        "Row ID", "Order ID",
        "order_date_key", "ship_date_key",
        "customer_key", "product_key", "region_key", "ship_mode_key",
        "Sales"
    ]].rename(columns={
        "Row ID": "row_id",
        "Order ID": "order_id",
        "Sales": "sales_amount"
    }).reset_index(drop=True)

    fact_sales.insert(0, "sales_id", range(1, len(fact_sales) + 1))

    return dim_date, dim_customer, dim_product, dim_region, dim_ship_mode, fact_sales

def make_summary_json(df_filtered: pd.DataFrame) -> dict:
    total_sales = float(df_filtered["Sales"].sum())

    sales_by_category = (
        df_filtered.groupby("Category")["Sales"].sum().sort_values(ascending=False)
    )
    sales_by_category = {k: round(float(v), 2) for k, v in sales_by_category.items()}

    top_products = (
        df_filtered.groupby("Product Name")["Sales"].sum()
                   .sort_values(ascending=False).head(10)
    )
    top_products_list = [{"name": idx, "sales": round(float(val), 2)} for idx, val in top_products.items()]

    monthly = (
        df_filtered.assign(month=df_filtered["Order Date"].dt.to_period("M").astype(str))
                   .groupby("month")["Sales"].sum().reset_index().sort_values("month")
    )
    monthly_sales_trend = [{"month": r["month"], "sales": round(float(r["Sales"]), 2)} for _, r in monthly.iterrows()]

    return {
        "total_sales": round(total_sales, 2),
        "sales_by_category": sales_by_category,
        "top_products": top_products_list,
        "monthly_sales_trend": monthly_sales_trend
    }

def to_excel_bytes(raw_df, dim_date, dim_customer, dim_product, dim_region, dim_ship_mode, fact_sales) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        raw_df.to_excel(writer, sheet_name="raw_train", index=False)
        dim_date.to_excel(writer, sheet_name="dim_date", index=False)
        dim_customer.to_excel(writer, sheet_name="dim_customer", index=False)
        dim_product.to_excel(writer, sheet_name="dim_product", index=False)
        dim_region.to_excel(writer, sheet_name="dim_region", index=False)
        dim_ship_mode.to_excel(writer, sheet_name="dim_ship_mode", index=False)
        fact_sales.to_excel(writer, sheet_name="fact_sales", index=False)
    return output.getvalue()

# ✅ NEW: save Excel to disk (auto-save)
def save_star_schema_excel(filepath, raw_df, dim_date, dim_customer, dim_product, dim_region, dim_ship_mode, fact_sales):
    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        raw_df.to_excel(writer, sheet_name="raw_train", index=False)
        dim_date.to_excel(writer, sheet_name="dim_date", index=False)
        dim_customer.to_excel(writer, sheet_name="dim_customer", index=False)
        dim_product.to_excel(writer, sheet_name="dim_product", index=False)
        dim_region.to_excel(writer, sheet_name="dim_region", index=False)
        dim_ship_mode.to_excel(writer, sheet_name="dim_ship_mode", index=False)
        fact_sales.to_excel(writer, sheet_name="fact_sales", index=False)

# ✅ NEW: save Normalization (1NF–3NF) to disk (auto-save)
def save_normalization_excel(filepath, raw_df, dim_date, dim_customer, dim_product, dim_region, dim_ship_mode, fact_sales):
    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        # 1NF: data mentah yang sudah dibersihkan (atomic + konsisten format)
        raw_df.to_excel(writer, sheet_name="1NF_raw", index=False)

        # 2NF: pisahkan entitas utama (hilangkan redundansi sebagian)
        dim_customer.to_excel(writer, sheet_name="2NF_customer", index=False)
        dim_product.to_excel(writer, sheet_name="2NF_product", index=False)
        dim_region.to_excel(writer, sheet_name="2NF_region", index=False)

        # 3NF: tabel fully normalized (dimensi + fact dengan FK)
        dim_date.to_excel(writer, sheet_name="3NF_dim_date", index=False)
        dim_ship_mode.to_excel(writer, sheet_name="3NF_dim_ship_mode", index=False)
        fact_sales.to_excel(writer, sheet_name="3NF_fact_sales", index=False)

# =========================================================
# LOAD DATA
# =========================================================
st.title("📊 BI Superstore Star Schema Builder Dashboard")

csv_path = "train.csv"
raw = load_and_prepare_raw(csv_path)

# =========================================================
# ✅ NEW: AUTO CREATE STAR SCHEMA EXCEL (ON FIRST RUN)
# =========================================================
STAR_SCHEMA_FILE = "train_star_schema.xlsx"
STAR_SCHEMA_PATH = os.path.join(os.getcwd(), STAR_SCHEMA_FILE)

if not os.path.exists(STAR_SCHEMA_PATH):
    dim_date, dim_customer, dim_product, dim_region, dim_ship_mode, fact_sales = build_star_schema(raw)
    save_star_schema_excel(
        STAR_SCHEMA_PATH,
        raw,
        dim_date,
        dim_customer,
        dim_product,
        dim_region,
        dim_ship_mode,
        fact_sales
    )

# =========================================================
# ✅ NEW: AUTO CREATE NORMALIZATION EXCEL (1NF–2NF–3NF)
# =========================================================
NORMALIZATION_FILE = "normalisasi_superstore.xlsx"
NORMALIZATION_PATH = os.path.join(os.getcwd(), NORMALIZATION_FILE)

if not os.path.exists(NORMALIZATION_PATH):
    # kita pakai hasil build_star_schema yang sudah ada (dimensi + fact)
    dim_date, dim_customer, dim_product, dim_region, dim_ship_mode, fact_sales = build_star_schema(raw)

    save_normalization_excel(
        NORMALIZATION_PATH,
        raw,
        dim_date,
        dim_customer,
        dim_product,
        dim_region,
        dim_ship_mode,
        fact_sales
    )


# =========================================================
# SIDEBAR FILTERS
# =========================================================
with st.sidebar:
    st.header("Filter Dashboard")

    min_date = raw["Order Date"].min()
    max_date = raw["Order Date"].max()

    date_range = st.date_input(
        "Rentang Order Date",
        value=(min_date.date(), max_date.date()),
        min_value=min_date.date(),
        max_value=max_date.date()
    )

    categories = sorted(raw["Category"].dropna().unique().tolist())
    cat_pick = st.multiselect("Category", options=categories, default=categories)

    regions = sorted(raw["Region"].dropna().unique().tolist())
    reg_pick = st.multiselect("Region", options=regions, default=regions)

    segments = sorted(raw["Segment"].dropna().unique().tolist())
    seg_pick = st.multiselect("Segment", options=segments, default=segments)

start_date, end_date = date_range
df_f = raw[
    (raw["Order Date"].dt.date >= start_date) &
    (raw["Order Date"].dt.date <= end_date) &
    (raw["Category"].isin(cat_pick)) &
    (raw["Region"].isin(reg_pick)) &
    (raw["Segment"].isin(seg_pick))
].copy()

# =========================================================
# KPI
# =========================================================
total_sales = df_f["Sales"].sum()
order_count = df_f["Order ID"].nunique()
customer_count = df_f["Customer ID"].nunique()

k1, k2, k3 = st.columns(3)
k1.metric("Total Sales", f"{total_sales:,.2f}")
k2.metric("Total Orders", f"{order_count:,}")
k3.metric("Total Customers", f"{customer_count:,}")

st.divider()

# =========================================================
# CHARTS: CATEGORY & SEGMENT (Pie + Donut)
# =========================================================
cat_sales = df_f.groupby("Category")["Sales"].sum().sort_values(ascending=False)
seg_sales = df_f.groupby("Segment")["Sales"].sum().sort_values(ascending=False)

c1, c2 = st.columns(2)

with c1:
    st.subheader("Sales by Category (Bar)")
    st.dataframe(cat_sales.reset_index().rename(columns={"Sales": "Total Sales"}), use_container_width=True)

    fig_cat_bar = plt.figure(figsize=(6, 3))
    plt.bar(cat_sales.index, cat_sales.values)
    plt.xticks(rotation=20, ha="right")
    plt.ylabel("Sales")
    plt.title("Sales by Category")
    plt.tight_layout()
    st.pyplot(fig_cat_bar, use_container_width=False)

with c2:
    st.subheader("Sales by Category (Pie)")
    fig_cat_pie = plt.figure(figsize=(5, 5))
    plt.pie(
        cat_sales.values,
        labels=cat_sales.index,
        autopct="%1.1f%%",
        startangle=90
    )
    plt.title("Category Share")
    plt.tight_layout()
    st.pyplot(fig_cat_pie, use_container_width=False)

st.divider()

d1, d2 = st.columns(2)
with d1:
    st.subheader("Sales by Segment (Donut)")
    fig_seg_donut = plt.figure(figsize=(5, 5))
    plt.pie(
        seg_sales.values,
        labels=seg_sales.index,
        autopct="%1.1f%%",
        startangle=90,
        wedgeprops={"width": 0.4}
    )
    plt.title("Segment Share")
    plt.tight_layout()
    st.pyplot(fig_seg_donut, use_container_width=False)

with d2:
    st.subheader("Sales by Region (Bar)")
    reg_sales = df_f.groupby("Region")["Sales"].sum().sort_values(ascending=False)
    st.dataframe(reg_sales.reset_index().rename(columns={"Sales": "Total Sales"}), use_container_width=True)

    fig_reg = plt.figure(figsize=(6, 3))
    plt.bar(reg_sales.index, reg_sales.values)
    plt.xticks(rotation=20, ha="right")
    plt.ylabel("Sales")
    plt.title("Sales by Region")
    plt.tight_layout()
    st.pyplot(fig_reg, use_container_width=False)

st.divider()

# =========================================================
# TOP PRODUCTS (Horizontal Bar)
# =========================================================
st.subheader("Top 10 Products (Horizontal Bar)")
top_prod = df_f.groupby("Product Name")["Sales"].sum().sort_values(ascending=False).head(10)
st.dataframe(top_prod.reset_index().rename(columns={"Sales": "Total Sales"}), use_container_width=True)

fig_top = plt.figure(figsize=(7, 4))
plt.barh(top_prod.index[::-1], top_prod.values[::-1])
plt.xlabel("Sales")
plt.title("Top 10 Products (by Sales)")
plt.tight_layout()
st.pyplot(fig_top, use_container_width=False)

st.divider()

# =========================================================
# MONTHLY TREND (Line) + FIX LABELS
# =========================================================
st.subheader("Monthly Sales Trend (Line)")
df_f["month"] = df_f["Order Date"].dt.to_period("M").astype(str)
monthly = df_f.groupby("month")["Sales"].sum()

fig_trend = plt.figure(figsize=(8, 3))
plt.plot(monthly.index, monthly.values, marker="o")

# show every 3 months to avoid messy labels
step = 3
ticks = range(0, len(monthly.index), step)
plt.xticks(ticks, [monthly.index[i] for i in ticks], rotation=45, ha="right")

plt.ylabel("Sales")
plt.title("Monthly Sales Trend")
plt.tight_layout()
st.pyplot(fig_trend, use_container_width=False)

st.divider()

# =========================================================
# STAR SCHEMA (BUILD + PREVIEW)
# =========================================================
st.header("⭐ Star Schema (Dimensi & Fakta)")

with st.expander("Klik untuk membangun & melihat tabel Star Schema"):
    dim_date, dim_customer, dim_product, dim_region, dim_ship_mode, fact_sales = build_star_schema(raw)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("dim_date", f"{len(dim_date):,}")
    m2.metric("dim_customer", f"{len(dim_customer):,}")
    m3.metric("dim_product", f"{len(dim_product):,}")
    m4.metric("fact_sales", f"{len(fact_sales):,}")

    st.subheader("Preview dim_customer")
    st.dataframe(dim_customer.head(15), use_container_width=True)

    st.subheader("Preview dim_product")
    st.dataframe(dim_product.head(15), use_container_width=True)

    st.subheader("Preview dim_region")
    st.dataframe(dim_region.head(15), use_container_width=True)

    st.subheader("Preview fact_sales")
    st.dataframe(fact_sales.head(15), use_container_width=True)

st.divider()

# =========================================================
# EXPORT (Excel multi-sheet + JSON summary)
# =========================================================
st.header("⬇️ Export")

dim_date, dim_customer, dim_product, dim_region, dim_ship_mode, fact_sales = build_star_schema(raw)
excel_bytes = to_excel_bytes(raw, dim_date, dim_customer, dim_product, dim_region, dim_ship_mode, fact_sales)

st.download_button(
    label="Download Excel (raw + dim + fact) -> train_star_schema.xlsx",
    data=excel_bytes,
    file_name="train_star_schema.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)


if os.path.exists(NORMALIZATION_PATH):
    with open(NORMALIZATION_PATH, "rb") as f:
        st.download_button(
            label="Download Normalisasi (1NF–3NF) -> normalisasi_superstore.xlsx",
            data=f,
            file_name="normalisasi_superstore.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


summary = make_summary_json(df_f)
summary_bytes = json.dumps(summary, ensure_ascii=False, indent=2).encode("utf-8")

st.download_button(
    label="Download JSON Summary (sesuai filter dashboard) -> summary_api_ready.json",
    data=summary_bytes,
    file_name="summary_api_ready.json",
    mime="application/json",
)

st.divider()

st.subheader("Preview Data (Filtered)")
st.dataframe(df_f.head(50), use_container_width=True)



