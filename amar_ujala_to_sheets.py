import os
import json
import time
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, date, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup
from groq import Groq
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pytz

# ----------------------------- Configuration -------------------------------
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
SPREADSHEET_ID = os.environ.get(
    "GOOGLE_SHEET_ID", "1zxVYJ0Xj7MzwEQzXST2oUBHDc42NDm4KrncwhaUlfRk"
)
CREDENTIALS_FILE = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "service-account.json")
RSS_URL = os.environ.get("RSS_URL", "https://www.amarujala.com/rss/uttarakhand.xml")
PORTAL_URLS = [u.strip() for u in os.environ.get("PORTAL_URLS", "https://www.amarujala.com/uttarakhand").split(",") if u.strip()]
TIMEZONE = os.environ.get("TIMEZONE", "Asia/Kolkata")
MAX_ARTICLES = int(os.environ.get("MAX_ARTICLES", "100"))
TARGET_NEWS = int(os.environ.get("TARGET_NEWS", "10"))
MAX_ARTICLE_CHARS = int(os.environ.get("MAX_ARTICLE_CHARS", "18000"))
LOOKBACK_HOURS = float(os.environ.get("LOOKBACK_HOURS", "30"))

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY environment variable is missing")

client_groq = Groq(api_key=GROQ_API_KEY)

