import threading
from flask import Flask

# Flask 앱 생성
app = Flask(__name__)

@app.route("/")
def health_check():
    return "OK", 200

def run_flask():
    app.run(host="0.0.0.0", port=8000)

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import time
from googletrans import Translator  # type: ignore
from transformers import pipeline

# 디스코드 웹훅 URL
WEBHOOK_URL = "https://discord.com/api/webhooks/1364605565136801792/M97P9KFLlipdBVAg_A-6GyoxKlot84qQS9Iz9shRMapfA5haVdW59Q1ErGP2P6xtLcTg"

# 번역기 및 요약기 초기화
translator = Translator()
summarizer = pipeline("summarization", model="t5-base", tokenizer="t5-base")

# 중복 방지
sent_links = set()

# 뉴스 검색 함수 (국내 + 해외)
def search_news_multilang():
    urls = [
        "https://news.google.com/rss/search?q=대한민국+대사관+철수",
        "https://news.google.com/rss/search?q=embassy+evacuation+South+Korea"
    ]
    all_items = []
    for url in urls:
        response = requests.get(url)
        soup = BeautifulSoup(response.content, "xml")
        items = soup.find_all("item")
        all_items.extend(items)
    return all_items

# 날짜 및 국가 추출
def extract_country_and_time(text):
    countries = re.findall(r"[가-힣]{2,10} 대사관", text)
    dates = re.findall(r"\d{1,2}월 \d{1,2}일|\d{4}년 \d{1,2}월 \d{1,2}일", text)
    country = countries[0].replace(" 대사관", "") if countries else "알 수 없음"
    time_found = dates[0] if dates else datetime.now().strftime("%Y-%m-%d %H:%M")
    return country, time_found

# 요약 및 번역
def summarize_and_translate(text):
    summary = summarizer(text[:1000], max_length=80, min_length=20, do_sample=False)[0]['summary_text']
    translated = translator.translate(summary, src='en', dest='ko').text
    return translated

# 디스코드 알림
def send_discord_alert(title, link, country, time_str, content_kr):
    message = f"@everyone\n🚨 **{country} 대사관 철수 감지**\n📰보도내용: {content_kr}\n🕒보도시각: {time_str}\n🔗링크: {link}"
    requests.post(WEBHOOK_URL, json={"content": message})

# 로그 저장
def save_log(title, link, country, time_str, content_kr):
    log_path = r"C:\Users\ksyso\OneDrive\바탕 화면\대사 관철수 알리미 TEST ver\log.txt"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now()} | {country} | {time_str} | {title} | {content_kr} | {link}\n")

# 뉴스 확인 및 알림 전송
def run_once():
    global sent_links
    print("[INFO]", datetime.now(), "- 뉴스 확인 중...")
    news_items = search_news_multilang()

    for item in news_items[:5]:
        title = item.title.text
        link = item.link.text

        if link in sent_links:
            continue

        try:
            # 리디렉션된 실제 뉴스 페이지 가져오기
            article_url = requests.get(link, allow_redirects=True).url
            article_response = requests.get(article_url)
            article_text = article_response.text

            if "embassy" in title.lower():
                country_match = re.search(r"([A-Z][a-z]+) Embassy", title)
                country = country_match.group(1) if country_match else "해외국가"
                time_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                summary_ko = summarize_and_translate(article_text)
            else:
                country, time_str = extract_country_and_time(article_text)
                summary_ko = title

            # AI 필터링: "주한" 또는 "대한민국 대사관" 관련만 전송
            if any(keyword in summary_ko for keyword in ["주한", "대한민국 대사관", "한국 내 대사관", "서울 주재", "한국 대사관"]):
                send_discord_alert(title, link, country, time_str, summary_ko)
                save_log(title, link, country, time_str, summary_ko)
                sent_links.add(link)
            else:
                print("❌ 필터링됨: 관련 없는 기사")

        except Exception as e:
            print(f"❌ 처리 실패: {e}")
            
# 메인 루프
def main():
    while True:
        run_once()
        print("1시간 대기 중...\n")
        time.sleep(3600)

if __name__ == "__main__":
    # Flask 서버를 백그라운드 쓰레드로 실행
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # 메인 함수 실행
    main()

