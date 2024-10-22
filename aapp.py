
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import mysql.connector
import hashlib
import numpy as np

# Database connection
def create_connection():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password='',
        database='forecast'
    )

# Hashing function for passwords
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Load data from database
def load_data_from_database():
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM stock_data")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    data = pd.DataFrame(rows, columns=["id", "item_name", "date", "value"])
    return data

def delete_and_update_stock_data(delete_ids):
    conn = create_connection()
    cursor = conn.cursor()

    # Fetch the initial IDs before deletion
    initial_ids = {}
    cursor.execute("SELECT id, item_name FROM stock_data WHERE id IN (%s)" % ','.join(['%s']*len(delete_ids)), tuple(delete_ids))
    rows = cursor.fetchall()
    for row in rows:
        initial_ids[row[0]] = row[1]

    # Delete the specified data
    format_strings = ','.join(['%s'] * len(delete_ids))
    cursor.execute(f"DELETE FROM stock_data WHERE id IN ({format_strings})", tuple(delete_ids))
    conn.commit()

    # Update the IDs with the initial IDs
    for idx, (id, item_name) in enumerate(initial_ids.items()):
        new_id = f"{item_name[:2].upper()}-{str(idx+1).zfill(3)}"
        cursor.execute("UPDATE stock_data SET id = %s WHERE id = %s", (new_id, id))

    conn.commit()
    cursor.close()
    conn.close()


# Delete all data from database by item name
def delete_all_stock_data_by_item_name(item_name):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM stock_data WHERE item_name = %s ORDER BY id ASC", (item_name,))
    ids = cursor.fetchall()
    cursor.execute("DELETE FROM stock_data WHERE item_name = %s", (item_name,))
    conn.commit()
    cursor.close()
    conn.close()

    # Update IDs to be sequential
    if ids:
        conn = create_connection()
        cursor = conn.cursor()
        for idx, (item_id,) in enumerate(ids, 1):
            cursor.execute("UPDATE stock_data SET id = %s WHERE id = %s", (f"DATA-{str(idx).zfill(3)}", item_id))
        conn.commit()
        cursor.close()
        conn.close()

                                                                       

# Weighted Moving Average function
def weighted_moving_average(data, weights):
    result = []
    for i in range(len(data)):
        if i < len(weights):
            wma = np.dot(data[:i+1][::-1], weights[:i+1])
        else:
            wma = np.dot(data[i-len(weights)+1:i+1][::-1], weights)
        result.append(wma)
    return np.array(result)

# MAPE calculation
def calculate_mape(actual, forecast):
    return np.mean(np.abs((actual - forecast) / actual)) * 100

def main():
    st.title("Forecasting Stok Barang KSR")
    st.image('pmi.jpg', caption='PMI Kabupaten Bogor')

    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.is_special = False  # Default admin bukan admin khusus

    if st.session_state.logged_in:
        sidebar_logged_in()
    else:
        sidebar_login_register()


def sidebar_login_register():
    st.sidebar.title("Menu")
    choice = st.sidebar.selectbox(
        "Pilih Menu",
        ["🔒 Login", "📝 Register"],
        key='sidebar_menu'
    )

    if choice == "🔒 Login":
        show_login()
    elif choice == "📝 Register":
        show_register()

def show_login():
    st.sidebar.subheader("Login Admin")
    username = st.sidebar.text_input("Username", key='login_username')
    password = st.sidebar.text_input("Password", type="password", key='login_password')
    if st.sidebar.button("Login", key='login_button'):
        user = login(username, password)
        if user:
            st.session_state.logged_in = True
            st.session_state.is_special = user[3]  # Kolom keempat adalah is_special
            st.experimental_rerun()
        else:
            st.sidebar.error("Username atau password salah")


def show_register():
    st.sidebar.subheader("Register Admin Baru")
    new_username = st.sidebar.text_input("Username Baru", key='register_username')
    new_password = st.sidebar.text_input("Password Baru", type="password", key='register_password')
    if st.sidebar.button("Daftar", key='register_button'):
        register(new_username, new_password)
        st.sidebar.success("Admin baru berhasil dibuat")

