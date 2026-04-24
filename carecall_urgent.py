"""
CLOVA CareCall 긴급 알림 다운로드 매크로
- 로그인 후 캠페인 현황 페이지 이동
- '긴급 알림' 탭 클릭 → 우측 상단 다운로드 버튼 클릭
- 기간: 시작일~종료일 (동일하면 그날 하루). 인자 없으면 어제 하루.
- 의존성 설치: pip install -r requirements.txt
- 자격증명 및 다운로드 폴더: config.ini (carecall.py와 공유)
"""

import time
import os
import sys
import argparse
from datetime import datetime
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

# Config 변수 (run()에서 load_config로 초기화)
EMAIL: str = ""
PASSWORD: str = ""
DOWNLOAD_DIR: str = ""


def parse_date_range() -> tuple[datetime, datetime]:
    """sys.argv에서 --start/--end 파싱 → resolve_date_range (default: 어제 하루)"""
    parser = argparse.ArgumentParser(
        description="CLOVA CareCall 긴급 알림 다운로드 매크로",
        add_help=True,
    )
    parser.add_argument("--start", help="시작일 (YYYYMMDD)")
    parser.add_argument("--end",   help="종료일 (YYYYMMDD)")
    args = parser.parse_args()
    return resolve_date_range(args.start, args.end, default_days_back=1)


