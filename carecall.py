"""
CLOVA CareCall 자동 다운로드 매크로
- '대화 파일.wav' 자동 다운로드 (기본: 이전 7일)
- 의존성 설치: pip install -r requirements.txt
- 사용:
    carecall.exe (대화형 입력, Enter=기본값)
    carecall.exe --start 20260401 --end 20260407
"""

import time
import os
import sys
import zipfile
import re
import argparse
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

from config_loader import load_config, default_download_dir
from date_utils import resolve_date_range

# Naver 케어콜 URL 정적 변수
LOGIN_URL = "https://carecall.naverncp.com/login"
CALL_URL  = "https://carecall.naverncp.com/management/results/call"

# Config 변수 : main()에서 load_config로 초기화
EMAIL: str = ""
PASSWORD: str = ""
DOWNLOAD_DIR: str = ""


def parse_date_range() -> tuple[datetime, datetime]:
    """
    sys.argv에서 --start/--end 파싱 후 resolve_date_range 위임
    (python carecall.py 직접 실행 시 사용)
    """
    parser = argparse.ArgumentParser(
        description="CLOVA CareCall 자동 다운로드 매크로",
        add_help=True,
    )
    parser.add_argument("--start", help="시작일 (YYYYMMDD)")
    parser.add_argument("--end", help="종료일 (YYYYMMDD)")
    args = parser.parse_args()
    return resolve_date_range(args.start, args.end, default_days_back=7)


def build_driver() -> webdriver.Chrome:
    """Chrome 드라이버 초기화"""
    options = Options()
    download_dir_pref = DOWNLOAD_DIR

    prefs = {
        "download.default_directory": download_dir_pref,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": False,
        "safebrowsing.disable_download_protection": True,
        "profile.default_content_settings.popups": 0,
        "profile.content_settings.exceptions.automatic_downloads.*.setting": 1,
    }
    options.add_experimental_option("prefs", prefs)

    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # 백그라운드 실행을 원하면 아래 주석을 해제
    # options.add_argument("--headless=new")
    options.add_argument("--window-size=1400,900")
    options.add_argument("--disable-notifications")

    # Windows 환경 추가 옵션
    if sys.platform == "win32":
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-features=InsecureDownloadWarnings")
        options.add_argument("--safebrowsing-disable-download-protection")
        options.add_argument("--no-proxy-server")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--allow-running-insecure-content")
        options.add_argument("--disable-popup-blocking")

    service = Service(ChromeDriverManager().install())
    driver  = webdriver.Chrome(service=service, options=options)
    driver.implicitly_wait(10)

    # CDP(Chrome DevTools Protocol) 다운로드 경로 이중 확정
    driver.execute_cdp_cmd(
        "Page.setDownloadBehavior",
        {"behavior": "allow", "downloadPath": DOWNLOAD_DIR}
    )

    return driver


def login(driver: webdriver.Chrome) -> None:
    """로그인 처리"""
    print(f"[1/4] 로그인 중... ({LOGIN_URL})")
    driver.get(LOGIN_URL)
    wait = WebDriverWait(driver, 20)

    # 이메일 입력 (name="email", data-cy="login_input_id")
    email_input = wait.until(EC.presence_of_element_located(
        (By.CSS_SELECTOR, "input[name='email'][data-cy='login_input_id']")
    ))
    email_input.clear()
    email_input.send_keys(EMAIL)

    # 비밀번호 입력 (name="password", type="password")
    pw_input = wait.until(EC.presence_of_element_located(
        (By.CSS_SELECTOR, "input[type='password'][name='password']")
    ))
    pw_input.clear()
    pw_input.send_keys(PASSWORD)

    # 로그인 버튼 클릭 (data-cy="btn_login")
    login_btn = wait.until(EC.element_to_be_clickable(
        (By.CSS_SELECTOR, "button[data-cy='btn_login']")
    ))
    login_btn.click()

    # 로그인 완료 대기 (URL 변화)
    wait.until(EC.url_changes(LOGIN_URL))
    print("    ✓ 로그인 성공")


