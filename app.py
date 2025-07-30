from flask import Flask, render_template, request
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
# from selenium.common.exceptions import WebDriverException
from bs4 import BeautifulSoup
import time
import requests
import re
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
import os
import csv
from datetime import datetime


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

def scrape_google_maps(category, pin_code, max_results=100):
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument("--log-level=3")
    service = Service(log_path=os.devnull)
    driver = webdriver.Chrome(options=options, service=service)
   
    wait = WebDriverWait(driver, 10)
 
    query = f"{category} near {pin_code}"
    maps_url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}/"
    driver.get(maps_url)
    wait.until(EC.presence_of_element_located((By.CLASS_NAME, "Nv2PK")))

    scrollable_div = wait.until(EC.presence_of_element_located((By.XPATH, '//div[@role="feed"]')))
    prev_count = 0

    for _ in range(20):  # Scroll to load more results
        # scrollable_div = driver.find_element(By.CLASS_NAME, "m6QErb.DxyBCb.kA9KIf.dS8AEf.ecceSd")  # May change; inspect DOM
        driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scrollable_div)

        # driver.execute_script("window.scrollBy(0, 1000);")
        time.sleep(2)

        listings = driver.find_elements(By.CLASS_NAME, "Nv2PK")
        if len(listings) == prev_count:
            break
        prev_count = len(listings)

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

        try:
            website_url = "N/A"
            for link in item.find_elements(By.TAG_NAME, "a"):
                href = link.get_attribute("href")
                if href and href.startswith("http") and "google.com/maps" not in href:
                    website_url = href
                    break
        except:
            website_url = "N/A"

        product_service = extract_about_us_content(website_url) if website_url != "N/A" else "N/A"
        email = extract_email_from_website(website_url) if website_url != "N/A" else "N/A"
        phone = extract_phone_from_text(item.text)

        results.append({
            "name": name,
            "address": address,
            "rating": rating,
            "email": email,
            "phone": phone,
            "category": category,
            "website": website_url,
            "gmap_link": maps_url,
            "services": product_service
        })

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_category = re.sub(r'\W+', '_', category.lower())
    csv_file = f"static/{safe_category}_{timestamp}.csv"
    os.makedirs("static", exist_ok=True)
 
    with open(csv_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "name", "address", "rating", "email", "phone",
            "category", "website", "gmap_link", "services"
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
            


            

























































