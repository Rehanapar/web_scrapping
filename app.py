from flask import Flask, render_template, request
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import requests
import re
import os
import csv
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

def extract_email_from_website(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", response.text)
            return emails[0] if emails else "N/A"
    except:
        pass
    return "N/A"

def extract_phone_from_text(text):
    phones = re.findall(r"\+?\d[\d\s\-().]{8,}\d", text)
    return phones[0] if phones else "N/A"

def extract_about_us_content(website_url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(website_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        for section in soup.find_all(["section", "div"]):
            text = section.get_text(separator=' ', strip=True)
            if "about us" in text.lower() or "about" in text.lower():
                return text[:500]
    except:
        pass
    return "N/A"

def fetch_website_data(entry):
    url = entry["website"]
    if url == "N/A":
        entry["email"] = "N/A"
        entry["services"] = "N/A"
        return entry
    entry["email"] = extract_email_from_website(url)
    entry["services"] = extract_about_us_content(url)
    return entry

def scrape_google_maps(category, pin_code, max_results=100):
    options = uc.ChromeOptions()
    options.headless = True
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--log-level=3")
    options.add_argument("user-agent=Mozilla/5.0")
    options.page_load_strategy = 'eager'
    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option("prefs", prefs)

    driver = uc.Chrome(options=options)

    wait = WebDriverWait(driver, 10)

    query = f"{category} near {pin_code}"
    maps_url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}/"
    driver.get(maps_url)
    wait.until(EC.presence_of_element_located((By.CLASS_NAME, "Nv2PK")))

    scrollable_div = wait.until(EC.presence_of_element_located((By.XPATH, '//div[@role="feed"]')))
    prev_count = 0

    start_time = datetime.now()
    timeout = 30  # seconds

    while (datetime.now() - start_time).total_seconds() < timeout:
        driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scrollable_div)
        time.sleep(0.5)
        listings = driver.find_elements(By.CLASS_NAME, "Nv2PK")
        if len(listings) > prev_count:
            prev_count = len(listings)
            start_time = datetime.now()
        if len(listings) >= max_results:
            break



    results = []
    listings = driver.find_elements(By.CLASS_NAME, "Nv2PK")[:max_results]

    for item in listings:
        try:
            name = item.find_element(By.CLASS_NAME, "qBF1Pd").text
        except:
            name = "N/A"

        try:
            address = item.find_elements(By.CLASS_NAME, "W4Efsd")[1].text
        except:
            address = "N/A"

      
        try:
            rating = item.find_element(By.CLASS_NAME, "MW4etd").text
        except:
            rating = "N/A"

        
        cid = "N/A"
        website_url = "N/A"

        try:
            for link in item.find_elements(By.TAG_NAME, "a"):
                href = link.get_attribute("href")
                if href:
                    # Case 1: Match normal decimal CID from URL
                    match = re.search(r"[?&]cid=(\d+)", href)
                    if match:
                        cid = match.group(1)

                    # Case 2: Match and convert hex CID like 0x3babefdbec337b57:0
                    elif "0x" in href:
                        hex_match = re.search(r"0x[0-9a-fA-F]+", href)
                        if hex_match:
                            hex_cid = hex_match.group(0)  # e.g. 0x3babefdbec337b57
                            try:
                                cid = str(int(hex_cid, 16))  # Convert to decimal
                            except ValueError:
                                cid = "Invalid Hex CID"

                    # Case 3: Extract external website
                    elif href.startswith("http") and "google.com/maps" not in href:
                        website_url = href
        except:
            cid = "N/A"
            website_url = "N/A"

        

        
        phone = extract_phone_from_text(item.text)

        results.append({
            "category": category,
            "pin_code": pin_code,
            "name": name,
            "address": address,
            
            "rating": rating,
            "email": "N/A",
            "phone": phone,
            "website": website_url,
            "gmap_link": maps_url,
            "services": "N/A",
            "cid": cid
        })


    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(fetch_website_data, results))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_category = re.sub(r'\W+', '_', category.lower())
    csv_file = f"static/{safe_category}_{timestamp}.csv"
    os.makedirs("static", exist_ok=True)

    with open(csv_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "category", "pin_code",
            "name", "address", "website", "rating", "email", "phone",
             "gmap_link", "services", "cid"
        ])
        writer.writeheader()
        writer.writerows(results)

    driver.quit()
    return results

@app.route("/", methods=["GET", "POST"])
def index():
    results = []
    if request.method == "POST":
        category = request.form.get("category")
        pin_code = request.form.get("pin")
        results = scrape_google_maps(category, pin_code)
    return render_template("index.html", results=results)

if __name__ == "__main__":
    app.run(debug=True)























