def build_driver() -> webdriver.Chrome:
    """Chrome 드라이버 초기화 (자동 다운로드 설정 포함)"""
    options = Options()

    prefs = {
        "download.default_directory": DOWNLOAD_DIR,
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

    # 백그라운드 실행 원하면 주석 해제
    # options.add_argument("--headless=new")
    options.add_argument("--window-size=1400,900")
    options.add_argument("--disable-notifications")

    if sys.platform == "win32":
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-features=InsecureDownloadWarnings")
        options.add_argument("--safebrowsing-disable-download-protection")
        options.add_argument("--disable-popup-blocking")

    service = Service(ChromeDriverManager().install())
    driver  = webdriver.Chrome(service=service, options=options)
    driver.implicitly_wait(10)

    driver.execute_cdp_cmd(
        "Page.setDownloadBehavior",
        {"behavior": "allow", "downloadPath": DOWNLOAD_DIR}
    )

    return driver


def login(driver: webdriver.Chrome) -> None:
    """로그인 처리"""
    print(f"[1/3] 로그인 중... ({LOGIN_URL})")
    driver.get(LOGIN_URL)
    wait = WebDriverWait(driver, 20)

    email_input = wait.until(EC.presence_of_element_located(
        (By.CSS_SELECTOR, "input[name='email'][data-cy='login_input_id']")
    ))
    email_input.clear()
    email_input.send_keys(EMAIL)

    pw_input = wait.until(EC.presence_of_element_located(
        (By.CSS_SELECTOR, "input[type='password'][name='password']")
    ))
    pw_input.clear()
    pw_input.send_keys(PASSWORD)

    login_btn = wait.until(EC.element_to_be_clickable(
        (By.CSS_SELECTOR, "button[data-cy='btn_login']")
    ))
    login_btn.click()

    wait.until(EC.url_changes(LOGIN_URL))
    print("    ✓ 로그인 성공")


def navigate_and_set_date(driver: webdriver.Chrome,
                          start_date: datetime, end_date: datetime) -> None:
    """
    캠페인 현황 페이지 이동 후 '직접 선택' → 시작일·종료일 범위 선택 + 적용
    start == end 이면 같은 날을 두 번 클릭해 단일 일 범위 생성
    """
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

    # ── '직접 선택' 라디오 클릭 (임의 기간 선택 활성화) ──
    custom_label = wait.until(EC.element_to_be_clickable(
        (By.XPATH, "//label[@for='custom' and contains(@class,'date_picker_dropdown_radio_label')]")
    ))
    custom_label.click()
    time.sleep(0.5)

    # ── 시작일: 해당 달로 backward 이동 후 클릭 ──
    _navigate_calendar_to_month(driver, start_date.year, start_date.month)
    _click_calendar_day(driver, wait, str(start_date.day))
    time.sleep(0.5)

    # ── 종료일: 다른 달이면 forward 이동, 같은 날이어도 한 번 더 클릭해 범위 확정 ──
    if (end_date.year, end_date.month) != (start_date.year, start_date.month):
        _navigate_calendar_forward_to_month(driver, end_date.year, end_date.month)
    _click_calendar_day(driver, wait, str(end_date.day))
    time.sleep(0.5)

    # ── '적용' 버튼 클릭 ──
    apply_btn = wait.until(EC.element_to_be_clickable(
        (By.CSS_SELECTOR, "button[class*='date_picker_dropdown_btn_comp']")
    ))
    apply_btn.click()
    time.sleep(3)
    print(f"    ✓ 날짜 설정 완료 ({date_str})")


def _navigate_calendar_to_month(driver, target_year: int, target_month: int) -> None:
    """달력 헤더가 target_year년 target_month월이 될 때까지 '이전 달' 반복 클릭"""
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
            prev_btn = driver.find_element(
                By.CSS_SELECTOR, "button[class*='date_picker_dropdown_m_prev']"
            )
            prev_btn.click()
            time.sleep(0.4)
        except Exception:
            break


def _navigate_calendar_forward_to_month(driver, target_year: int, target_month: int) -> None:
    """달력 헤더가 target_year년 target_month월이 될 때까지 '다음 달' 반복 클릭"""
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


def _click_calendar_day(driver, wait, day_str: str, timeout: int = 10) -> None:
    """rdr 달력에서 해당 '일' 숫자를 가진 버튼 클릭"""
    local_wait = WebDriverWait(driver, timeout)
    day_btn = local_wait.until(EC.element_to_be_clickable(
        (By.XPATH,
         f"//button[contains(@class,'rdrDay')"
         f"  and not(contains(@class,'rdrDayPassive'))"
         f"  and not(contains(@class,'rdrDayDisabled'))]"
         f"  /span[contains(@class,'rdrDayNumber')]"
         f"  /span[normalize-space(text())='{day_str}']"
         f"  /.."
         f"  /.."
        )
    ))
    day_btn.click()


def click_urgent_tab(driver: webdriver.Chrome) -> None:
    """'긴급 알림' 탭 클릭"""
    print(f"[3/4] 긴급 알림 탭 선택")
    wait = WebDriverWait(driver, 20)

    # '긴급 알림' 탭 버튼 클릭
    # - '상태 이상'도 result_red_theme 클래스를 가지므로 텍스트로 구분 필수
    # - <p class="result_info__..."> 의 직접 텍스트 노드가 "긴급 알림"
    urgent_btn = wait.until(EC.element_to_be_clickable(
        (By.XPATH,
         "//button[@role='tab']"
         "[.//p[contains(@class,'result_info')]"
         "   /text()[normalize-space()='긴급 알림']]"
        )
    ))
    urgent_btn.click()
    time.sleep(2)
    print("    ✓ 긴급 알림 탭 선택 완료")


def click_download_button(driver: webdriver.Chrome, date_file: str) -> None:
    """다운로드 버튼 클릭 후 파일을 date_file(YYYYMMDD) 기준으로 이름/폴더 변경"""
    print(f"[4/4] 다운로드 버튼 클릭")
    wait = WebDriverWait(driver, 20)

    # 다운로드 직전의 기존 파일 목록 — 이후 새 파일 식별용
    before_files = set(os.listdir(DOWNLOAD_DIR))

    # 다운로드 버튼: img[src='/img/svg/icon_btn_download.svg']의 부모 button
    # 혹은 tooltip 텍스트 '다운로드'를 가진 button
    download_btn = wait.until(EC.element_to_be_clickable(
        (By.XPATH,
         "//button[.//img[contains(@src,'icon_btn_download')]]"
         " | "
         "//button[.//span[contains(@class,'tooltip') and normalize-space(text())='다운로드']]"
        )
    ))
    download_btn.click()
    print("    ✓ 다운로드 버튼 클릭")
    time.sleep(2)

    # 다운로드 확인 모달이 뜨면 "다운로드" 버튼 클릭 (있을 경우)
    try:
        confirm_btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "button[class*='download_setting_modal_btn_download']")
        ))
        confirm_btn.click()
        print("    ✓ 다운로드 모달 확인")
        time.sleep(2)
    except Exception:
        # 모달 없이 바로 다운로드되는 경우 무시
        pass

    # 새로 추가된 파일이 완료될 때까지 대기
    new_file = wait_new_download(DOWNLOAD_DIR, before_files)
    if new_file:
        renamed = rename_to_date(DOWNLOAD_DIR, new_file, date_file)
        print(f"    ✓ 다운로드 완료 → {renamed}")
    else:
        print("    ⚠ 새 다운로드 파일을 찾지 못했습니다.")