def sidebar_logged_in():
    st.sidebar.title("Menu")
    if st.session_state.is_special:
        choice = st.sidebar.selectbox(
            "Pilih Menu",
            ["📦 Data Stok Barang Keluar", "📊 Grafik Data Barang", "🔮 Forecasting dan MAPE", "🚪 Logout"],
            key='sidebar_logged_in_menu'
        )
    else:
        choice = st.sidebar.selectbox(
            "Pilih Menu",
            ["📦 Data Stok Barang Keluar", "✏️ Input Data Manual", "📊 Grafik Data Barang", "🔮 Forecasting dan MAPE", "🚪 Logout"],
            key='sidebar_logged_in_menu'
        )

    if choice == "📦 Data Stok Barang Keluar":
        show_stock_data()
    elif choice == "✏️ Input Data Manual":
        input_manual_data()
    elif choice == "📊 Grafik Data Barang":
        show_item_graphs()
    elif choice == "🔮 Forecasting dan MAPE":
        show_forecasting_mape()
    elif choice == "🚪 Logout":
        st.session_state.logged_in = False
        st.experimental_rerun()


def show_stock_data():
    st.subheader("Data Stok Barang")
    data = load_data_from_database()
    item_types = data['item_name'].unique()
    selected_item_type = st.selectbox("Pilih Jenis Barang", item_types)
    filtered_data = data[data['item_name'] == selected_item_type]
    st.write(filtered_data)

    if st.session_state.is_special:
        st.info("Anda login sebagai admin spesial. Anda tidak memiliki akses untuk menghapus data.")
    else:
        st.subheader("Hapus Data")
        delete_ids = st.multiselect("ID Data yang ingin dihapus", filtered_data['id'])
        if st.button("Hapus Data"):
            delete_and_update_stock_data(delete_ids)
            st.success("Data berhasil dihapus dan ID diperbarui.")
            st.experimental_rerun()

        if st.button("Hapus Semua Data"):
            delete_all_stock_data_by_item_name(selected_item_type)
            st.success("Semua data berhasil dihapus.")
            st.experimental_rerun()

def input_manual_data():
    st.subheader("Input Data Manual")
    data = load_data_from_database()
    item_names = data['item_name'].unique()
    new_item = st.checkbox("Input Nama Barang Baru")
    
    if new_item:
        item_name = st.text_input("Nama Barang Baru")
    else:
        item_name = st.selectbox("Pilih Nama Barang yang Sudah Ada", item_names)

    date = st.date_input("Tanggal")
    value = st.number_input("Nilai")
    
    if st.button("Tambah Data"):
        item_id = generate_item_id(item_name)
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO stock_data (id, item_name, date, value) VALUES (%s, %s, %s, %s)", (item_id, item_name, date, value))
        conn.commit()
        cursor.close()
        conn.close()
        st.success("Data berhasil ditambahkan.")
        st.experimental_rerun()

def get_initials_and_last_letters(item_name):
    words = item_name.split()
    if len(words) >= 2:
        initials = ''.join([word[0] for word in words[:2]]).upper()
        last_letters = ''.join([word[-2:] for word in words[:2]]).upper()
        return initials, last_letters
    else:
        return None, None


def generate_item_id(item_name):
    initials, last_letters = get_initials_and_last_letters(item_name)
    if initials is not None and last_letters is not None:
        item_id = f"{initials}-{last_letters}"
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM stock_data WHERE item_name = %s", (item_name,))
        count = cursor.fetchone()[0] + 1
        cursor.close()
        conn.close()
        item_id = f"{initials}-{last_letters}-{str(count).zfill(3)}"
        return item_id
    else:
        raise ValueError("Nama barang harus terdiri dari minimal dua kata.")


def show_item_graphs():
    st.subheader("Grafik Data Masing-Masing Jenis Barang")
    data = load_data_from_database()
    item_types = data['item_name'].unique()
    selected_item_type = st.selectbox("Pilih Jenis Barang", item_types)
    filtered_data = data[data['item_name'] == selected_item_type]
    
    if not filtered_data.empty:
        filtered_data['year'] = pd.to_datetime(filtered_data['date']).dt.year
        years = filtered_data['year'].unique()
        
        fig = go.Figure()
        
        for year in years:
            year_data = filtered_data[filtered_data['year'] == year]
            fig.add_trace(go.Scatter(
                x=year_data['date'], 
                y=year_data['value'], 
                mode='lines+markers', 
                name=str(year),
                line=dict(color=px.colors.qualitative.Plotly[years.tolist().index(year) % len(px.colors.qualitative.Plotly)])
            ))
        
        fig.update_layout(
            title=f"Grafik Data Stok Barang {selected_item_type} per Tahun",
            xaxis_title="Tanggal",
            yaxis_title="Nilai"
        )
        st.plotly_chart(fig)

    st.subheader("Tampilan Data Tertinggi dan Terendah")
    if not filtered_data.empty:
        max_value_item = filtered_data.loc[filtered_data['value'].idxmax()]
        min_value_item = filtered_data.loc[filtered_data['value'].idxmin()]
        st.write("Barang dengan Nilai Tertinggi:", max_value_item)
        st.write("Barang dengan Nilai Terendah:", min_value_item)