# Current 70-seat order used by the Uttarakhand CM Office legislator list.
# The model is never allowed to invent a constituency or MLA. It selects only
# one of these canonical keys; the script supplies the verified MLA and number.
CONSTITUENCY = {
    "purola": (1, "पुरोला", "दुर्गेश्वर लाल (BJP)"),
    "yamunotri": (2, "यमुनोत्री", "संजय डोभाल (निर्दलीय)"),
    "gangotri": (3, "गंगोत्री", "सुरेश चौहान (BJP)"),
    "badrinath": (4, "बद्रीनाथ", "लखपत सिंह बुटोला (कांग्रेस)"),
    "tharali": (5, "थराली", "भोपाल राम टम्टा (BJP)"),
    "karnaprayag": (6, "कर्णप्रयाग", "अनिल नौटियाल (BJP)"),
    "kedarnath": (7, "केदारनाथ", "आशा नौटियाल (BJP)"),
    "rudraprayag": (8, "रुद्रप्रयाग", "भरत सिंह चौधरी (BJP)"),
    "ghansali": (9, "घनसाली", "शक्तिलाल शाह (BJP)"),
    "devprayag": (10, "देवप्रयाग", "विनोद कंडारी (BJP)"),
    "narendranagar": (11, "नरेन्द्रनगर", "सुबोध उनियाल (BJP)"),
    "pratapnagar": (12, "प्रतापनगर", "विक्रम सिंह नेगी (कांग्रेस)"),
    "tehri": (13, "टिहरी", "किशोर उपाध्याय (BJP)"),
    "dhanaulti": (14, "धनौल्टी", "प्रीतम सिंह पंवार (BJP)"),
    "chakrata": (15, "चकराता", "प्रीतम सिंह (कांग्रेस)"),
    "vikasnagar": (16, "विकासनगर", "मुन्ना सिंह चौहान (BJP)"),
    "sahaspur": (17, "सहसपुर", "सहदेव सिंह पुंडीर (BJP)"),
    "dharampur": (18, "धर्मपुर", "विनोद चमोली (BJP)"),
    "raipur": (19, "रायपुर", "उमेश शर्मा काऊ (BJP)"),
    "rajpur_road": (20, "राजपुर रोड(SC)", "खजान दास (BJP)"),
    "dehradun_cantt": (21, "देहरादून कैंट", "सविता कपूर (BJP)"),
    "mussoorie": (22, "मसूरी", "गणेश जोशी (BJP)"),
    "doiwala": (23, "डोईवाला", "बृज भूषण गैरोला (BJP)"),
    "rishikesh": (24, "ऋषिकेश", "प्रेमचंद अग्रवाल (BJP)"),
    "haridwar": (25, "हरिद्वार", "मदन कौशिक (BJP)"),
    "bhel_ranipur": (26, "बीएचईएल रानीपुर", "आदेश चौहान (BJP)"),
    "jwalapur": (27, "ज्वालापुर", "इंजीनियर रवि बहादुर (कांग्रेस)"),
    "bhagwanpur": (28, "भगवानपुर", "ममता राकेश (कांग्रेस)"),
    "jhabrera": (29, "झबरेड़ा", "वीरेंद्र कुमार (कांग्रेस)"),
    "piran_kaliyar": (30, "पिरान कलियर", "फुरकान अहमद (कांग्रेस)"),
    "roorkee": (31, "रुड़की", "प्रदीप बत्रा (BJP)"),
    "khanpur": (32, "खानपुर", "उमेश कुमार (निर्दलीय)"),
    "manglaur": (33, "मंगलौर", "काजी मोहम्मद निजामुद्दीन (कांग्रेस)"),
    "laksar": (34, "लक्सर", "मोहम्मद शहजाद (BSP)"),
    "haridwar_rural": (35, "हरिद्वार ग्रामीण", "अनुपमा रावत (कांग्रेस)"),
    "yamkeshwar": (36, "यमकेश्वर", "रेणु बिष्ट (BJP)"),
    "pauri": (37, "पौड़ी", "राज कुमार पोरी (BJP)"),
    "srinagar": (38, "श्रीनगर", "डॉ. धन सिंह रावत (BJP)"),
    "chaubattakhal": (39, "चौबट्टाखाल", "सतपाल महाराज (BJP)"),
    "lansdowne": (40, "लैंसडाउन", "दिलीप सिंह रावत (BJP)"),
    "kotdwar": (41, "कोटद्वार", "ऋतु खंडूरी भूषण (BJP)"),
    "dharchula": (42, "धारचूला", "हरीश सिंह धामी (कांग्रेस)"),
    "didihat": (43, "डीडीहाट", "बिशन सिंह चुफाल (BJP)"),
    "pithoragarh": (44, "पिथौरागढ़", "मयूख सिंह महर (कांग्रेस)"),
    "gangolihat": (45, "गंगोलीहाट", "फकीर राम टम्टा (BJP)"),
    "kapkote": (46, "कपकोट", "सुरेश गड़िया (BJP)"),
    "bageshwar": (47, "बागेश्वर", "पार्वती दास (BJP)"),
    "dwarahat": (48, "द्वाराहाट", "मदन सिंह बिष्ट (कांग्रेस)"),
    "salt": (49, "सल्ट", "महेश जीना (BJP)"),
    "ranikhet": (50, "रानीखेत", "प्रमोद नैनवाल (BJP)"),
    "someshwar": (51, "सोमेश्वर", "रेखा आर्य (BJP)"),
    "almora": (52, "अल्मोड़ा", "मनोज तिवारी (कांग्रेस)"),
    "jageshwar": (53, "जागेश्वर", "मोहन सिंह मेहरा (BJP)"),
    "lohaghat": (54, "लोहाघाट", "खुशाल सिंह अधिकारी (कांग्रेस)"),
    "champawat": (55, "चंपावत", "पुष्कर सिंह धामी (मुख्यमंत्री, BJP)"),
    "lalkuan": (56, "लालकुआं", "डॉ. मोहन सिंह बिष्ट (BJP)"),
    "bhimtal": (57, "भीमताल", "राम सिंह कैड़ा (BJP)"),
    "nainital": (58, "नैनीताल", "सरिता आर्या (BJP)"),
    "haldwani": (59, "हल्द्वानी", "सुमित हृदयेश (कांग्रेस)"),
    "kaladhungi": (60, "कालाढूंगी", "बंशीधर भगत (BJP)"),
    "ramnagar": (61, "रामनगर", "दीवान सिंह बिष्ट (BJP)"),
    "jaspur": (62, "जसपुर", "आदेश सिंह चौहान (कांग्रेस)"),
    "kashipur": (63, "काशीपुर", "त्रिलोक सिंह चीमा (BJP)"),
    "bazpur": (64, "बाजपुर", "यशपाल आर्य (कांग्रेस)"),
    "gadarpur": (65, "गदरपुर", "अरविंद पांडे (BJP)"),
    "rudrapur": (66, "रुद्रपुर", "शिव अरोड़ा (BJP)"),
    "kichha": (67, "किच्छा", "तिलक राज बेहड़ (कांग्रेस)"),
    "sitarganj": (68, "सितारगंज", "सौरभ बहुगुणा (BJP)"),
    "nanakmatta": (69, "नानकमत्ता", "गोपाल सिंह राणा (कांग्रेस)"),
    "khatima": (70, "खटीमा", "भुवन चंद्र कापड़ी (कांग्रेस)"),
}

