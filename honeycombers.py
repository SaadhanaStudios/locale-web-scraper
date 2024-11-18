import logging
from bs4 import BeautifulSoup

def parse_html(html_content, url):
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        main_content = soup.select_one("#genesis-content")
        article_title = soup.select_one("h1.entry-title").get_text(strip=True)
        author_date = soup.select_one("p.entry-meta").get_text(strip=True)
        author, date = author_date.split('•')
        
        data = []

        current_category = None
        for tag in main_content.find_all(['h2', 'h3']):
            if tag.name == 'h2':
                current_category = tag.get_text(strip=True)
            elif tag.name == 'h3' and current_category:
                activity_name = tag.get_text(strip=True)
                images = [img['src'] for img in tag.find_all_next('img', limit=10) if img.has_attr('src')]
                description = ' '.join([p.get_text(strip=True) for p in tag.find_all_next('p', limit=10)])
                external_links = [a['href'] for a in tag.find_all_next('a', limit=10) if a.has_attr('href')]

                data.append({
                    'Article Name': article_title,
                    'Author': author.strip(),
                    'Date': date.strip(),
                    'Category': current_category,
                    'Activity Name': activity_name,
                    'Images': ', '.join(images),
                    'Description': description,
                    'External Links': ', '.join(external_links),
                    'URL': url
                })
        logging.info(f"Successfully parsed HTML content for {url}")
        return data

    except Exception as e:
        logging.error(f"Error parsing HTML content for {url}: {e}")
        return []
