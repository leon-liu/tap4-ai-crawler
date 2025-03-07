import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urlunparse
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
import random
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

def create_session():
    """Create a session with retry strategy and custom headers"""
    session = requests.Session()
    
    # Configure retry strategy
    retries = Retry(
        total=5,  # number of retries
        backoff_factor=1,  # wait 1, 2, 4, 8, 16 seconds between retries
        status_forcelist=[500, 502, 503, 504]
    )
    
    # Mount the adapter to the session
    session.mount('http://', HTTPAdapter(max_retries=retries))
    session.mount('https://', HTTPAdapter(max_retries=retries))
    
    # Add user agent to appear more like a regular browser
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    })
    
    return session

def parse_sitemap_index(sitemap_url):
    """Parse the main sitemap index and return all sub-sitemap URLs"""
    session = create_session()
    time.sleep(random.uniform(1, 3))  # Random delay between 1-3 seconds
    response = session.get(sitemap_url)
    root = ET.fromstring(response.content)
    
    sitemap_urls = []
    for sitemap in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc'):
        sitemap_urls.append(sitemap.text)
    
    return sitemap_urls

def parse_sub_sitemap(sitemap_url):
    """Parse each sub-sitemap and extract tool URLs"""
    session = create_session()
    time.sleep(random.uniform(2, 5))  # Random delay between 2-5 seconds
    response = session.get(sitemap_url)
    root = ET.fromstring(response.content)
    
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    
    tool_urls = []
    for url in root.findall('.//ns:loc', namespaces=ns):
        if '/en/tool/' in url.text:
            tool_urls.append(url.text)
    
    print(f"{sitemap_url} Found {len(tool_urls)} tool URLs")
    print(tool_urls)
    return tool_urls

def extract_open_site_url(page_url):
    """Extract the open site URL from a tool page"""
    session = create_session()
    time.sleep(random.uniform(3, 7))  # Random delay between 3-7 seconds
    
    try:
        response = session.get(page_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find span with "Open site" text, then get its parent 'a' tag
        open_site_span = soup.find('span', string='Open site')
        if open_site_span and open_site_span.parent.name == 'a':
            url = open_site_span.parent['href']
            parsed_url = urlparse(url)
            clean_url = urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, '', '', ''))
            print(f"Successfully extracted URL from {page_url}: {clean_url}")
            return clean_url
        else:
            print(f"No 'Open site' link found on {page_url}")
            return None
    except Exception as e:
        print(f"Error processing {page_url}: {str(e)}")
        return None

def save_to_google_sheets(data):
    """Save the collected data to Google Sheets"""
    try:
        # Set up Google Sheets API credentials
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name('link-crawler-452902-36160d579053.json', scope)
        client = gspread.authorize(creds)

        try:
            # List available spreadsheets to debug
            available_sheets = client.openall()
            print("\nAvailable spreadsheets:")
            for sheet in available_sheets:
                print(f"- {sheet.title}")

            # Open the specified Google Sheet
            #sheet = client.open("www.toolify.ai")  # Replace with your exact spreadsheet name
            sheet = client.open_by_key('1fr6_KuehJqGvW-8hT5XtDlk7uaA-M3yYxJtKh5i-qOs')  # Get ID from the URL
            worksheet = sheet.sheet1
            print(f"\n✅ Successfully opened sheet: {sheet.title}")
            
        except Exception as sheet_error:
            print("\n❌ Sheet Access Error:")
            print(f"Detailed error: {str(sheet_error)}")
            print("Make sure:")
            print("1. The spreadsheet name is exactly correct (case-sensitive)")
            print("2. You've shared the spreadsheet with the service account email")
            print("3. The service account has edit permissions")
            return False

        # Write data in batches to avoid API limits
        batch_size = 100
        rows_saved = 0
        
        print(f"\nStarting to save {len(data)} rows of data...")
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            try:
                for row in batch:
                    worksheet.append_row(row)  # Use worksheet instead of sheet
                    rows_saved += 1
                    time.sleep(1)  # Avoid Google Sheets API rate limits
                print(f"✅ Successfully saved batch of {len(batch)} rows (Total: {rows_saved})")
            except Exception as batch_error:
                print(f"❌ Error saving batch starting at row {i}:")
                print(f"Detailed error: {str(batch_error)}")
                print("This might be due to API rate limits or invalid data format")
                print(f"Last successful save was at row {rows_saved}")
                return False
        
        print(f"\n✅ Successfully completed! Total rows saved: {rows_saved}")
        return True
            
    except Exception as e:
        print(f"Error saving to Google Sheets: {str(e)}")

