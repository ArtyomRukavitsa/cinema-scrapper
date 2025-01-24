import scrapy
from cinema.items import CinemaItem

# Хэдер для доступа к IMDb
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Referer': 'https://www.imdb.com/'
}


def extract_text_or_default(selector, css_query, default=""):
    return selector.css(css_query).extract_first() or default


def extract_list_or_default(selector, css_queries, default=""):
    for query in css_queries:
        result = selector.css(query).extract()
        if result:
            return result
    return [default]


# Парсим табличку с информацией о фильме
def parse_table_rows(selector, film):
    for tr in selector.css('tr'):
        th_text = extract_text_or_default(tr, 'th.plainlist::text')

        if th_text:  # Если есть текст в <th> (т.е. страна, режиссер, продюсер, год, проч.)
            if 'Режиссёр' in th_text:
                film['director'] = ', '.join(extract_list_or_default(tr, ['td a::text', 'span::text']))
            elif 'Год' in th_text or 'Дата выхода' in th_text or 'Первый показ' in th_text:
                film['year'] = ' '.join(extract_list_or_default(tr, ['a::text', 'span::text', 'td::text']))
            elif 'Стран' in th_text:
                film['country'] = ', '.join(extract_list_or_default(tr, ['span.wrap::text', 'a::text', 'a::attr(title)']))
        else:  # Если <th> пустое, проверяем жанры (но там еще могут быть картинки и прочая информация)
            genre_header = extract_text_or_default(tr, 'th a::text')
            if 'Жанр' in genre_header:
                film['genre'] = ', '.join(extract_list_or_default(tr, ['td a::text', 'td span::text']))

    return film


class WikipediaSpider(scrapy.Spider):
    name = "wikipedia"
    allowed_domains = ["ru.wikipedia.org", "imdb.com"]

    def start_requests(self):
        url = "https://ru.wikipedia.org/wiki/%D0%9A%D0%B0%D1%82%D0%B5%D0%B3%D0%BE%D1%80%D0%B8%D1%8F:" \
              "%D0%A4%D0%B8%D0%BB%D1%8C%D0%BC%D1%8B_%D0%BF%D0%BE_%D0%B0%D0%BB%D1%84%D0%B0%D0%B2%D0%B8%D1%82%D1%83"
        yield scrapy.Request(url=url, callback=self.parse)

    def parse(self, response):
        for selector in response.css("div.mw-category-group"):
            hrefs = selector.css('a::attr(href)').extract()
            title = selector.css('bdi a::text').extract_first() # избавляемся от Мультфильмов и Телесериалов по алфавиту
            if not title:
                for href in hrefs:
                    yield scrapy.Request(url=f"https://ru.wikipedia.org/{href}", callback=self.parse_film)

        href = response.xpath('//a[@title="Категория:Фильмы по алфавиту" and text()="Следующая страница"]/@href').get()
        print(href)
        yield scrapy.Request(url=f"https://ru.wikipedia.org/{href}", callback=self.parse)

    def parse_film(self, response):
        selector = response.css('table tbody')
        for sel in selector:
            if 'infobox-above' in sel.get():
                selector = sel
                break

        film = CinemaItem()
        film = parse_table_rows(selector, film)

        title_selectors = [
            "th.infobox-above::text",
            "th.infobox-above span::text",
            "th.infobox-above i::text",
            "th.infobox-above b::text",
            "th.infobox-above small::text",
            "th.infobox-above a::text"
        ]
        titles = extract_list_or_default(selector, title_selectors)
        title = next((t.strip() for t in titles if t.strip()), None)
        if title:
            film['title'] = title
            imdb_link = selector.xpath('//a[starts-with(@href, "https://www.imdb.com/title/")]/@href').get()
            if imdb_link:
                yield scrapy.Request(url=imdb_link, callback=self.parse_imdb,
                                     meta={'film': film, 'wikipedia_url': response.url}, headers=headers)
            else:
                yield film

    def parse_imdb(self, response):
        rating = response.css("span.ipc-btn__text span::text").extract_first()
        film = response.meta['film']
        film['rating'] = rating
        yield film