def navigate_and_set_date(driver: webdriver.Chrome,
                          start_date: datetime, end_date: datetime) -> None:
    """캠페인 현황 페이지로 이동 후 시작일~종료일 범위 선택 + 적용"""
    date_str = f"{start_date.strftime('%Y.%m.%d')} ~ {end_date.strftime('%Y.%m.%d')}"
    print(f"[2/4] 캠페인 현황 페이지 이동 및 날짜 설정 ({date_str})")
    driver.get(CALL_URL)
    wait = WebDriverWait(driver, 20)
    time.sleep(3)

    # ── 날짜 피커 버튼 클릭 (달력 팝업 열기) ──
    date_btn = wait.until(EC.element_to_be_clickable(
        (By.CSS_SELECTOR, "button[class*='date_picker_dropdown_btn_dropdown']")
    ))
    date_btn.click()
    time.sleep(1)

    # ── '직접 선택' 라디오 클릭 (달력에서 임의 기간 선택 활성화) ──
    custom_label = wait.until(EC.element_to_be_clickable(
        (By.XPATH, "//label[@for='custom' and contains(@class,'date_picker_dropdown_radio_label')]")
    ))
    custom_label.click()
    time.sleep(0.5)

    # ── 시작일: 해당 달로 이동(backward) 후 클릭 ──
    _navigate_calendar_to_month(driver, wait, start_date.year, start_date.month)
    _click_calendar_day(driver, wait, str(start_date.day))
    time.sleep(0.5)

    # ── 종료일: 다른 달이면 forward 이동 후 클릭 (rdr 범위 선택의 두 번째 클릭) ──
    if (end_date.year, end_date.month) != (start_date.year, start_date.month):
        _navigate_calendar_forward_to_month(driver, end_date.year, end_date.month)
    _click_calendar_day(driver, wait, str(end_date.day))
    time.sleep(0.5)

    # ── '적용' 버튼 클릭 ──
    apply_btn = wait.until(EC.element_to_be_clickable(
        (By.CSS_SELECTOR, "button[class*='date_picker_dropdown_btn_comp']")
    ))
    apply_btn.click()
    time.sleep(5)

    print(f"    ✓ 날짜 설정 완료 (대상: {date_str})")


def set_page_size_to_150(driver: webdriver.Chrome) -> None:
    """'50개씩 보기' 드롭다운을 열고 '150개씩 보기' 옵션 선택"""
    wait = WebDriverWait(driver, 20)

    # 개수 드롭다운 버튼 클릭 (현재 '50개씩 보기' 상태)
    count_btn = wait.until(EC.element_to_be_clickable(
        (By.XPATH,
         "//button[contains(@class,'common_btn') and contains(@class,'count')"
         "  and .//span[contains(@class,'txt_count')]]")
    ))
    count_btn.click()
    time.sleep(0.5)

    # '150개씩 보기' 옵션 클릭
    option_150 = wait.until(EC.element_to_be_clickable(
        (By.XPATH,
         "//button[contains(@class,'count_list_count_item')"
         "  and normalize-space(text())='150개씩 보기']")
    ))
    option_150.click()
    time.sleep(3)

    print("    ✓ 페이지 크기 150개로 변경 완료")


def _navigate_calendar_to_month(driver, wait, target_year: int, target_month: int) -> None:
    """
    달력 헤더(strong.date_picker_dropdown_cal_now)가
    'target_year년 target_month월'이 될 때까지 이전 달 버튼 클릭
    이전 달 버튼 class: date_picker_dropdown_m_prev__eG+Uh
    """
    for _ in range(24):
        try:
            # 헤더 텍스트 예: "2026년 3월"
            header = driver.find_element(
                By.CSS_SELECTOR, "strong[class*='date_picker_dropdown_cal_now']"
            ).text.strip()
        except Exception:
            time.sleep(0.5)
            continue

        if f"{target_year}년 {target_month}월" in header:
            break

        # 이전 달 버튼: class에 date_picker_dropdown_m_prev 포함, 텍스트 "이전"
        try:
            prev_btn = driver.find_element(
                By.CSS_SELECTOR, "button[class*='date_picker_dropdown_m_prev']"
            )
            prev_btn.click()
            time.sleep(0.4)
        except Exception:
            break


def _navigate_calendar_forward_to_month(driver, target_year: int, target_month: int) -> None:
    """
    달력을 앞으로(다음 달 방향) 이동
    시작일 클릭 후 종료일이 더 뒤 달에 있을 때 사용
    """
    for _ in range(24):
        try:
            header = driver.find_element(
                By.CSS_SELECTOR, "strong[class*='date_picker_dropdown_cal_now']"
            ).text.strip()
        except Exception:
            time.sleep(0.5)
            continue

        if f"{target_year}년 {target_month}월" in header:
            break

        try:
            next_btn = driver.find_element(
                By.CSS_SELECTOR, "button[class*='date_picker_dropdown_m_next']"
            )
            next_btn.click()
            time.sleep(0.4)
        except Exception:
            break


