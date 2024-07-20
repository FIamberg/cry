def main():
    st.title('Wallets')

    today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - datetime.timedelta(days=7)

    # Инициализация состояния для хранения выбранного диапазона дат
    if 'date_range' not in st.session_state:
        st.session_state.date_range = [week_ago, today]

    # Функция для обновления диапазона дат
    def update_date_range(start_date, end_date):
        st.session_state.date_range = [start_date, end_date]

    # Добавляем кнопки для быстрого выбора диапазона дат
    st.sidebar.subheader("Быстрый выбор дат")
    if st.sidebar.button("Последние 3 дня"):
        update_date_range(today - datetime.timedelta(days=2), today)
    if st.sidebar.button("Последние 7 дней"):
        update_date_range(today - datetime.timedelta(days=6), today)
    if st.sidebar.button("Текущий месяц"):
        update_date_range(today.replace(day=1), today)
    if st.sidebar.button("Все время"):
        update_date_range(datetime.datetime(2000, 1, 1), today)

    # Добавляем календарь для выбора дат
    date_range = st.sidebar.date_input("Выберите диапазон дат", st.session_state.date_range)

    # Обновляем session_state.date_range, если пользователь изменил даты через календарь
    if date_range != st.session_state.date_range:
        st.session_state.date_range = date_range

    if len(date_range) == 2:
        date_from, date_to = date_range
        date_from = pd.Timestamp(date_from)
        date_to = pd.Timestamp(date_to) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)

        df = fetch_data(date_from, date_to)