def show_forecasting_mape():
    st.subheader("Forecasting menggunakan Weighted Moving Average")
    data = load_data_from_database()
    item_types = data['item_name'].unique()
    selected_item_type = st.selectbox("Pilih Jenis Barang", item_types)
    filtered_data = data[data['item_name'] == selected_item_type]

    weights = np.array([0.5, 0.3, 0.2])
    if len(filtered_data) >= len(weights):
        data_forecast = filtered_data['value'].tolist()
        wma_forecast = weighted_moving_average(data_forecast, weights)
        next_month_forecast = wma_forecast[-1]
        st.write(f"Forecast untuk {selected_item_type} bulan depan: {next_month_forecast}")

        st.subheader("Perhitungan Mean Absolute Percentage Error (MAPE)")
        if len(filtered_data) >= len(weights):
            actual_values = np.array(data_forecast)
            forecast_values = wma_forecast
            mape = calculate_mape(actual_values[len(weights)-1:], forecast_values[len(weights)-1:])
            st.write(f"Nilai MAPE untuk {selected_item_type}: {mape}%")
            if mape <= 20:
                st.write("Model peramalan baik.")
            elif mape <= 50:
                st.write("Model peramalan layak/memadai/dikondisikan.")
            else:
                st.write("Model peramalan buruk.")


        # Tampilkan grafik peramalan
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=filtered_data['date'], y=data_forecast, mode='lines+markers', name='Data Asli', marker=dict(color='blue')))
        fig.add_trace(go.Scatter(x=filtered_data['date'], y=wma_forecast, mode='lines+markers', name='Data Peramalan', marker=dict(color='red')))
        fig.update_layout(title=f"Forecasting Stok Barang {selected_item_type}", xaxis_title="Tanggal", yaxis_title="Nilai")
        st.plotly_chart(fig)

        # Buat DataFrame untuk peramalan
        forecast_df = pd.DataFrame({
            'Tanggal': filtered_data['date'],
            'Data Asli': data_forecast,
            'Forecast': wma_forecast
        })
        st.write(forecast_df)

        # Hitung MAPE
        actual_values = np.array(data_forecast)
        forecast_values = wma_forecast
        mapes = []
        for i in range(len(weights), len(actual_values)):
            mape = calculate_mape(actual_values[:i+1], forecast_values[:i+1])
            mapes.append(mape)

        # Tampilkan tabel nilai MAPE
        mape_df = pd.DataFrame({
            'Bulan': filtered_data['date'].iloc[len(weights):],  # Mulai dari bulan pertama setelah periode weights
            'MAPE (%)': mapes
        })
        st.write("Tabel Nilai MAPE untuk semua bulan:")
        st.write(mape_df)



        # Nilai MAPE tertinggi dan terendah
        max_mape = mape_df['MAPE (%)'].max()
        min_mape = mape_df['MAPE (%)'].min()
        st.write(f"MAPE Tertinggi: {max_mape}%")
        st.write(f"MAPE Terendah: {min_mape}%")

        # Kualifikasi model berdasarkan MAPE
        if max_mape <= 20:
            st.write("Model peramalan baik.")
        elif max_mape <= 50:
            st.write("Model peramalan layak/memadai/dikondisikan.")
        else:
            st.write("Model peramalan buruk.")


def login(username, password):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM admin WHERE username = %s AND password = %s", (username, hash_password(password)))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return user

def register(username, password):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO admin (username, password) VALUES (%s, %s)", (username, hash_password(password)))
    conn.commit()
    cursor.close()
    conn.close()

def register(username, password, is_special=False):
    conn = create_connection()
    cursor = conn.cursor()
    hashed_password = hash_password(password)
    cursor.execute("INSERT INTO admin (username, password, is_special) VALUES (%s, %s, %s)", (username, hashed_password, is_special))
    conn.commit()
    cursor.close()
    conn.close()

def login(username, password):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM admin WHERE username = %s AND password = %s", (username, hash_password(password)))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return user


if __name__ == "__main__":
    main()