def _click_calendar_day(driver, wait, day_str: str) -> None:
    """
    rdr(React Date Range) 달력에서 날짜 셀 클릭
    달력 컨테이너: div.rdrMonths
    날짜 버튼:     button.rdrDay (비활성: rdrDayPassive / rdrDayDisabled 제외)
    날짜 숫자:     span.rdrDayNumber > span
    """
    # rdr 라이브러리 구조: button.rdrDay > span.rdrDayNumber > span(텍스트)
    day_btn = wait.until(EC.element_to_be_clickable(
        (By.XPATH,
         f"//button[contains(@class,'rdrDay')"
         f"  and not(contains(@class,'rdrDayPassive'))"
         f"  and not(contains(@class,'rdrDayDisabled'))]"
         f"  /span[contains(@class,'rdrDayNumber')]"
         f"  /span[normalize-space(text())='{day_str}']"
         f"  /.."   # span.rdrDayNumber 로 올라감
         f"  /.."   # button.rdrDay 로 올라감
        )
    ))
    day_btn.click()


def get_total_pages(driver: webdriver.Chrome) -> int:
    """현재 페이지네이션의 총 페이지 수 반환"""
    try:
        # data-cy="pagination_page_num_N" 패턴으로 페이지 버튼 수집
        page_btns = driver.find_elements(
            By.CSS_SELECTOR, "button[data-cy*='pagination_page_num']"
        )
        if not page_btns:
            return 1
        # data-cy="pagination_page_num_0" ~ pagination_page_num_N (0-based index)
        max_idx = max(
            int(btn.get_attribute("data-cy").replace("pagination_page_num_", ""))
            for btn in page_btns
        )
        return max_idx + 1  # 0-based → 1-based
    except Exception:
        return 1


def go_to_page(driver: webdriver.Chrome, wait: WebDriverWait, page_idx: int) -> None:
    """0-based 페이지 인덱스로 이동 (data-cy="pagination_page_num_N")"""
    btn = wait.until(EC.element_to_be_clickable(
        (By.CSS_SELECTOR, f"button[data-cy='pagination_page_num_{page_idx}']")
    ))
    btn.click()
    time.sleep(1.5)


def go_to_next_page_group(driver: webdriver.Chrome, wait: WebDriverWait) -> bool:
    """
    페이지 그룹 이동 (1~10 → 11~20 등)
    data-cy="pagination_pg_next" 버튼이 활성화 상태면 클릭 후 True 반환
    비활성(disabled)이면 False 반환
    """
    try:
        next_group_btn = driver.find_element(
            By.CSS_SELECTOR, "button[data-cy='pagination_pg_next']"
        )
        if next_group_btn.get_attribute("disabled"):
            return False
        next_group_btn.click()
        time.sleep(1.5)
        return True
    except Exception:
        return False


def select_all_and_download_page(driver: webdriver.Chrome, wait: WebDriverWait,
                                  page_num: int) -> None:
    """현재 페이지에서 전체선택 후 wav 다운로드"""

    # ── 전체 선택 ──
    select_all = wait.until(EC.element_to_be_clickable(
        (By.CSS_SELECTOR, "label[for='total-캠페인 현황 목록']")
    ))
    select_all.click()
    time.sleep(1)

    # 다운로드 버튼 활성화 대기
    time.sleep(1.5)

    def open_dropdown():
        btn = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "button[class*='result_dropdown_btn']")
        ))
        btn.click()
        time.sleep(1)

    # ── 대화 파일.wav ──
    open_dropdown()
    wait.until(EC.element_to_be_clickable(
        (By.XPATH,
         "//button[contains(@class,'result_down_btn')]"
         "[.//span[contains(@class,'result_text') and contains(text(),'대화 파일')]]"
        )
    )).click()
    print(f"    ✓ [페이지 {page_num}] 대화 파일.wav 다운로드 요청")
    time.sleep(2)

    # 다운로드 완료 대기
    wait_download(DOWNLOAD_DIR)
    extract_and_remove_zips(DOWNLOAD_DIR)
    print(f"    ✓ [페이지 {page_num}] 다운로드 완료")


