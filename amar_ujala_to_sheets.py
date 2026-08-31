import os
import json
import time
import requests
import xml.etree.ElementTree as ET
from groq import Groq
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz

# Environment Variables setup
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
SPREADSHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "1zxVYJ0Xj7MzwEQzXST2oUBHDc42NDm4KrncwhaUlfRk")
CREDENTIALS_FILE = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "service-account.json")
RSS_URL = os.environ.get("RSS_URL", "https://www.amarujala.com/rss/uttarakhand.xml")
TIMEZONE = os.environ.get("TIMEZONE", "Asia/Kolkata")

client_groq = Groq(api_key=GROQ_API_KEY)

# Uttarakhand 70 Vidhansabha Hindi + English MLA Mapping
MLA_MAPPING = {
    # Dehradun District
    "chakrata": "प्रीतम सिंह (INC)", "चकराता": "प्रीतम सिंह (INC)",
    "vikasnagar": "मुन्ना सिंह चौहान (BJP)", "विकासनगर": "मुन्ना सिंह चौहान (BJP)",
    "sahaspur": "सहदेव सिंह पुंडीर (BJP)", "सहसपुर": "सहदेव सिंह पुंडीर (BJP)",
    "dharampur": "विनोद चमोली (BJP)", "धर्मपुर": "विनोद चमोली (BJP)",
    "raipur": "उमेश शर्मा काउ (BJP)", "रायपुर": "उमेश शर्मा काउ (BJP)",
    "rajpur road": "खजान दास (BJP)", "राजपुर रोड": "खजान दास (BJP)",
    "dehradun cantt": "सविता कपूर (BJP)", "कैंट": "सविता कपूर (BJP)", "देहरादून कैंट": "सविता कपूर (BJP)",
    "mussoorie": "गणेश जोशी (BJP)", "मसूरी": "गणेश जोशी (BJP)",
    "doiwala": "बृज भूषण गैरोला (BJP)", "डोईवाला": "बृज भूषण गैरोला (BJP)",
    "rishikesh": "प्रेमचंद अग्रवाल (BJP)", "ऋषिकेश": "प्रेमचंद अग्रवाल (BJP)",

    # Haridwar District
    "haridwar": "मदन कौशिक (BJP)", "हरिद्वार": "मदन कौशिक (BJP)",
    "bhel ranipur": "आदेश चौहान (BJP)", "रानीपुर": "आदेश चौहान (BJP)",
    "jwalapur": "इंजीनियर रवि बहादुर (INC)", "ज्वालापुर": "इंजीनियर रवि बहादुर (INC)",
    "bhagwanpur": "ममता राकेश (INC)", "भगवानपुर": "ममता राकेश (INC)",
    "jhabrera": "वीरेंद्र कुमार (INC)", "झबरेड़ा": "वीरेंद्र कुमार (INC)",
    "piran kaliyar": "फुरकान अहमद (INC)", "पिरान कलियर": "फुरकान अहमद (INC)", "कलियर": "फुरकान अहमद (INC)",
    "roorkee": "प्रदीप बत्रा (BJP)", "रुड़की": "प्रदीप बत्रा (BJP)",
    "khanpur": "उमेश कुमार (Independent)", "खानपुर": "उमेश कुमार (Independent)",
    "manglaur": "काज़ी मोहम्मद निज़ामुद्दीन (INC)", "मंगलौर": "काज़ी मोहम्मद निज़ामुद्दीन (INC)",
    "laksar": "मोहम्मद शहजाद (BSP)", "लक्सर": "मोहम्मद शहजाद (BSP)",
    "haridwar rural": "अनुपमा रावत (INC)", "हरिद्वार ग्रामीण": "अनुपमा रावत (INC)",

    # Uttarkashi District
    "purola": "दुर्गेश्वर लाल (BJP)", "पुरोला": "दुर्गेश्वर लाल (BJP)",
    "yamunotri": "संजय डोभाल (Independent)", "यमुनोत्री": "संजय डोभाल (Independent)",
    "gangotri": "सुरेश सिंह चौहान (BJP)", "गंगोत्री": "सुरेश सिंह चौहान (BJP)", "उत्तरकाशी": "सुरेश सिंह चौहान (BJP)",

    # Chamoli District
    "badrinath": "लखपत सिंह बुटोला (INC)", "बद्रीनाथ": "लखपत सिंह बुटोला (INC)",
    "thali": "सतपाल महाराज (BJP)", "थराली": "भूपाल राम टम्टा (BJP)",
    "karnaprayag": "अनिल नौटियाल (BJP)", "कर्णप्रयाग": "अनिल नौटियाल (BJP)",

    # Rudraprayag District
    "kedarnath": "आशा नौटियाल (BJP)", "केदारनाथ": "आशा नौटियाल (BJP)",
    "rudraprayag": "भरत सिंह चौधरी (BJP)", "रुद्रप्रयाग": "भरत सिंह चौधरी (BJP)",

    # Tehri Garhwal District
    "ghansali": "शक्ति लाल शाह (BJP)", "घनसाली": "शक्ति लाल शाह (BJP)",
    "devprayag": "विनोद कंडारी (BJP)", "देवप्रयाग": "विनोद कंडारी (BJP)",
    "narendranagar": "सुबोध उनियाल (BJP)", "नरेन्द्रनगर": "सुबोध उनियाल (BJP)",
    "pratapnagar": "विक्रम सिंह नेगी (INC)", "प्रतापनगर": "विक्रम सिंह नेगी (INC)",
    "tehri": "किशोर उपाध्याय (BJP)", "टिहरी": "किशोर उपाध्याय (BJP)",
    "dhanaulti": "प्रीतम सिंह पंवार (BJP)", "धनौल्टी": "प्रीतम सिंह पंवार (BJP)",

    # Pauri Garhwal District
    "yamkeshwar": "रेणु बिष्ट (BJP)", "यमकेश्वर": "रेणु बिष्ट (BJP)",
    "pauri": "राजकुमार पोरी (BJP)", "पौड़ी": "राजकुमार पोरी (BJP)",
    "srinagar": "डॉ. धन सिंह रावत (BJP)", "श्रीनगर": "डॉ. धन सिंह रावत (BJP)",
    "chaubattakhal": "सतपाल महाराज (BJP)", "चौबट्टाखाल": "सतपाल महाराज (BJP)",
    "lansdowne": "दलीप सिंह रावत (BJP)", "लेंसडाउन": "दलीप सिंह रावत (BJP)",
    "kotdwar": "ऋतु खंडूरी भूषण (BJP)", "कोटद्वार": "ऋतु खंडूरी भूषण (BJP)",

    # Pithoragarh & Bageshwar District
    "dharchula": "हरीश सिंह धामी (INC)", "धारचूला": "हरीश सिंह धामी (INC)",
    "didihat": "विशन सिंह चुफाल (BJP)", "डीडीहाट": "विशन सिंह चुफाल (BJP)",
    "pithoragarh": "मयूख महर (INC)", "पिथौरागढ़": "मयूख महर (INC)",
    "gangolihat": "फकीर राम टम्टा (BJP)", "गंगोलीहाट": "फकीर राम टम्टा (BJP)",
    "kapkot": "सुरेश गड़िया (BJP)", "कपकोट": "सुरेश गड़िया (BJP)",
    "bageshwar": "पार्वती दास (BJP)", "बागेश्वर": "पार्वती दास (BJP)",

    # Almora & Champawat District
    "dwarahat": "मदन सिंह बिष्ट (INC)", "द्वाराहाट": "मदन सिंह बिष्ट (INC)",
    "salt": "महेश जीना (BJP)", "सल्ट": "महेश जीना (BJP)",
    "ranikhet": "प्रमोद नैनवाल (BJP)", "रानीखेत": "प्रमोद नैनवाल (BJP)",
    "someshwar": "रेखा आर्य (BJP)", "सोमेश्वर": "रेखा आर्य (BJP)",
    "almora": "मनोज तिवारी (INC)", "अल्मोड़ा": "मनोज तिवारी (INC)",
    "jageshwar": "मोहन सिंह मेहरा (BJP)", "जागेश्वर": "मोहन सिंह मेहरा (BJP)",
    "lohaghat": "खुशाल सिंह अधिकारी (INC)", "लोहाघाट": "खुशाल सिंह अधिकारी (INC)",
    "champawat": "पुष्कर सिंह धामी (CM - BJP)", "चंपावत": "पुष्कर सिंह धामी (CM - BJP)",

    # Nainital & Udham Singh Nagar District
    "lalkuan": "डॉ. मोहन सिंह बिष्ट (BJP)", "लालकुआं": "डॉ. मोहन सिंह बिष्ट (BJP)",
    "bhimtal": "राम सिंह कैड़ा (BJP)", "भीमताल": "राम सिंह कैड़ा (BJP)",
    "nainital": "सरिता आर्य (BJP)", "नैनीताल": "सरिता आर्य (BJP)",
    "haldwani": "सुमित हृदयेश (INC)", "हल्द्वानी": "सुमित हृदयेश (INC)",
    "kaladhungi": "बंशीधर भगत (BJP)", "कालाढूंगी": "बंशीधर भगत (BJP)",
    "ramnagar": "दीवान सिंह बिष्ट (BJP)", "रामनगर": "दीवान सिंह बिष्ट (BJP)",
    "jaspur": "आदेश सिंह चौहान (INC)", "जसपुर": "आदेश सिंह चौहान (INC)",
    "kashipur": "त्रिलोक सिंह चीमा (BJP)", "काशीपुर": "त्रिलोक सिंह चीमा (BJP)",
    "bazpur": "यशपाल आर्य (INC)", "बाजपुर": "यशपाल आर्य (INC)",
    "gadarpur": "अरविंद पांडे (BJP)", "गदरपुर": "अरविंद पांडे (BJP)",
    "rudrapur": "शिव अरोड़ा (BJP)", "रुद्रपुर": "शिव अरोड़ा (BJP)",
    "kichha": "तिलक राज बेहड़ (INC)", "किच्छा": "तिलक राज बेहड़ (INC)",
    "sitarganj": "सौरभ बहुगुणा (BJP)", "सितारगंज": "सौरभ बहुगुणा (BJP)",
    "nanakmatta": "गोपाल सिंह राणा (INC)", "नानकमत्ता": "गोपाल सिंह राणा (INC)",
    "khatima": "भुवन चंद्र कापड़ी (INC)", "खटीमा": "भुवन चंद्र कापड़ी (INC)"
}