def test_url_extraction():
    """Test function to verify extract_open_site_url functionality with multiple URLs"""
    # List of test URLs
    test_urls = [
        "https://www.toolify.ai/en/tool/eazyrag",
        "https://www.toolify.ai/en/tool/gptsmith",
        # Add more test URLs as needed
    ]
    
    for test_url in test_urls:
        print(f"\nTesting URL extraction with: {test_url}")
        print("----------------------------------------")
        
        try:
            result = extract_open_site_url(test_url)
            if result:
                print(f"✅ Success!")
                print(f"Original URL: {test_url}")
                print(f"Extracted URL: {result}")
            else:
                print("❌ Failed to extract URL")
                print("No URL was found on the page")
                
        except Exception as e:
            print("❌ Error during extraction:")
            print(f"Error details: {str(e)}")
        
        print("----------------------------------------")

def test_google_sheets_save():
    """Test function to verify save_to_google_sheets functionality"""
    # Test data - sample URLs and their corresponding open site URLs
    test_data = [
        ["https://www.toolify.ai/en/tool/eazyrag", "https://eazyrag.com"],
        ["https://www.toolify.ai/en/tool/gptsmith", "https://gptsmith.app"]
    ]
    
    print("\nTesting Google Sheets saving functionality")
    print("----------------------------------------")
    print(f"Test data to save ({len(test_data)} rows):")
    for row in test_data:
        print(f"Tool URL: {row[0]}")
        print(f"Open Site URL: {row[1]}")
        print("---")
    
    try:
        print("\nAttempting to save to Google Sheets...")
        save_to_google_sheets(test_data)
        print("✅ Success! Data was saved to Google Sheets")
        
    except Exception as e:
        print("❌ Error saving to Google Sheets:")
        print(f"Error details: {str(e)}")
        
        # Additional error information for common issues
        if "credentials" in str(e).lower():
            print("\nTip: Make sure 'credentials.json' file exists and has correct permissions")
        elif "not found" in str(e).lower():
            print("\nTip: Verify the Google Sheet name is correct")
        elif "quota" in str(e).lower():
            print("\nTip: You might have hit Google Sheets API quota limits. Wait a while and try again")
    
    print("----------------------------------------")
    
def get_last_processed_url():
    """Get the last URL processed from Google Sheets"""
    try:
        print("\nChecking last processed URL in Google Sheets...")
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name('link-crawler-452902-36160d579053.json', scope)
        client = gspread.authorize(creds)
        
        sheet = client.open_by_key('1fr6_KuehJqGvW-8hT5XtDlk7uaA-M3yYxJtKh5i-qOs')
        worksheet = sheet.sheet1
        
        # Get all values from first column (toolify URLs)
        all_values = worksheet.col_values(1)
        if all_values:
            last_url = all_values[-1]  # Get the last URL
            print(f"Found last processed URL: {last_url}")
            return last_url
        else:
            print("No URLs found in sheet, starting from beginning")
            return None
            
    except Exception as e:
        print(f"Error checking last URL: {str(e)}")
        return None

def main(auto_resume=True):
    main_sitemap_url = 'https://toolify.ai/sitemap.xml'
    
    try:
        # Get last processed URL if auto-resuming
        start_from_url = None
        if auto_resume:
            start_from_url = get_last_processed_url()
        
        # Get all sub-sitemap URLs
        print("Parsing main sitemap...")
        sub_sitemaps = parse_sitemap_index(main_sitemap_url)
        print(f"Found {len(sub_sitemaps)} sub-sitemaps")
        
        # Collect all tool URLs
        all_tool_urls = []
        for sub_sitemap in sub_sitemaps:
            tool_urls = parse_sub_sitemap(sub_sitemap)
            all_tool_urls.extend(tool_urls)
        
        print(f"\nTotal tool URLs found: {len(all_tool_urls)}")
        
        # Find starting index if resuming
        start_index = 0
        if start_from_url:
            try:
                start_index = all_tool_urls.index(start_from_url)
                # Start from the next URL after the last processed one
                start_index += 1
                print(f"Resuming from next URL after: {start_from_url}")
                print(f"Starting at index: {start_index}")
            except ValueError:
                print(f"Warning: Last processed URL not found in current list, beginning from start")
        
        # Process each tool URL from the starting point
        results = []
        for i, url in enumerate(all_tool_urls[start_index:], start_index + 1):
            print(f"\nProcessing URL {i}/{len(all_tool_urls)}: {url}")
            open_site_url = extract_open_site_url(url)
            if open_site_url:
                results.append([url, open_site_url])
        
        print(f"\nSuccessfully processed {len(results)} URLs")
        
        # Save results to Google Sheets
        if results:
            print("\nSaving results to Google Sheets...")
            save_to_google_sheets(results)
            print("Data successfully saved to Google Sheets")
        else:
            print("No results to save")
            
    except Exception as e:
        print(f"An error occurred in main execution: {str(e)}")

if __name__ == '__main__':
    #test_google_sheets_save()
    #test_url_extraction
    # Auto-resume from last processed URL
    main(auto_resume=True)
