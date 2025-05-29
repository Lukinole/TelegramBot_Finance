import sqlite3
import csv

def export_to_csv(db_file, csv_file):
    """Экспортирует данные из базы данных в CSV файл."""
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Извлечение данных из таблицы user_data
    cursor.execute('SELECT * FROM user_data')
    user_data_rows = cursor.fetchall()

    # Извлечение данных из таблицы transactions
    cursor.execute('SELECT * FROM transactions')
    transaction_rows = cursor.fetchall()

    conn.close()

    # Запись данных в CSV файл
    with open(csv_file, 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)

        # Запись заголовков для user_data
        writer.writerow(['user_id', 'final_balance', 'changes', 'dates', 'categories'])
        writer.writerows(user_data_rows)

        # Пустая строка между таблицами
        writer.writerow([])

        # Запись заголовков для transactions
        writer.writerow(['id', 'user_id', 'amount', 'date', 'category'])
        writer.writerows(transaction_rows)

    print(f"Данные успешно экспортированы в {csv_file}")

# Пример использования
export_to_csv('user_info.db', 'exported_data.csv')
