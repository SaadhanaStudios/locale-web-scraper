import re
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import time
from logging.handlers import RotatingFileHandler
import os

# Setup detailed logging with rotation and console output
log_file = 'scraping_log.txt'
logging.basicConfig(
    handlers=[
        RotatingFileHandler(log_file, maxBytes=2000000, backupCount=5),
        logging.StreamHandler()
    ],
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def setup_webdriver():
    """Set up the WebDriver."""
    try:
        options = webdriver.FirefoxOptions()
        options.add_argument('--headless')
        driver = webdriver.Firefox(options=options)
        logging.info("WebDriver setup successfully.")
        return driver
    except Exception as e:
        logging.error(f"Failed to set up WebDriver: {e}")
        raise


def get_recent_urls(log_file='scraping_log.txt'):
    """Get the last 5 scraped URLs and selectors from the summary log."""
    summary_file = 'IngestionSummary.csv'
    recent_urls = []

    if not os.path.exists(summary_file):
        logging.info("IngestionSummary.csv not found. No recent URLs to display.")
        return recent_urls

    try:
        df = pd.read_csv(summary_file)
        recent_records = df.tail(5)  # Get the last 5 records
        for _, row in recent_records.iterrows():
            recent_urls.append((row['URL'], row['Selector']))
        logging.info("Fetched the last 5 recent URLs from IngestionSummary.csv.")
    except Exception as e:
        logging.error(f"Error reading {summary_file}: {e}")

    return recent_urls


def extract_csv_filename(url):
    """Extract the domain and the last part of the URL to use as the CSV file name."""
    try:
        domain = url.split("//")[-1].split("/")[0].replace('www.', '')
        last_part = url.rstrip('/').split("/")[-1]
        filename = f"{domain}-{last_part}".replace(' ', '_').replace('%20', '_').replace('/', '_')
        return filename
    except Exception as e:
        logging.error(f"Error extracting CSV filename from URL: {e}")
        return "default_filename"

def generate_unique_filename(base_path, filename, extension):
    """Generate a unique file name by appending a number if the file already exists."""
    counter = 1
    unique_filename = f"{filename}.{extension}"
    while os.path.exists(os.path.join(base_path, unique_filename)):
        unique_filename = f"{filename}_{counter}.{extension}"
        counter += 1
    return unique_filename


def log_scraping_info(url, article_name):
    """Log scraping information."""
    logging.info(f"Scraping Information - URL: {url}, Article Name: {article_name}")


def scrape_url(driver, url, selector):
    """Scrape the given URL and return the page source."""
    try:
        driver.get(url)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
        element = driver.find_element(By.CSS_SELECTOR, selector)
        html_content = element.get_attribute('outerHTML')
        logging.info(f"Successfully scraped URL: {url} using selector: {selector}")
        return html_content
    except Exception as e:
        logging.error(f"Error scraping {url} with selector {selector}: {e}")
        return ""


def parse_html(html_content):
    """Parse HTML content and return relevant data."""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        genesis_content = soup.find(id='genesis-content')
        article_name = soup.find('h1', class_='entry-title').get_text(strip=True)
        author_date = soup.find('p', class_='entry-meta').get_text(strip=True)
        author, date = author_date.split('•')
        logging.info(f"Successfully parsed HTML content - Article Name: {article_name}, Author: {author}, Date: {date}")
        return soup, genesis_content, article_name, author.strip(), date.strip()
    except Exception as e:
        logging.error(f"Error parsing HTML content: {e}")
        return None, None, "", "", ""


def extract_data(soup, genesis_content, article_name, author, date, url):
    """Extract relevant data from the parsed HTML content."""
    data = []
    current_category = None

    try:
        if genesis_content:
            for tag in genesis_content.find_all(['h2', 'h3']):
                if tag.name == 'h2':
                    current_category = tag.get_text(strip=True)
                elif tag.name == 'h3' and current_category:
                    activity_name = tag.get_text(strip=True)
                    images = [img['src'] for img in tag.find_all_next('img', limit=10) if img.has_attr('src')]
                    description = ' '.join([p.get_text(strip=True) for p in tag.find_all_next('p', limit=10)])
                    external_links = [a['href'] for a in tag.find_all_next('a', limit=10) if a.has_attr('href')]

                    data.append({
                        'Article Name': article_name,
                        'Author': author,
                        'Date': date,
                        'Category': current_category,
                        'Activity Name': activity_name,
                        'Images': ', '.join(images),
                        'Description': description,
                        'External Links': ', '.join(external_links),
                        'URL': url
                    })
            logging.info(f"Successfully extracted data - Article Name: {article_name}, Number of activities: {len(data)}")
        else:
            logging.warning(f"No genesis-content found in the HTML for URL: {url}")
    except Exception as e:
        logging.error(f"Error extracting data from URL: {url}: {e}")

    return data


def save_to_csv(data, html_content, url, selector, method):
    """Save the extracted data to a CSV file and log the summary."""
    try:
        # Create the all_csv_outputs directory if it doesn't exist
        csv_output_folder = 'all_csv_outputs'
        os.makedirs(csv_output_folder, exist_ok=True)

        df = pd.DataFrame(data)
        filename = extract_csv_filename(url)
        output_file = generate_unique_filename(csv_output_folder, filename, 'csv')
        df.to_csv(os.path.join(csv_output_folder, output_file), index=False)
        logging.info(f"CSV file '{output_file}' has been created and saved successfully in '{csv_output_folder}'.")
        
        # Save the raw HTML content
        save_raw_html(html_content, filename)
        
        # Append to summary log
        status = 'Success' if len(df) > 0 else 'No Data'
        append_to_summary_log(url, selector, output_file, len(df), status, method)
    except Exception as e:
        logging.error(f"Error saving CSV file for URL: {url}, Selector: {selector}: {e}")
        append_to_summary_log(url, selector, '', 0, 'Failed', method)




def save_raw_html(html_content, filename):
    """Save the raw HTML content to a file in the previous_scrapes folder."""
    try:
        # Create the previous_scrapes directory if it doesn't exist
        os.makedirs('previous_scrapes', exist_ok=True)
        
        # Generate unique file name
        base_path = 'previous_scrapes'
        unique_filename = generate_unique_filename(base_path, filename, 'html')
        
        # Save the HTML content
        file_path = os.path.join(base_path, unique_filename)
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(html_content)
        logging.info(f"Raw HTML content saved to {file_path}")
    except Exception as e:
        logging.error(f"Error saving raw HTML content for filename: {filename}: {e}")



def append_to_collected_data(data):
    """Append the data to CollectedData.csv, creating the file if it doesn't exist."""
    collected_file = 'CollectedData.csv'
    append_mode = 'a' if os.path.exists(collected_file) else 'w'

    try:
        collected_df = pd.DataFrame(data)
        collected_df.to_csv(collected_file, mode=append_mode, header=(append_mode == 'w'), index=False)
        rows_appended = len(collected_df)
        if append_mode == 'w':
            logging.info(f"CollectedData.csv file created.")
        logging.info(f"{rows_appended} rows appended to CollectedData.csv.")
    except Exception as e:
        logging.error(f"Error appending to CollectedData.csv: {e}")

def append_to_summary_log(url, selector, csv_file, num_rows, status, method):
    """Append the summary details of the ingestion to a summary CSV file."""
    summary_file = 'IngestionSummary.csv'
    expected_columns = ['URL', 'Selector', 'CSV File', 'Number of Rows', 'Date/Time', 'Status', 'Ingestion Method']
    append_mode = 'a' if os.path.exists(summary_file) else 'w'

    try:
        # Create the file with headers if it doesn't exist
        if not os.path.exists(summary_file):
            df = pd.DataFrame(columns=expected_columns)
            df.to_csv(summary_file, index=False)
            logging.info(f"Created {summary_file} as it did not exist.")

        summary_data = {
            'URL': url,
            'Selector': selector,
            'CSV File': csv_file,
            'Number of Rows': num_rows,
            'Date/Time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'Status': status,
            'Ingestion Method': method
        }
        summary_df = pd.DataFrame([summary_data])
        summary_df.to_csv(summary_file, mode=append_mode, header=False, index=False)
        logging.info(f"Appended ingestion summary for {url} to {summary_file}")
    except Exception as e:
        logging.error(f"Error appending to {summary_file}: {e}")







def is_url_ingested(url, selector):
    """Check if the URL and selector combination has already been ingested."""
    summary_file = 'IngestionSummary.csv'
    if not os.path.exists(summary_file):
        return False
    
    try:
        df = pd.read_csv(summary_file)
        return (url, selector) in zip(df['URL'], df['Selector'])
    except Exception as e:
        logging.error(f"Error reading {summary_file}: {e}")
        return False




def check_ingestion_summary(urls):
    """Check if the URL and selector combinations already exist in the ingestion summary."""
    summary_file = 'IngestionSummary.csv'
    if not os.path.exists(summary_file):
        return urls, []

    try:
        summary_df = pd.read_csv(summary_file)
        existing_combinations = set(zip(summary_df['URL'], summary_df['Selector']))
        new_urls = []
        existing_urls = []

        for url_info in urls:
            url_selector_pair = (url_info['URL'], url_info['Selector'])
            if url_selector_pair not in existing_combinations:
                new_urls.append(url_info)
            else:
                existing_urls.append(url_info)

        return new_urls, existing_urls
    except Exception as e:
        logging.error(f"Error reading {summary_file}: {e}")
        return urls, []




def read_urls_from_csv(csv_file='BulkIngestion.csv'):
    """Read URLs and selectors from the given CSV file. Create the file if it doesn't exist."""
    if not os.path.exists(csv_file):
        # Create the file with headers if it doesn't exist
        df = pd.DataFrame(columns=['URL', 'Selector'])
        df.to_csv(csv_file, index=False)
        logging.info(f"Created {csv_file} as it did not exist.")
        return []

    try:
        df = pd.read_csv(csv_file)
        if 'URL' not in df.columns or 'Selector' not in df.columns:
            logging.error("CSV file must contain 'URL' and 'Selector' columns.")
            return []
        return df.to_dict('records')
    except Exception as e:
        logging.error(f"Error reading {csv_file}: {e}")
        return []


def deduplicate_urls(urls):
    """Deduplicate the list of URLs and selectors."""
    seen = set()
    unique_urls = []
    duplicates = []

    for url_info in urls:
        url_selector_pair = (url_info['URL'], url_info['Selector'])
        if url_selector_pair not in seen:
            seen.add(url_selector_pair)
            unique_urls.append(url_info)
        else:
            duplicates.append(url_info)

    return unique_urls, duplicates



def clear_csv_file(csv_file='BulkIngestion.csv'):
    """Clear the contents of the given CSV file but keep the column headers."""
    try:
        df = pd.DataFrame(columns=['URL', 'Selector'])
        df.to_csv(csv_file, index=False)
        logging.info(f"Cleared the contents of {csv_file} but kept the headers")
    except Exception as e:
        logging.error(f"Error clearing {csv_file}: {e}")






def get_previous_selector(url):
    """Retrieve the previous selector used for the given URL from the summary log."""
    summary_file = 'IngestionSummary.csv'
    try:
        df = pd.read_csv(summary_file)
        record = df[df['URL'] == url]
        if not record.empty:
            return record.iloc[-1]['Selector']
    except Exception as e:
        logging.error(f"Error reading {summary_file}: {e}")
    return None

def get_user_input(recent_urls):
    """Prompt the user to enter a URL and selector or use recent ones."""
    print("Recently scraped URLs:")
    for url, selector in recent_urls:
        print(f"URL: {url}, Selector: {selector}")

    url = input("Please enter the URL you want to scrape (or press 'p' for the most recent URL): ")

    if url.lower() == 'p':
        if recent_urls:
            url, previous_selector = recent_urls[-1]
            print(f"Using the most recently scraped URL: {url}")
            use_previous = input(f"Use the previous selector '{previous_selector}'? (y/n): ")
            selector = previous_selector if use_previous.lower() == 'y' else input("Please enter a new CSS selector to use (default 'main'): ") or "main"
        else:
            print("No recent URLs found. Please enter a URL.")
            return None, None
    else:
        selector = input("Please enter the CSS selector to use (default 'main'): ") or "main"
    
    return url, selector


def handle_duplicates(existing_urls, new_urls):
    """Handle duplicate URL and selector combinations during bulk ingestion."""
    if existing_urls:
        for url_info in existing_urls:
            print(f"URL and selector already ingested: {url_info}")
        action = input("Some URL and selector combinations have already been ingested. Do you want to (c)ontinue, (s)kip, or (a)bort?: ")

        if action.lower() == 'a':
            print("Ingestion aborted.")
            logging.info(f"Ingestion aborted due to existing URL and selector combinations: {existing_urls}")
            return [], False
        elif action.lower() == 's':
            new_urls = [url_info for url_info in new_urls if url_info not in existing_urls]
            print(f"Skipped URL and selector combinations: {existing_urls}")
            logging.info(f"Skipped URL and selector combinations: {existing_urls}")
        elif action.lower() == 'c':
            print(f"Continuing without processing existing URL and selector combinations: {existing_urls}")
            logging.info(f"Continuing without processing existing URL and selector combinations: {existing_urls}")

    return new_urls, True



def process_urls(urls, method):
    """Process each URL and selector combination."""
    driver = setup_webdriver()
    
    for url_info in urls:
        url = url_info['URL']
        selector = url_info['Selector'] or "main"  # Ensure default selector

        # Scrape the URL
        page_source = scrape_url(driver, url, selector)

        if not page_source:
            print(f"Failed to scrape the URL: {url}")
            continue

        # Parse the HTML content
        soup, genesis_content, article_name, author, date = parse_html(page_source)

        if not article_name:
            print(f"Failed to parse the HTML content for URL: {url}")
            continue

        # Log the scraping information
        log_scraping_info(url, article_name)

        # Extract data
        data = extract_data(soup, genesis_content, article_name, author, date, url)

        # Save the data to a CSV file
        save_to_csv(data, page_source, url, selector, method)

        # Append the data to CollectedData.csv
        append_to_collected_data(data)

    driver.quit()


def main():
    urls = read_urls_from_csv()

    if not urls:
        recent_urls = get_recent_urls()
        url, selector = get_user_input(recent_urls)
        if not url:
            return

        method = 'Manual'
        
        if is_url_ingested(url, selector):
            continue_scraping = input("This URL and selector combination has already been ingested. Do you want to continue? (y/n): ")
            if continue_scraping.lower() != 'y':
                print("Scraping aborted.")
                return

        process_urls([{'URL': url, 'Selector': selector}], method)
    else:
        unique_urls, duplicates = deduplicate_urls(urls)

        if duplicates:
            logging.info(f"Skipped duplicate URLs and selectors within bulk file: {duplicates}")
            print(f"Skipped duplicate URLs and selectors within bulk file: {duplicates}")

        new_urls, existing_urls = check_ingestion_summary(unique_urls)
        new_urls, should_continue = handle_duplicates(existing_urls, new_urls)

        if should_continue:
            method = 'Bulk'
            process_urls(new_urls, method)
            clear_csv_file()

if __name__ == "__main__":
    main()

