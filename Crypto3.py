import streamlit as st
import pandas as pd
import mysql.connector
import datetime

st.set_page_config(layout="wide")

def connect_to_database():
    conn = mysql.connector.connect(
        host="185.120.57.125",
        user="admin",
        password="v8S7b$82j51d1",
        database="crypto"
    )
    return conn

@st.cache_data
@st.cache_resource
def fetch_data(date_from=None, date_to=None):
    conn = connect_to_database()
    
    query = """
    SELECT 
        etherdrop_parser.currency_name, 
        wallet_list.wallet_address,
        etherdrop_parser.datetime, 
        etherdrop_parser.dollar_value,
        CASE 
            WHEN wallet_list.wallet_address = etherdrop_parser.pool_address_from THEN 'продажа'
            WHEN wallet_list.wallet_address = etherdrop_parser.receiver_address_link THEN 'покупка'
            ELSE 'пустой кошелек'
        END AS wallet_type
    FROM wallet_list
    LEFT JOIN etherdrop_parser 
        ON wallet_list.wallet_address = etherdrop_parser.pool_address_from 
        OR wallet_list.wallet_address = etherdrop_parser.receiver_address_link
    WHERE etherdrop_parser.id IS NOT NULL 
    """

    if date_from and date_to:
        query += f" AND etherdrop_parser.datetime BETWEEN '{date_from}' AND '{date_to}'"

    df = pd.read_sql(query, conn)
    conn.close()

    return df

def main():
    st.title('Wallets')

    # Выбор диапазона дат
    today = datetime.datetime.now()
    month_ago = today - datetime.timedelta(days=7)
    date_range = st.sidebar.date_input("Выберите диапазон дат", [month_ago, today])

    if len(date_range) == 2:
        date_from, date_to = date_range
        date_from = pd.Timestamp(date_from)
        date_to = pd.Timestamp(date_to)

        df = fetch_data(date_from, date_to)

        # Преобразование столбца 'datetime' в datetime
        df['datetime'] = pd.to_datetime(df['datetime'])

        # Фильтры
        unique_usernames = df['wallet_address'].unique().tolist()
        unique_currency_names = df['currency_name'].unique().tolist()
        unique_wallet_types = df['wallet_type'].unique().tolist()

        selected_currency = st.sidebar.selectbox("currency_name:", [""] + unique_currency_names)
        selected_username = st.sidebar.selectbox("wallet_address:", [""] + unique_usernames)
        #selected_wallet_type = st.sidebar.selectbox("wallet_type:", [""] + unique_wallet_types)

        # Применение фильтров
        if selected_username:
            df = df[df['wallet_address'] == selected_username]
        if selected_currency:
            df = df[df['currency_name'] == selected_currency]
        #if selected_wallet_type:
        #    df = df[df['wallet_type'] == selected_wallet_type]

        # Создание таблиц
        # 1. Детальная информация
        detailed_info = df.groupby(['currency_name', 'wallet_address', 'datetime', 'wallet_type'])['dollar_value'].sum().reset_index()
        detailed_info = detailed_info.sort_values(['currency_name', 'wallet_address', 'datetime'], ascending=[True, True, False])

        # 2. Сводная информация по валютам
        currency_summary = df.groupby('currency_name').agg({
            'wallet_address': lambda x: x[df['wallet_type'] == 'покупка'].nunique(),
            'dollar_value': lambda x: (x * (df['wallet_type'] == 'покупка')).sum()
        }).rename(columns={'wallet_address': 'Кошельки покупки', 'dollar_value': 'Объем покупки $'})
        
        currency_summary['Кошельки продажи'] = df[df['wallet_type'] == 'продажа'].groupby('currency_name')['wallet_address'].nunique()
        currency_summary['Объем продажи'] = df[df['wallet_type'] == 'продажа'].groupby('currency_name')['dollar_value'].sum()
        currency_summary = currency_summary.reset_index()

        # 3. Информация по кошелькам
        wallet_info = df.groupby('wallet_address').agg({
            'dollar_value': lambda x: [
                (x * (df['wallet_type'] == 'покупка')).sum(),
                (x * (df['wallet_type'] == 'продажа')).sum()
            ]
        }).reset_index()
        wallet_info[['buy_volume', 'sell_volume']] = pd.DataFrame(wallet_info['dollar_value'].tolist(), index=wallet_info.index)
        wallet_info = wallet_info.drop('dollar_value', axis=1)

        # Отображение таблиц
        col1, col2 = st.columns([1, 2])

        with col1:
            st.subheader("Сводная информация по валютам")
            st.dataframe(currency_summary, use_container_width=True, height=500, hide_index=True)

            st.subheader("Информация по кошелькам")
            st.dataframe(wallet_info, use_container_width=True, height=400, hide_index=True)

        with col2:
            st.subheader("Детальная информация")
            st.dataframe(detailed_info, use_container_width=True, height=982, hide_index=True)

    else:
        st.error("Пожалуйста, выберите диапазон дат.")

if __name__ == "__main__":
    main()