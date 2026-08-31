import os
import json
import time
import requests
import xml.etree.ElementTree as ET
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz

# Environment Variables setup
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
SPREADSHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "1zxVYJ0Xj7MzwEQzXST2oUBHDc42NDm4KrncwhaUlfRk")
CREDENTIALS_FILE = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "service-account.json")
RSS_URL = os.environ.get("RSS_URL", "https://www.amarujala.com/rss/uttarakhand.xml")
TIMEZONE = os.environ.get("TIMEZONE", "Asia/Kolkata")

genai.configure(api_key=GEMINI_API_KEY)

def fetch_news_from_rss():
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(RSS_URL, headers=headers)
    
    articles = []
    if response.status_code == 200:
        root = ET.fromstring(response.content)
        for item in root.findall('./channel/item'):
            title = item.find('title').text if item.find('title') is not None else ""
            link = item.find('link').text if item.find('link') is not None else ""
            description = item.find('description').text if item.find('description') is not None else ""
            
            if title and link:
                articles.append({
                    "title": title,
                    "link": link,
                    "description": description
                })
    return articles[:10]

def extract_structured_data(news_item, today_date_str):
    model = genai.GenerativeModel('gemini-3.6-flash')
    
    prompt = f"""
    Aapko Uttarakhand News parse karni hai aur Ground Impact Assessment Sheet ke exact format me extract karna hai.
    
    News Title: {news_item['title']}
    News Link: {news_item['link']}
    News Summary: {news_item['description']}

    Rules:
    1. Check karo kya isme Uttarakhand Government, Administration, PWD, Health, Jal Sansthan, Drainage, School, Transport, ya public issue me govt ka action required hai?
    2. Agar Govt ka koi role nahi hai, to JSON me "is_relevant": false return karo.
    3. Agar Govt/Admin issue hai, to details strictly is format me do:
       - Vidhansabha: Uttarakhand ki 70 Vidhansabha me se exact naam (e.g. "ऋषिकेश (संख्या 24)", "डोईवाला (23)").
       - Vidhayak: Us Vidhansabha ka Vidhayak aur party (e.g. "प्रेमचंद अग्रवाल (BJP)").
       - Location: Exact gaon, tehsil, ya chowk (e.g. "अमरपुर (रुद्रपुर)").
       - Issue: Samasya ka pura detail vivaran Hindi me.
       - Link: News URL ("{news_item['link']}")
       - POC: News portal / Channel ("अमर उजाला")
       - Date: Exact date format ("{today_date_str}")

    Strictly return JSON only:
    {{
      "is_relevant": true,
      "Vidhansabha": "...",
      "Vidhayak": "...",
      "Location": "...",
      "Issue": "...",
      "Link": "{news_item['link']}",
      "POC": "अमर उजाला",
      "Date": "{today_date_str}"
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        clean_json = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_json)
        return data
    except Exception as e:
        print(f"Error parsing news item: {e}")
        return None

def append_to_sheet(rows_data, today_tab_name):
    if not rows_data:
        print("No new relevant news found today.")
        return

    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)
    
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    
    try:
        sheet = spreadsheet.worksheet(today_tab_name)
        print(f"Found existing tab: {today_tab_name}")
    except gspread.exceptions.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title=today_tab_name, rows=100, cols=10)
        print(f"Created new tab: {today_tab_name}")
        headers = ["Vidhansabha", "Vidhayak", "Location", "Issue", "Link", "POC", "Date"]
        sheet.append_row(headers)

    for row_data in rows_data:
        row = [
            row_data.get("Vidhansabha", ""),
            row_data.get("Vidhayak", ""),
            row_data.get("Location", ""),
            row_data.get("Issue", ""),
            row_data.get("Link", ""),
            row_data.get("POC", "अमर उजाला"),
            row_data.get("Date", "")
        ]
        sheet.append_row(row)
        print(f"Successfully appended row to tab '{today_tab_name}': {row[0]} - {row[2]}")

if __name__ == "__main__":
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    today_tab_name = now.strftime("%d-%m-%Y")
    today_date_str = now.strftime("%d %B, %Y")

    print(f"Starting Uttarakhand Daily News Processing for Date: {today_tab_name}...")
    news_items = fetch_news_from_rss()
    relevant_entries = []
    
    for item in news_items:
        parsed = extract_structured_data(item, today_date_str)
        if parsed and parsed.get("is_relevant"):
            relevant_entries.append(parsed)
        
        # Rate limit exceed na ho iske liye 10 second ka delay
        time.sleep(10)
            
    append_to_sheet(relevant_entries, today_tab_name)
    print("Task Completed Successfully.")
