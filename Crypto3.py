import streamlit as st
import pandas as pd
import mysql.connector
import datetime
import plotly.graph_objects as go
import numpy as np

st.set_page_config(layout="wide")

st.markdown("""
    <style>
        .block-container {
            padding-top: 2rem;
            padding-bottom: 0rem;
            padding-left: 1.5rem;
            padding-right: 1.5rem;
        }
    </style>
    """, unsafe_allow_html=True)

def init_connection():
    return mysql.connector.connect(
        host="185.120.57.125",
        user="admin",
        password="v8S7b$82j51d1",
        database="crypto"
    )

def get_connection():
    if 'conn' not in st.session_state:
        st.session_state.conn = init_connection()
    return st.session_state.conn

@st.cache_data(ttl=5*60)
def fetch_data(_conn, date_from=None, date_to=None):
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
    AND (etherdrop_parser.platfor_name_to = 'Uniswap' 
    OR etherdrop_parser.platfor_name_from = 'Uniswap');
    """

    if date_from and date_to:
        query += " AND etherdrop_parser.datetime BETWEEN %s AND %s"
        df = pd.read_sql(query, _conn, params=[date_from, date_to])
    else:
        df = pd.read_sql(query, _conn)
    
    return df

def make_wallet_address_link(wallet_address):
    return f"https://www.alphatrace.xyz/wallet/{wallet_address}"

def create_wallet_chart(df):
    fig = go.Figure()
    
    df_grouped = df.groupby(['datetime', 'currency_name', 'wallet_type'])['dollar_value'].sum().reset_index()
    
    currencies = df_grouped['currency_name'].unique()
    
    bar_width = 5 * 60 * 60 * 1000 / 2
    
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
            text=[currency] * len(buy_data),
            width=bar_width
        ))
        
        fig.add_trace(go.Bar(
            x=sell_data['datetime'],
            y=sell_data['dollar_value'],
            name=f'Продажа ({currency})',
            marker_color='rgb(214, 69, 69)',
            hovertemplate='Валюта: %{text}<br>Дата: %{x}<br>Объем продажи: $%{y:.2f}<extra></extra>',
            text=[currency] * len(sell_data),
            width=bar_width
        ))
    
    fig.update_layout(
        xaxis_title='Дата',
        yaxis_title='Объем (USD)',
        barmode='group',
        hovermode='closest',
        width=1000,
        height=450
    )
    
    fig.update_xaxes(
        range=[df['datetime'].min() - pd.Timedelta(days=1), 
               df['datetime'].max() + pd.Timedelta(days=1)]
    )
    
    return fig

def dataframe_with_selections(df, column_config=None, use_container_width=False, height=None):
    df_with_selections = df.copy()
    df_with_selections.insert(0, "Select", False)
    
    if column_config is None:
        column_config = {}
    
    column_config["Select"] = st.column_config.CheckboxColumn(required=True)
    
    edited_df = st.data_editor(
        df_with_selections,
        hide_index=True,
        column_config=column_config,
        disabled=df.columns,
        use_container_width=use_container_width,
        height=height
    )
    selected_indices = list(np.where(edited_df.Select)[0])
    selected_rows = df[edited_df.Select]
    return {"selected_rows_indices": selected_indices, "selected_rows": selected_rows}
    
def main():
    today = datetime.datetime.now().replace(microsecond=0)
    yesterday = today - datetime.timedelta(hours=24)

    if 'date_range' not in st.session_state:
        st.session_state.date_range = [yesterday, today]

    def update_date_range(start_date, end_date):
        st.session_state.date_range = [start_date, end_date]

    st.sidebar.subheader("Быстрый выбор дат")
    if st.sidebar.button("Последние 24 часа"):
        update_date_range(today - datetime.timedelta(hours=24), today)
    if st.sidebar.button("Последние 3 дня"):
        update_date_range(today - datetime.timedelta(days=2), today)
    if st.sidebar.button("Последние 7 дней"):
        update_date_range(today - datetime.timedelta(days=6), today)
    if st.sidebar.button("Текущий месяц"):
        update_date_range(today.replace(day=1), today)
    if st.sidebar.button("Все время"):
        update_date_range(datetime.datetime(2000, 1, 1), today)

    date_range = st.sidebar.date_input("Выберите диапазон дат", st.session_state.date_range)

    if date_range != st.session_state.date_range:
        st.session_state.date_range = date_range

    if len(date_range) == 2:
        date_from, date_to = date_range
        date_from = pd.Timestamp(date_from)
        date_to = pd.Timestamp(date_to) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)

        conn = get_connection()
        df = fetch_data(conn, date_from, date_to)

        df['datetime'] = pd.to_datetime(df['datetime'])

        detailed_info = df.groupby(['currency_name', 'wallet_address', 'datetime', 'wallet_type'])['dollar_value'].sum().reset_index()
        detailed_info = detailed_info.sort_values(['currency_name', 'wallet_address', 'datetime'], ascending=[True, True, False])

        currency_summary = df.groupby(['currency_name']).agg({
            'wallet_address': lambda x: x[df['wallet_type'] == 'кошелек покупки'].nunique(),
            'dollar_value': lambda x: (x * (df['wallet_type'] == 'кошелек покупки')).sum()
        }).rename(columns={'wallet_address': 'buy_wallets_count', 'dollar_value': 'buy_volume'})
        
        currency_summary['sell_wallets_count'] = df[df['wallet_type'] == 'кошелек продажи'].groupby(['currency_name'])['wallet_address'].nunique()
        currency_summary['sell_volume'] = df[df['wallet_type'] == 'кошелек продажи'].groupby(['currency_name'])['dollar_value'].sum()
        currency_summary = currency_summary.reset_index()

        col1, col2 = st.columns([2, 3])

        with col1:
            st.subheader("Выбор валют")
            selection = dataframe_with_selections(
                currency_summary[['currency_name', 'buy_wallets_count', 'buy_volume','sell_wallets_count','sell_volume']],
                column_config={
                    "currency_name": "Currency",
                    "buy_volume": st.column_config.NumberColumn("Buy Volume", format="%.2f"),
                    "sell_volume": st.column_config.NumberColumn("Sell Volume", format="%.2f"),
                    "buy_wallets_count": st.column_config.NumberColumn("Buy Wallets", format="%d"),
                    "sell_wallets_count": st.column_config.NumberColumn("Sell Wallets", format="%d")
                },
                use_container_width=True,
                height=530
            )
            selected_currencies = selection["selected_rows"]["currency_name"].tolist()

            st.subheader("Информация по кошелькам")
            if selected_currencies:
                filtered_df = df[df['currency_name'].isin(selected_currencies)]
                
                filtered_wallet_info = filtered_df.groupby('wallet_address').agg({
                    'dollar_value': lambda x: [
                        (x * (filtered_df['wallet_type'] == 'кошелек покупки')).sum(),
                        (x * (filtered_df['wallet_type'] == 'кошелек продажи')).sum()
                    ]
                }).reset_index()
                
                filtered_wallet_info[['buy_volume', 'sell_volume']] = pd.DataFrame(filtered_wallet_info['dollar_value'].tolist(), index=filtered_wallet_info.index)
                filtered_wallet_info = filtered_wallet_info.drop('dollar_value', axis=1)
                
                filtered_wallet_info['wallet_link'] = filtered_wallet_info['wallet_address'].apply(make_wallet_address_link)
                filtered_wallet_info = filtered_wallet_info.rename(columns={'wallet_link': 'Wallet Link'})
            else:
                filtered_wallet_info = df.groupby('wallet_address').agg({
                    'dollar_value': lambda x: [
                        (x * (df['wallet_type'] == 'кошелек покупки')).sum(),
                        (x * (df['wallet_type'] == 'кошелек продажи')).sum()
                    ]
                }).reset_index()
                filtered_wallet_info[['buy_volume', 'sell_volume']] = pd.DataFrame(filtered_wallet_info['dollar_value'].tolist(), index=filtered_wallet_info.index)
                filtered_wallet_info = filtered_wallet_info.drop('dollar_value', axis=1)
                filtered_wallet_info['wallet_link'] = filtered_wallet_info['wallet_address'].apply(make_wallet_address_link)
                filtered_wallet_info = filtered_wallet_info.rename(columns={'wallet_link': 'Wallet Link'})
            
            st.dataframe(
                filtered_wallet_info[['wallet_address', 'buy_volume', 'sell_volume', 'Wallet Link']],
                column_config={
                    "Wallet Link": st.column_config.LinkColumn(
                        label="Wallet Address",
                        display_text="Link",
                        help="Click to open wallet"
                    ),
                    "buy_volume": st.column_config.NumberColumn("Buy Volume", format="%.2f"),
                    "sell_volume": st.column_config.NumberColumn("Sell Volume", format="%.2f")
                },
                hide_index=True,
                use_container_width=True,
                height=400
            )

        with col2:
            st.subheader("График объемов покупок и продаж")
            if selected_currencies:
                filtered_df = df[df['currency_name'].isin(selected_currencies)]
            else:
                filtered_df = df
            chart = create_wallet_chart(filtered_df)
            st.plotly_chart(chart, use_container_width=True, height=500)  

            st.subheader("Детальная информация")
            if selected_currencies:
                filtered_detailed_info = detailed_info[detailed_info['currency_name'].isin(selected_currencies)]
            else:
                filtered_detailed_info = detailed_info
            st.dataframe(filtered_detailed_info, use_container_width=True, height=400)

    else:
        st.error("Пожалуйста, выберите диапазон дат.")

if __name__ == "__main__":
    main()