def select_all_rows_and_download(driver: webdriver.Chrome) -> None:
    """
    모든 페이지를 순회하며 전체선택 → xlsx + wav 다운로드 반복
    페이지 구조:
      - 한 그룹에 최대 10개 페이지 버튼 (data-cy: pagination_page_num_0 ~ _9, 인덱스 리셋)
      - 다음 그룹: data-cy="pagination_pg_next"
    """
    print("[3~4/4] 페이지별 전체 선택 및 다운로드 시작...")
    wait = WebDriverWait(driver, 20)
    page_num = 1

    while True:
        total_in_group = get_total_pages(driver)
        print(f"\n  현재 그룹 페이지 수: {total_in_group}")

        for idx in range(total_in_group):
            go_to_page(driver, wait, idx)  # 항상 클릭 (이미 표시 중이어도 문제없음)

            print(f"\n  ─ 페이지 {page_num} 처리 중...")
            select_all_and_download_page(driver, wait, page_num)
            page_num += 1

        if not go_to_next_page_group(driver, wait):
            print(f"\n  ✓ 마지막 페이지 그룹 완료. 총 {page_num - 1}페이지 처리.")
            break


def wait_download(folder: str, timeout: int = 300) -> None:
    """
    다운로드 완료 대기
    - zip / wav 파일이 존재하고
    - .crdownload(진행 중) 파일이 없을 때 반환
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        files = os.listdir(folder)
        completed = [
            f for f in files
            if f.endswith(".zip") or f.endswith(".wav")
        ]
        downloading = [f for f in files if f.endswith(".crdownload")]
        if completed and not downloading:
            break
        time.sleep(2)
    else:
        print(f"    ⚠ 다운로드 대기 시간 초과 ({timeout}초). 현재 파일: {os.listdir(folder)}")


def extract_and_remove_zips(folder: str) -> None:
    """zip 파일을 날짜별 하위 폴더(folder/<date>/)로 압축 해제 후 zip 삭제"""
    zip_files = [f for f in os.listdir(folder) if f.endswith(".zip")]
    if not zip_files:
        return
    for zip_name in zip_files:
        zip_path = os.path.join(folder, zip_name)
        try:
            # 파일명에서 날짜 추출 (예: CLOVA CareCall_통화녹음_260323_120428.zip → 260323)
            match = re.search(r'_(\d{6})_', zip_name)
            date_str = match.group(1) if match else "unknown"

            with zipfile.ZipFile(zip_path, "r") as z:
                # Windows 한국어 환경에서 zip 파일명 인코딩 변환 (cp437 → cp949)
                if sys.platform == "win32":
                    for info in z.infolist():
                        try:
                            info.filename = info.filename.encode('cp437').decode('cp949')
                        except (UnicodeDecodeError, UnicodeEncodeError):
                            pass
                sub_folder = os.path.join(folder, date_str)
                os.makedirs(sub_folder, exist_ok=True)
                z.extractall(sub_folder)

            os.remove(zip_path)
            print(f"    ✓ 압축 해제 → {date_str}/ : {zip_name}")
        except Exception as e:
            print(f"    ⚠ zip 처리 실패 ({zip_name}): {e}")


def run(start_date: datetime, end_date: datetime) -> None:
    """
    설정 로드 + 주어진 날짜 범위로 다운로드 실행
    main.py 디스패처 또는 직접 호출용 재사용 진입점
    """
    global EMAIL, PASSWORD, DOWNLOAD_DIR
    try:
        EMAIL, PASSWORD, DOWNLOAD_DIR = load_config(
            "download_dir", default_download_dir("CareCall", "wav")
        )
    except ValueError as e:
        print(f"❌ 설정 오류: {e}")
        sys.exit(1)
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    date_str = f"{start_date.strftime('%Y.%m.%d')} ~ {end_date.strftime('%Y.%m.%d')}"
    print("=" * 55)
    print(" CLOVA CareCall 자동 다운로드 매크로")
    print(f" 대상 날짜: {date_str}")
    print(f" 저장 경로: {DOWNLOAD_DIR}")
    print("=" * 55)

    driver = build_driver()
    try:
        login(driver)
        navigate_and_set_date(driver, start_date, end_date)
        set_page_size_to_150(driver)
        select_all_rows_and_download(driver)
        print("\n✅ 작업 완료!")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        time.sleep(2)
        driver.quit()


def main() -> None:
    """python carecall.py 직접 실행 시 진입점"""
    try:
        start_date, end_date = parse_date_range()
    except ValueError as e:
        print(f"❌ 입력 오류: {e}")
        sys.exit(1)
    run(start_date, end_date)


if __name__ == "__main__":
    main()