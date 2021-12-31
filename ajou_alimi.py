from datetime import datetime, date, timedelta
import schedule
import requests
from bs4 import BeautifulSoup as BS
import time
from pandas import Series, DataFrame
import numpy as np
import pandas as pd
import os

# 'InsecureRequestWarning' 에러 안뜨게 하기
requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)
# 'Chained Assignement' 경고 무시하기
pd.set_option('mode.chained_assignment',  None)

# 슬랙 토큰
slack_Tocken = ""

# 슬랙 메시지 전송 함수
def send_slack_message(token, channel, text):
    response = requests.post("https://slack.com/api/chat.postMessage",
        headers={"Authorization": "Bearer "+token},
        data={"channel": channel,"text": text}
    )

# 오늘, 어제 날짜 가져오기
def get_date():
  global today
  global yesterday
  today = int(datetime.today().strftime("%Y%m%d")[2:])
  yesterday = date.today() - timedelta(1)
  yesterday = int(yesterday.strftime("%Y%m%d")[2:])

# 아주대 공지사항 페이지
LIMIT = 10
url = "https://www.ajou.ac.kr/kr/ajou/notice.do"
URL = f"https://www.ajou.ac.kr/kr/ajou/notice.do?mode=list&&articleLimit={LIMIT}"

get_date()
schedule.every().day.at("00:00").do(lambda: get_date())


# 리스트 생성
number_list_for_last_number = []
date_list_for_last_number = []
last_number = 0
# 마지막 번호 가져오기
for page in range(3):
    #print((f"Scrapping page {page+1}"))
    html = requests.get(f"{URL}&article.offset={page*LIMIT}", verify=False)
    soup = BS(html.content, "html.parser")
    # 공지 번호 가져오기
    box_number = soup.find_all(class_="b-num-box")
    for number in box_number:
        number = number.get_text().strip()
        number_list_for_last_number.append(number)
    # 공지 날짜 가져오기
    dates = soup.find_all(class_="b-date")
    for date in dates:
      date = int(date.get_text().strip().replace('.',''))
      date_list_for_last_number.append(date)
      
# 공지 데이터(딕셔너리) 만들기
data_for_last_number = {'number':  number_list_for_last_number,
           'date':  date_list_for_last_number}

# 데이터(딕셔너리)를 활용하여 데이터프레임 만들기
df_for_last_number= DataFrame(data_for_last_number)

# 넘버 컬럼에서 '공지'들어있는 행과 날짜 컬럼에 오늘 날짜인 행 뺴버기리
dropped_df_for_last_number = df_for_last_number[(df_for_last_number['number'].str.contains('공지') == False) & (df_for_last_number['date'] != today)]

# 마지막 숫자 구하기
last_number = int(dropped_df_for_last_number[:1]['number'])
#print(last_number)

while True:
  try:
    # 리스트 생성
    number_list = []
    date_list = []
    title_list = []
    link_list = []

    # 공지페이지에서 필요한 데이터 가져오기
    for page in range(3):
        print((f"Scrapping page {page+1}"))
        html = requests.get(f"{URL}&article.offset={page*LIMIT}", verify=False)
        soup = BS(html.content, "html.parser")
        # 공지 번호 가져오기
        box_number = soup.find_all(class_="b-num-box")
        for number in box_number:
            number = number.get_text().strip()
            number_list.append(number)
        # 공지 날짜 가져오기
        dates = soup.find_all(class_="b-date")
        for date in dates:
          date = int(date.get_text().strip().replace('.',''))
          date_list.append(date)
        # 공지 제목과 링크 가져오기
        title_and_link = soup.find_all(class_ ="b-title-box")
        for result in title_and_link:
            for title in result.find_all("a"):
                title = title.get("title").strip()[:-6]
                title_list.append(title)
            for link in result.find_all("a"):
                link =url + link.get("href").strip()
                link_list.append(link)

    # 공지 데이터(딕셔너리) 만들기
    notice_data = {'number':  number_list,
               'date':  date_list,
               'title' :  title_list,
               'link': link_list}

    # 데이터(딕셔너리)를 활용하여 데이터프레임 만들기
    df= DataFrame(notice_data)

    # number컬럼에 '공지' 빼고 나머지 남기기
    """이거 number컬럼에서 문자열 찾기로 바꿔야함!!!"""
    dropped_df = df[df['number'].str.contains('공지') == False]

    # 맨위에 있는 공지의 번호 가져오기
    top_number = int(dropped_df[:1]['number'])
    
    # 새로 업데이트 된 공지가 있는지 확인하기
    if top_number <= last_number:
      time.sleep(60*10) # 10분동안 멈춤
    else:
      # 전날 공지의 마지막 번호 가져오기
      yesterday_df = dropped_df[dropped_df['date'] == yesterday]
      if yesterday_df.empty: #.empty는 비어있는지 확인
        time.sleep(60*10) # 10분동안 멈춤
      else:
        # 마지막 번호 다음 번호부터 데이터 불러오기
        after_last_number_df = dropped_df[(dropped_df['number'].astype('int') > last_number) & (dropped_df['date'] == today)] # astype는 데이터프레임 타입 변경용
        
        # 새로운 마지막 번호 추출하기
        last_number = int(after_last_number_df[:1]['number'])
        #print(last_number)
        # 제목과 링크 합쳐서 새로은 열 만들기
        after_last_number_df['title&link'] = after_last_number_df[['title', 'link']].agg(' '.join, axis=1).copy()

        # 제목과 링크 합친 열 리스트로 추출
        titlelink_list = list(after_last_number_df['title&link'])
        #for a in titlelink_list:
        #  print(a)

        # slack으로 제목과 링크 리스트 보내기
        for a in range(len(titlelink_list)):           
          send_slack_message(slack_Tocken,"#ajou_univ_notice", titlelink_list[a])
        time.sleep(60*10) # 10분동안 멈춤
  except Exception as e:
        print(e)
        #send_slack_message(slack_Tocken,"#ajou_univ_notice", e)
        time.sleep(1)