def get_mla_by_constituency(constituency_name):
    if not constituency_name:
        return ""
    name_clean = constituency_name.strip().lower()
    
    # Direct match check
    for key, val in MLA_MAPPING.items():
        if key in name_clean or name_clean in key:
            return val
            
    return ""

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
    return articles[:20]

def extract_structured_data(news_item, today_date_str):
    prompt = f"""
    Aapko Uttarakhand News parse karni hai aur Ground Impact Assessment Sheet ke exact format me extract karna hai.
    
    News Title: {news_item['title']}
    News Link: {news_item['link']}
    News Summary: {news_item['description']}

    Rules:
    1. Check karo kya isme Uttarakhand Government, Administration, PWD, Health, Jal Sansthan, Drainage, School, Transport, ya public issue me govt action required hai?
    2. Agar Govt/Public issue nahi hai, to JSON me "is_relevant": false return karo.
    3. Vidhansabha identify karo (e.g., "ऋषिकेश", "रानीखेत", "डोईवाला", "उत्तरकाशी", "रुद्रपुर", "यमुनोत्री"). Agar pure state ki news hai to "Uttarakhand (State Level)" likho.
    4. Location: Exact location (Gaon, Hospital, Tehsil ya District) likho.

    Strictly return JSON only:
    {{
      "is_relevant": true,
      "Vidhansabha": "...",
      "Location": "...",
      "Issue": "...",
      "Link": "{news_item['link']}",
      "POC": "अमर उजाला",
      "Date": "{today_date_str}"
    }}
    """
    
    try:
        response = client_groq.chat.completions.create(
            messages=[
                {"role": "user", "content": prompt}
            ],
            model="openai/gpt-oss-20b",
            response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content)
        
        if data.get("is_relevant"):
            vidhansabha = data.get("Vidhansabha", "")
            # Auto-fetch exact MLA from dictionary
            mapped_mla = get_mla_by_constituency(vidhansabha)
            if not mapped_mla:
                if "state" in vidhansabha.lower() or "uttarakhand" in vidhansabha.lower():
                    mapped_mla = "पुष्कर सिंह धामी (CM - BJP)"
                else:
                    mapped_mla = "N/A"
            data["Vidhayak"] = mapped_mla

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
        print(f"Successfully appended row to tab '{today_tab_name}': {row[0]} - {row[1]}")

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
        time.sleep(1)
            
    append_to_sheet(relevant_entries, today_tab_name)
    print("Task Completed Successfully.")
