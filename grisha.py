import requests
import sqlite3
from bs4 import BeautifulSoup


class CrawlerAIF:

    BASE_URL = 'https://aif.ru/search'

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:157.0) Gecko/20100101 Firefox/157.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://aif.ru/',
    }

    PARAMS = {
        'text': 'спбгу',
    }

    def __init__(self):
        self.keywords = []
        self.data = []

    def get_database_keywords(self):
        conn = sqlite3.connect('db.sqlite3')
        cursor = conn.cursor()

        query = 'SELECT keyword FROM keywords'
        cursor.execute(query)
        keywords = cursor.fetchall()

        for keyword in keywords:
            self.keywords.append(keyword[0])

        cursor.close()
        conn.close()

    def extract(self, html):
        soup = BeautifulSoup(html, 'html.parser')

        # Находим карточки новостей. Этот класс мы нашли в HTML на AIF.
        articles = soup.select('div.text_box.no_title_element_js')

        for article in articles:
            title_tag = article.select_one('h3')
            date_tag = article.select_one('.text_box__date')

            if title_tag is None:
                continue

            # В найденной разметке ссылка находится вокруг заголовка.
            link_tag = title_tag.find_parent('a')

            if link_tag is None:
                continue

            # Описание идёт следующим span после даты.
            description_tag = None
            if date_tag:
                description_tag = date_tag.find_next_sibling('span')

            title = title_tag.get_text(strip=True)
            url = link_tag.get('href')
            pubdate = date_tag.get_text(strip=True) if date_tag else None
            text = description_tag.get_text(strip=True) if description_tag else ''

            self.data.append({
                'url': url,
                'title': title,
                'text': text,
                'pubdate': pubdate
            })

    def insert_data(self, data):
        conn = sqlite3.connect('db.sqlite3')
        cursor = conn.cursor()

        for article in data:
            # Не добавляем статью, если такой URL уже есть в базе.
            cursor.execute('SELECT id FROM articles WHERE url = ?', (article['url'],))

            if cursor.fetchone() is None:
                # Дата на AIF приходит как 03.11.2026 15:58.
                # Переставляем части даты, а SQLite превращает её в Unix timestamp.
                date_sql = None
                if article['pubdate']:
                    try:
                        date_parts = article['pubdate'].split()
                        day, month, year = date_parts[0].split('.')
                        date_sql = year + '-' + month + '-' + day + ' ' + date_parts[1] + ':00+03:00'
                    except:
                        date_sql = None

                query = """INSERT INTO articles (url, title, text, pubdate)
                             VALUES (?, ?, ?, CAST(strftime('%s', ?) AS INTEGER))"""

                cursor.execute(query, (
                    article['url'],
                    article['title'],
                    article['text'],
                    date_sql
                ))
                print('INSERT URL', article['url'], 'SUCCESS')
            else:
                print('URL ALREADY EXISTS:', article['url'])

        conn.commit()
        cursor.close()
        conn.close()

    def make_request(self, keyword):
        self.data = []

        params = self.PARAMS.copy()
        params['text'] = keyword

        response = requests.get(
            self.BASE_URL,
            params=params,
            headers=self.HEADERS
        )
        response.raise_for_status()

        print('Запрос:', response.url)

        self.extract(response.text)
        print('Найдено статей:', len(self.data))

        self.insert_data(self.data)


def main():
    crawler = CrawlerAIF()
    crawler.get_database_keywords()

    for keyword in crawler.keywords:
        print('\nИщем:', keyword)
        crawler.make_request(keyword)


if __name__ == '__main__':
    main()