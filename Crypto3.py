import streamlit as st
import pandas as pd
import mysql.connector
import datetime
import plotly.graph_objects as go
import numpy as np

st.set_page_config(layout="wide")

def connect_to_database():
    conn = mysql.connector.connect(
        host="185.120.57.125",
        user="admin",
        password="v8S7b$82j51d1",
        database="crypto"
    )
    return conn

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
            WHEN wallet_list.wallet_address = etherdrop_parser.pool_address_from THEN 'кошелек продажи'
            WHEN wallet_list.wallet_address = etherdrop_parser.receiver_address_link THEN 'кошелек покупки'
            ELSE 'пустой кошелек'
        END AS wallet_type
    FROM wallet_list
    LEFT JOIN etherdrop_parser 
        ON wallet_list.wallet_address = etherdrop_parser.pool_address_from 
        OR wallet_list.wallet_address = etherdrop_parser.receiver_address_link
    WHERE etherdrop_parser.id IS NOT NULL 
    """

    if date_from and date_to:
        query += " AND etherdrop_parser.datetime BETWEEN %s AND %s"
        df = pd.read_sql(query, conn, params=[date_from, date_to])
    else:
        df = pd.read_sql(query, conn)
    
    conn.close()
    return df

def make_wallet_address_link(wallet_address):
    return f"https://www.alphatrace.xyz/wallet/{wallet_address}"

def create_wallet_chart(df):
    fig = go.Figure()
    
    # Группируем данные по дате и валюте
    df_grouped = df.groupby(['datetime', 'currency_name', 'wallet_type'])['dollar_value'].sum().reset_index()
    
    # Получаем уникальные валюты
    currencies = df_grouped['currency_name'].unique()
    
    # Задаем фиксированную ширину столбца в миллисекундах (примерно 50 пикселей)
    bar_width = 10 * 60 * 60 * 1000 / 2  # половина дня в миллисекундах
    
    # Задаем конкретные цвета
    buy_color = '#4CAF50'  # зеленый
    sell_color = '#F44336'  # красный
    
    for currency in currencies:
        currency_data = df_grouped[df_grouped['currency_name'] == currency]
        
        buy_data = currency_data[currency_data['wallet_type'] == 'кошелек покупки']
        sell_data = currency_data[currency_data['wallet_type'] == 'кошелек продажи']
        
        fig.add_trace(go.Bar(
            x=buy_data['datetime'],
            y=buy_data['dollar_value'],
            name=f'Покупка ({currency})',
            marker_color='rgb(132, 214, 69)',
            hovertemplate='Валюта: %{text}<br>Дата: %{x}<br>Объем покупки: $%{y:.2f}<extra></extra>',
            text=[currency] * len(buy_data),  # Добавляем название валюты
            width=bar_width
        ))
        
        fig.add_trace(go.Bar(
            x=sell_data['datetime'],
            y=sell_data['dollar_value'],
            name=f'Продажа ({currency})',
            marker_color='rgb(214, 69, 69)',
            hovertemplate='Валюта: %{text}<br>Дата: %{x}<br>Объем продажи: $%{y:.2f}<extra></extra>',
            text=[currency] * len(sell_data),  # Добавляем название валюты
            width=bar_width
        ))
    
    fig.update_layout(
        title='Объемы покупок и продаж по валютам',
        xaxis_title='Дата',
        yaxis_title='Объем (USD)',
        barmode='group',
        hovermode='closest',
        width=1000,
        height=450
    )
    
    # Устанавливаем диапазон дат на оси X
    fig.update_xaxes(
        range=[df['datetime'].min() - pd.Timedelta(days=1), 
               df['datetime'].max() + pd.Timedelta(days=1)]
    )
    
    return fig

def dataframe_with_selections(df):
    df_with_selections = df.copy()
    df_with_selections.insert(0, "Select", False)
    edited_df = st.data_editor(
        df_with_selections,
        hide_index=True,
        column_config={"Select": st.column_config.CheckboxColumn(required=True)},
        disabled=df.columns,
    )
    selected_indices = list(np.where(edited_df.Select)[0])
    selected_rows = df[edited_df.Select]
    return {"selected_rows_indices": selected_indices, "selected_rows": selected_rows}

def main():
    st.title('Wallets')

    # Выбор диапазона дат
    today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - datetime.timedelta(days=7)
    date_range = st.sidebar.date_input("Выберите диапазон дат", [week_ago, today])

    if len(date_range) == 2:
        date_from, date_to = date_range
        date_from = pd.Timestamp(date_from)
        date_to = pd.Timestamp(date_to) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)

        df = fetch_data(date_from, date_to)

        # Преобразование столбца 'datetime' в datetime
        df['datetime'] = pd.to_datetime(df['datetime'])

        # Создание таблиц
        # 1. Детальная информация
        detailed_info = df.groupby(['currency_name', 'wallet_address', 'datetime', 'wallet_type'])['dollar_value'].sum().reset_index()
        detailed_info = detailed_info.sort_values(['currency_name', 'wallet_address', 'datetime'], ascending=[True, True, False])

        # 2. Сводная информация по валютам
        currency_summary = df.groupby('currency_name').agg({
            'wallet_address': lambda x: x[df['wallet_type'] == 'кошелек покупки'].nunique(),
            'dollar_value': lambda x: (x * (df['wallet_type'] == 'кошелек покупки')).sum()
        }).rename(columns={'wallet_address': 'buy_wallets_count', 'dollar_value': 'buy_volume'})
        
        currency_summary['sell_wallets_count'] = df[df['wallet_type'] == 'кошелек продажи'].groupby('currency_name')['wallet_address'].nunique()
        currency_summary['sell_volume'] = df[df['wallet_type'] == 'кошелек продажи'].groupby('currency_name')['dollar_value'].sum()
        currency_summary = currency_summary.reset_index()

        # 3. Информация по кошелькам
        wallet_info = df.groupby('wallet_address').agg({
            'dollar_value': lambda x: [
                (x * (df['wallet_type'] == 'кошелек покупки')).sum(),
                (x * (df['wallet_type'] == 'кошелек продажи')).sum()
            ]
        }).reset_index()
        wallet_info[['buy_volume', 'sell_volume']] = pd.DataFrame(wallet_info['dollar_value'].tolist(), index=wallet_info.index)
        wallet_info = wallet_info.drop('dollar_value', axis=1)

        # Добавляем столбец со ссылкой
        wallet_info['wallet_link'] = wallet_info['wallet_address'].apply(make_wallet_address_link)
        wallet_info = wallet_info.rename(columns={'wallet_link': 'Wallet Link'})  # Переименование столбца

        # Отображение таблиц
        col1, col2 = st.columns([2, 3])

        with col1:
            st.subheader("Сводная информация по валютам")
            selection = dataframe_with_selections(currency_summary)
            selected_currencies = selection["selected_rows"]["currency_name"].tolist()

            st.subheader("Информация по кошелькам")
            if selected_currencies:
                # Фильтруем транзакции по выбранным валютам
                filtered_df = df[df['currency_name'].isin(selected_currencies)]
                
                # Группируем отфильтрованные данные по wallet_address
                filtered_wallet_info = filtered_df.groupby('wallet_address').agg({
                    'dollar_value': lambda x: [
                        (x * (filtered_df['wallet_type'] == 'кошелек покупки')).sum(),
                        (x * (filtered_df['wallet_type'] == 'кошелек продажи')).sum()
                    ]
                }).reset_index()
                
                filtered_wallet_info[['buy_volume', 'sell_volume']] = pd.DataFrame(filtered_wallet_info['dollar_value'].tolist(), index=filtered_wallet_info.index)
                filtered_wallet_info = filtered_wallet_info.drop('dollar_value', axis=1)
                
                # Добавляем столбец со ссылкой
                filtered_wallet_info['wallet_link'] = filtered_wallet_info['wallet_address'].apply(make_wallet_address_link)
                filtered_wallet_info = filtered_wallet_info.rename(columns={'wallet_link': 'Wallet Link'})
            else:
                filtered_wallet_info = wallet_info
            
            st.dataframe(
                filtered_wallet_info[['wallet_address', 'buy_volume', 'sell_volume', 'Wallet Link']],
                column_config={
                    "Wallet Link": st.column_config.LinkColumn(
                        label="Wallet Address",
                        display_text="Link",
                        help="Click to open wallet"
                    ),
                    "buy_volume": st.column_config.NumberColumn("Buy Volume"),
                    "sell_volume": st.column_config.NumberColumn("Sell Volume")
                },
                hide_index=True,
                use_container_width=True,
                height=400
            )

        with col2:
            st.subheader("Детальная информация")
            if selected_currencies:
                filtered_detailed_info = detailed_info[detailed_info['currency_name'].isin(selected_currencies)]
            else:
                filtered_detailed_info = detailed_info
            st.dataframe(filtered_detailed_info, use_container_width=True, height=500)

            # Создание и отображение графика
            st.subheader("График объемов покупок и продаж")
            if selected_currencies:
                filtered_df = df[df['currency_name'].isin(selected_currencies)]
            else:
                filtered_df = df
            chart = create_wallet_chart(filtered_df)
            st.plotly_chart(chart, use_container_width=True)

    else:
        st.error("Пожалуйста, выберите диапазон дат.")

if __name__ == "__main__":
    main()