# Hindi/English aliases accepted from the model, normalized before lookup.
ALIASES = {
    "thali": "tharali", "थराली": "tharali", "karnprayag": "karnaprayag",
    "rajpur road": "rajpur_road", "rajpur_road": "rajpur_road",
    "dehradun cantt": "dehradun_cantt", "dehradun cantonment": "dehradun_cantt",
    "bhel ranipur": "bhel_ranipur", "piran kaliyar": "piran_kaliyar",
    "haridwar rural": "haridwar_rural", "yamkeshwar": "yamkeshwar",
}
for key, (_, hindi_name, _) in list(CONSTITUENCY.items()):
    ALIASES[hindi_name.lower()] = key


def normalize_constituency(value):
    if not value:
        return ""
    text = re.sub(r"\s+", " ", str(value).strip().lower())
    text = re.sub(r"\s*\([^)]*\)", "", text).strip()
    return ALIASES.get(text, text if text in CONSTITUENCY else "")


def format_constituency(key):
    # Keep the Sheet visually clean: only the constituency name in column A.
    return CONSTITUENCY[key][1]


def parse_feed_datetime(value, tz):
    """Parse RSS pubDate into the configured local timezone."""
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = tz.localize(parsed)
        return parsed.astimezone(tz)
    except (TypeError, ValueError, OverflowError):
        return None


def fetch_news_from_rss(target_date, tz):
    response = requests.get(RSS_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    articles = []
    cutoff = datetime.now(tz) - timedelta(hours=LOOKBACK_HOURS)
    for item in root.findall("./channel/item")[:MAX_ARTICLES]:
        title = item.findtext("title", default="").strip()
        link = item.findtext("link", default="").strip()
        description = item.findtext("description", default="").strip()
        published_raw = item.findtext("pubDate", default="").strip()
        published_at = parse_feed_datetime(published_raw, tz)

        # Keep recent stories within the configured window. The old exact-date
        # check could exclude valid stories published shortly before the run.
        if not published_at or published_at < cutoff:
            continue
        if title and link and link.startswith("http"):
            articles.append({
                "title": title,
                "link": link,
                "description": description,
                "published_at": published_at,
            })
    return articles


def fetch_news_from_portal(tz):
    """Collect Uttarakhand article links visible on the configured portal pages."""
    articles = []
    seen = set()
    for page_url in PORTAL_URLS:
        try:
            response = requests.get(
                page_url,
                headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "hi-IN,hi;q=0.9"},
                timeout=30,
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            for anchor in soup.select("a[href]"):
                href = urljoin(page_url, anchor.get("href", "").strip())
                parsed = urlparse(href)
                title = anchor.get_text(" ", strip=True)
                if (
                    parsed.scheme not in {"http", "https"}
                    or "amarujala.com" not in parsed.netloc
                    or "/uttarakhand/" not in parsed.path
                    or not title
                    or len(title) < 20
                    or href in seen
                ):
                    continue
                seen.add(href)
                articles.append({
                    "title": title,
                    "link": href,
                    "description": "",
                    "published_at": datetime.now(tz),
                })
        except requests.RequestException as exc:
            print(f"Portal scan failed for {page_url}: {exc}")
    return articles


def merge_articles(*article_lists):
    merged = []
    seen = set()
    for article_list in article_lists:
        for article in article_list:
            link = article.get("link", "").strip()
            if link and link not in seen:
                seen.add(link)
                merged.append(article)
    return merged


def fetch_article_text(url):
    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "hi-IN,hi;q=0.9"},
        timeout=30,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "header", "form"]):
        tag.decompose()
    candidates = soup.select("article, [itemprop='articleBody'], .article-body, .articleBody, main")
    if candidates:
        text = max((node.get_text(" ", strip=True) for node in candidates), key=len, default="")
    else:
        text = soup.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text)[:MAX_ARTICLE_CHARS]