def wait_new_download(folder: str, before_files: set, timeout: int = 120) -> str:
    """
    다운로드 완료 대기 후 새로 추가된 파일명 반환
    - before_files 에 없는 파일 중 .crdownload 가 아닌 파일이 나타나면 반환
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        current = set(os.listdir(folder))
        new_files = current - before_files
        completed = [
            f for f in new_files
            if f.endswith((".zip", ".xlsx", ".csv", ".wav"))
               and not f.endswith(".crdownload")
        ]
        downloading = [f for f in new_files if f.endswith(".crdownload")]
        if completed and not downloading:
            # 가장 최근 수정된 파일 반환
            completed.sort(
                key=lambda f: os.path.getmtime(os.path.join(folder, f)),
                reverse=True,
            )
            return completed[0]
        time.sleep(1)
    print(f"    ⚠ 다운로드 대기 시간 초과 ({timeout}초).")
    return ""


def rename_to_date(folder: str, filename: str, date_str: str) -> str:
    """
    folder/<date_str>/ 하위 폴더를 만들고, 파일명을 date_str + 원본 확장자로 변경 후 이동.
    동일 이름이 이미 있으면 _1, _2 ... 접미사 부여.
    반환값은 folder 기준 상대 경로 (예: "20260423/20260423.xlsx").
    """
    src = os.path.join(folder, filename)
    _, ext = os.path.splitext(filename)
    date_folder = os.path.join(folder, date_str)
    os.makedirs(date_folder, exist_ok=True)

    new_name = f"{date_str}{ext}"
    dst = os.path.join(date_folder, new_name)

    idx = 1
    while os.path.exists(dst):
        new_name = f"{date_str}_{idx}{ext}"
        dst = os.path.join(date_folder, new_name)
        idx += 1

    os.rename(src, dst)
    return os.path.join(date_str, new_name)


def run(start_date: datetime, end_date: datetime) -> None:
    """
    설정 로드 + 주어진 기간의 긴급 알림 다운로드 실행
    main.py 디스패처 또는 직접 호출용 재사용 진입점
    start == end 이면 그날 하루만 다운로드
    파일명/폴더는 end_date 기준 YYYYMMDD
    """
    global EMAIL, PASSWORD, DOWNLOAD_DIR
    try:
        EMAIL, PASSWORD, DOWNLOAD_DIR = load_config(
            "urgent_download_dir", default_download_dir("CareCall", "urgent")
        )
    except ValueError as e:
        print(f"❌ 설정 오류: {e}")
        sys.exit(1)
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    date_str  = f"{start_date.strftime('%Y.%m.%d')} ~ {end_date.strftime('%Y.%m.%d')}"
    date_file = end_date.strftime("%Y%m%d")  # 파일명·폴더 라벨

    print("=" * 55)
    print(" CLOVA CareCall 긴급 알림 다운로드 매크로")
    print(f" 대상 날짜: {date_str}")
    print(f" 저장 경로: {DOWNLOAD_DIR}")
    print("=" * 55)

    driver = build_driver()
    try:
        login(driver)
        navigate_and_set_date(driver, start_date, end_date)
        click_urgent_tab(driver)
        click_download_button(driver, date_file)
        print("\n✅ 작업 완료!")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        time.sleep(2)
        driver.quit()


def main() -> None:
    """python carecall_urgent.py 직접 실행 시 진입점"""
    try:
        start_date, end_date = parse_date_range()
    except ValueError as e:
        print(f"❌ 입력 오류: {e}")
        sys.exit(1)
    run(start_date, end_date)


if __name__ == "__main__":
    main()