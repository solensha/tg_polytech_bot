from aiohttp import web
import sqlite3
import json


def links(chats_links):
    links_database = sqlite3.connect('database.db')
    cursor = links_database.cursor()
    cursor.execute('''
           CREATE TABLE IF NOT EXISTS Links (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               chat_url TEXT
           )
       ''')
    for link in chats_links:
        cursor.execute("SELECT COUNT(*) AS count FROM Links WHERE chat_url = ?", (link,))
        result = cursor.fetchone()
        if result[0] == 0:
            cursor.execute("INSERT INTO Links (chat_url) VALUES (?)", (link,))
            links_database.commit()


def get_links():
    try:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("SELECT chat_url FROM Links LIMIT 1")
        result = cursor.fetchone()
        if result:
            chat_url = result[0]
            cursor.execute("DELETE FROM Links WHERE chat_url = ?", (chat_url,))
            conn.commit()
            cursor.close()
            conn.close()
            return chat_url
    except Exception as e:
        print(f"Ошибка: {e}")


async def handle_add_links(request):
    urls = await request.json()
    chats_links = []
    for url in urls['urls']:
        if not url.startswith('https://t.me/'):
            return web.Response(text='Некорректные ссылки на чаты', status=400)
        chats_links.append(url)
    links(chats_links)
    return web.Response(text='Ссылки добавлены')


def handle_get_links(request):
    try:
        chat_link = get_links()
        data = json.dumps(chat_link)
        with open('links.json', 'w') as f:
            f.write(data)
        return web.Response(body=data, content_type='application/json')
    except Exception as e:
        print(f'Error: {e}')
        return web.Response(text="Произошла ошибка.")


def handle_get_all_links(request):
    links_database = sqlite3.connect('database.db')
    cursor = links_database.cursor()
    chats = cursor.execute("SELECT chat_url FROM Links")
    chat_urls = [chat[0] for chat in chats]
    json_chat_urls = json.dumps(chat_urls)
    return web.Response(body=json_chat_urls, content_type='application/json')


app = web.Application()
app.router.add_get('/link', handle_get_links)
app.router.add_get('/all_links', handle_get_all_links)
app.router.add_post('/add', handle_add_links)

if __name__ == "__main__":
    web.run_app(app, port=80)