PROMPT = """
आप उत्तराखंड सरकार के लिए अत्यंत सख्त Ground Impact Assessment analyst हैं। आपको Amar Ujala की खबर का शीर्षक, RSS विवरण और पूरा लेख दिया गया है। केवल लेख में लिखे हुए प्रमाण के आधार पर JSON बनाइए। अनुमान, सामान्य ज्ञान या अपनी ओर से कोई नाम/स्थान/विधानसभा न जोड़ें।

सबसे महत्वपूर्ण नियम:
1. केवल तब is_relevant=true दें जब खबर में किसी स्थानीय जनता की वास्तविक समस्या और उसके समाधान के लिए सरकार/जिला प्रशासन/PWD/पुलिस/स्वास्थ्य/शिक्षा/बिजली/जल/नगर निकाय/अन्य सार्वजनिक प्राधिकरण की ठोस कार्रवाई आवश्यक हो। दुर्घटना या अपराध की सामान्य खबर, राजनीतिक बयान, समारोह, खेल, मौसम का सामान्य पूर्वानुमान और बिना किसी स्पष्ट प्रशासनिक समस्या वाली खबर false होगी।
2. खबर अगर पूरे राज्य, कई जिलों या कई अलग-अलग विधानसभा क्षेत्रों की हो और लेख किसी एक विधानसभा को स्पष्ट रूप से केंद्रित न करता हो, तो is_relevant=false करें। कभी भी “उत्तराखंड”, “राज्य स्तर”, “देहरादून जिला”, “मुख्यमंत्री की विधानसभा” या कोई अनुमानित विधानसभा न भरें।
3. Vidhansabha_key केवल नीचे दिए गए 70 canonical keys में से एक हो सकता है। लेख में स्पष्ट स्थान/गांव/तहसील/नगर/मार्ग जिस विधानसभा में आता है, वही key चुनें। यदि mapping निश्चित नहीं है तो false करें। Sheet के Vidhansabha cell में बाद में केवल विधानसभा का साफ हिंदी नाम आएगा; संख्या, जिला, “(State Level)” या कोई अतिरिक्त text नहीं आएगा।
4. Vidhansabha और Vidhayak model से invent नहीं करने हैं; code बाद में verified mapping लगाएगा। JSON में Vidhansabha_key ही दें।
5. Location में केवल खबर में स्पष्ट रूप से दिया गया सबसे सटीक स्थानीय स्थान लिखें। पहले छोटे landmark/गांव/बाजार/चौक/पुल/सड़क/अस्पताल का नाम दें और जरूरत हो तो उसके बाद क्षेत्र/तहसील लिखें। उदाहरण: “जखंड गांव, अमोली, नाबड़ी, ततिया और मंडल क्षेत्र”, “लाइब्रेरी चौक, माल रोड, मसूरी” या “काठगोदाम मार्ग, चोपड़ा, नैनीताल, दो गांव के पास”। केवल जिला, राज्य, “देहरादून जिला”, “उत्तरकाशी” या “स्थानीय क्षेत्र” न लिखें। एक ही स्थान को दोहराएँ नहीं, अनावश्यक प्रशासनिक विवरण न जोड़ें, और article में न लिखा हुआ landmark अनुमान से न बनाएं।
6. Issue summary नहीं होगा। शुद्ध और स्वाभाविक हिंदी के पूरे विवरण में लिखें: क्या हुआ, जनता को किस तरह की परेशानी/जोखिम है, लोगों की मांग क्या है, और प्रशासन/विभाग ने क्या किया या क्या stand बताया है। यदि मांग या प्रशासनिक stand लेख में नहीं है तो साफ लिखें “खबर में मांग/प्रशासनिक पक्ष स्पष्ट नहीं बताया गया है”; उसे गढ़ें नहीं।
7. Issue, Location और POC हिंदी में लिखें। केवल unavoidable proper noun, संक्षिप्त सरकारी नाम और संख्याएँ आदि अंग्रेज़ी में हो सकते हैं।
"""




# Expected JSON returned by Groq. Keep the output contract explicit.
PROMPT += """

केवल इस JSON object में उत्तर दें:
{
  "is_relevant": true,
  "Vidhansabha_key": "canonical_key_or_empty",
  "Location": "हिंदी में सटीक स्थान",
  "Issue": "हिंदी में पूरा विवरण",
  "POC": "हिंदी में संबंधित विभाग/अधिकारी/व्यक्ति, या स्पष्ट रूप से उपलब्ध नहीं",
  "confidence": 0.0
}
यदि खबर relevant नहीं है तो is_relevant=false और बाकी fields खाली string रखें। Markdown या अतिरिक्त text बिल्कुल न दें।
"""

SHEET_NAME = os.environ.get("SHEET_NAME", "Sheet1")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
SHEET_HEADERS = ["Vidhansabha", "Vidhayak", "Location", "Issue", "Link"]


