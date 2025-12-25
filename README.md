# 📊 Superstore Business Intelligence Dashboard

# Star Schema & Normalisasi (1NF–3NF)

# 📌 Deskripsi Proyek

Proyek ini merupakan implementasi Business Intelligence (BI) menggunakan Superstore Sales Dataset (Kaggle). Dataset mentah berbentuk flat table diolah melalui proses ETL, normalisasi database, dan perancangan Data Warehouse (Star Schema), kemudian divisualisasikan dalam bentuk dashboard interaktif berbasis Streamlit.

Aplikasi ini tidak hanya menampilkan dashboard analitik, tetapi juga secara otomatis menghasilkan file dokumentasi normalisasi (1NF–3NF) serta file Star Schema dalam format Excel sebagai bukti proses perancangan data warehouse.


# 🎯 Tujuan

  -Melakukan analisis dataset Superstore untuk mengidentifikasi atribut dan permasalahan data.
  -Melakukan normalisasi database hingga Third Normal Form (3NF).
  -Mendesain Data Warehouse dengan Star Schema.
  -Menyediakan dataset API-ready (JSON) untuk integrasi aplikasi (misalnya mobile/Flutter).
  -Menyajikan insight bisnis melalui dashboard interaktif.

# 📂 Dataset

Nama Dataset: Superstore Sales Dataset
Sumber: Kaggle
Link: https://www.kaggle.com/datasets/rohitsahoo/sales-forecasting/data
File yang digunakan: train.csv

# 🗂️ Struktur Folder
project/
├── app.py
├── train.csv
├── train_star_schema.xlsx
├── normalisasi_superstore.xlsx
└── README.md

# 🧱 Proses Business Intelligence
# 1️⃣ Analisis Dataset

  -Identifikasi atribut (Order, Customer, Product, Region, Time)
  -Perbaikan format tanggal
  -Pembersihan data duplikat
  -Standarisasi Postal Code

# 2️⃣ Normalisasi Database
-Normalisasi dilakukan hingga 3NF, dengan dokumentasi hasil pada file:

    📘 normalisasi_superstore.xlsx

-Normal Form	Sheet	Keterangan
    1NF	1NF_raw	Data mentah yang sudah atomic & konsisten
    2NF	2NF_customer	Entitas customer
    2NF	2NF_product	Entitas produk
    2NF	2NF_region	Entitas wilayah
    3NF	3NF_dim_date	Dimensi waktu
    3NF	3NF_dim_ship_mode	Dimensi pengiriman
    3NF	3NF_fact_sales	Tabel fakta penjualan

# 3️⃣ Desain Data Warehouse (Star Schema)

Star Schema terdiri dari:

  -fact_sales
  -dim_date
  -dim_customer
  -dim_product
  -dim_region
  -dim_ship_mode

📁 Disimpan dalam file:
📊 train_star_schema.xlsx

Grain Fact:

1 baris pada fact_sales merepresentasikan 1 transaksi penjualan per produk (order line).

# 4️⃣ ETL Pipeline

Extract: train.csv

Transform:

    -Cleaning data
    -Normalisasi
    -Mapping foreign key

Load:

    -Excel (Star Schema & Normalisasi)
    -Dataset JSON (API-ready)

# 5️⃣ Dashboard BI

Dashboard dibangun menggunakan Streamlit dengan fitur:

  -KPI (Total Sales, Orders, Customers)
  -Bar Chart
  -Pie Chart
  -Donut Chart
  -Line Chart (Monthly Trend)
  -Filter interaktif (Date, Category, Region, Segment)
  -Export Excel & JSON

# ⬇️ Fitur Export

  -Aplikasi menyediakan fitur unduhan:
  -Star Schema Excel
  -Normalisasi 1NF–3NF Excel
  -JSON Summary (API-ready)

# 🚀 Cara Menjalankan Aplikasi
# 1️⃣ Install Dependency
pip install streamlit pandas matplotlib openpyxl

# 2️⃣ Jalankan Aplikasi
streamlit run app.py

# 🧠 Teknologi yang Digunakan

  -Python
  -Pandas
  -Streamlit
  -Matplotlib
  -OpenPyXL

# 🎓 Catatan Akademik

Proyek ini dibuat untuk memenuhi tugas Mata Kuliah Business Intelligence, dengan penekanan pada:

  -Proses normalisasi database
  -Perancangan data warehouse
  -Integrasi BI dengan aplikasi berbasis dashboard

# 👤 Author

Muhamad Gian Novridan, Muhammad Adli Nursah, Alya Nabilah
Program Studi: Informatika
Institusi: Universitas Sultan Ageng Tirtayasa
Tahun: 2025