def get_worksheet(tab_name):
    if not os.path.exists(CREDENTIALS_FILE):
        raise FileNotFoundError(f"Google credentials file not found: {CREDENTIALS_FILE}")

    scopes = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets",
    ]
    credentials = ServiceAccountCredentials.from_json_keyfile_name(
        CREDENTIALS_FILE, scopes
    )
    sheets = gspread.authorize(credentials)
    spreadsheet = sheets.open_by_key(SPREADSHEET_ID)

    try:
        worksheet = spreadsheet.worksheet(tab_name)
        print(f"Using existing date tab: {tab_name}")
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=tab_name, rows=1000, cols=len(SHEET_HEADERS))
        print(f"Created new date tab: {tab_name}")

    current_headers = worksheet.row_values(1)
    if current_headers[: len(SHEET_HEADERS)] != SHEET_HEADERS:
        worksheet.update("A1:E1", [SHEET_HEADERS])
        print(f"Initialized headers in worksheet: {tab_name}")
    return worksheet


def analyze_article(article, article_text):
    prompt = (
        PROMPT
        + "\n\nशीर्षक:\n"
        + article["title"]
        + "\n\nRSS विवरण:\n"
        + article["description"]
        + "\n\nपूरा लेख:\n"
        + article_text
    )
    completion = client_groq.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        response_format={"type": "json_object"},
    )
    content = completion.choices[0].message.content or "{}"
    result = json.loads(content)
    if not isinstance(result, dict):
        raise ValueError("Groq response is not a JSON object")
    return result


def build_row(article, result, local_date):
    key = normalize_constituency(result.get("Vidhansabha_key", ""))
    if not result.get("is_relevant") or key not in CONSTITUENCY:
        return None

    _, hindi_constituency, vidhayak = CONSTITUENCY[key]
    return [
        hindi_constituency,
        vidhayak,
        str(result.get("Location", "")).strip(),
        str(result.get("Issue", "")).strip(),
        article["link"],
    ]


def append_new_rows(worksheet, rows):
    if not rows:
        print("No relevant articles found; no rows were written.")
        return 0

    existing_links = set()
    link_column = worksheet.col_values(5)[1:]
    existing_links.update(link.strip() for link in link_column if link.strip())
    new_rows = [row for row in rows if row[4] not in existing_links]

    if new_rows:
        worksheet.append_rows(new_rows, value_input_option="USER_ENTERED")
        print(f"Successfully appended {len(new_rows)} row(s) to {SHEET_NAME}.")
    else:
        print("All relevant articles already exist in the sheet.")
    return len(new_rows)


def main():
    tz = pytz.timezone(TIMEZONE)
    local_date = datetime.now(tz).date()
    print(f"Starting automation for {local_date} ({TIMEZONE})")

    rss_articles = fetch_news_from_rss(local_date, tz)
    portal_articles = fetch_news_from_portal(tz)
    articles = merge_articles(rss_articles, portal_articles)
    print(f"RSS articles: {len(rss_articles)}; portal links: {len(portal_articles)}; unique total: {len(articles)}")
    tab_name = local_date.isoformat()
    worksheet = get_worksheet(tab_name)
    rows = []

    for index, article in enumerate(articles[:MAX_ARTICLES], start=1):
        try:
            article_text = fetch_article_text(article["link"])
            if not article_text:
                print(f"[{index}] Skipped: empty article text")
                continue
            result = analyze_article(article, article_text)
            row = build_row(article, result, local_date)
            if row:
                rows.append(row)
                print(f"[{index}] Relevant: {article['title'][:90]}")
            else:
                print(f"[{index}] Not relevant or constituency not verified")
        except Exception as exc:
            print(f"[{index}] Failed: {article['link']} -> {exc}")

    written = append_new_rows(worksheet, rows)
    print(f"Done. Candidate rows: {len(rows)}; newly written rows: {written}")


if __name__ == "__main__":
    main()


def _test_row_shape():
    """Small local sanity check; it does not contact Google or Groq."""
    sample = {"is_relevant": True, "Vidhansabha_key": "mussoorie", "Location": "माल रोड", "Issue": "सड़क की समस्या", "POC": "नगर निकाय"}
    row = build_row({"link": "https://example.com"}, sample, date(2026, 1, 1))
    assert row[0] == "मसूरी" and row[4] == "https://example.com" and len(row) == 5


_test_row_shape()

def _check_runtime_config():
    print(f"Configured sheet: {SHEET_NAME}; model: {GROQ_MODEL}")


_check_runtime_config()


# Note: the test/config checks above run during startup, while main() is invoked
# only when this file is executed directly by GitHub Actions.
