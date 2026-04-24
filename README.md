# Naver CareCall 자동 다운로드 매크로

CLOVA CareCall 대시보드에서 지정 기간의 '대화 파일.wav'를 자동으로 다운로드하고 날짜별 폴더로 정리하는 Selenium 기반 매크로입니다.

## 요구사항

- Python 3.9 이상
- Google Chrome (최신 버전)
- macOS / Windows

## 설치

```bash
pip install -r requirements.txt
```

`webdriver-manager`가 첫 실행 시 시스템에 맞는 ChromeDriver를 자동으로 다운로드합니다.

## 설정 (config.ini)

### 최초 실행 시 자동 생성

`config.ini` 없이 실행하면 프로젝트 루트(`.py` 실행 시) 또는 `.exe` 옆(바이너리 실행 시)에 템플릿이 자동 생성되고 프로그램이 종료됩니다.

```
❌ 설정 파일이 없어 템플릿을 생성했습니다:
   /path/to/config.ini
   파일을 열어 email/password를 입력한 뒤 다시 실행해주세요.
```

### config.ini 내용

```ini
[auth]
email    = your-email@example.com
password = your-password

[paths]
# 비워두면 OS별 기본값 사용
#   Windows: C:\CareCall\wav  /  C:\CareCall\urgent
#   Mac/Linux: ~/Downloads/CareCall/wav  /  ~/Downloads/CareCall/urgent
download_dir        =
urgent_download_dir =
```

- `download_dir`: `carecall.py` (대화 파일.wav)가 사용
- `urgent_download_dir`: `carecall_urgent.py` (긴급 알림)가 사용

- `config.ini`는 `.gitignore`에 등록되어 있어 커밋되지 않습니다. **절대 공유하거나 커밋하지 마세요.**

## 실행

통합 진입점은 **`main.py`** 입니다. 개별 스크립트(`carecall.py`, `carecall_urgent.py`)를 직접 실행해도 동작합니다.

### 1. 대화형 메뉴 (가장 간단)

```bash
python main.py
```

작업 선택 프롬프트가 뜹니다:
```
 1. 대화 파일(.wav) 다운로드  [기간 지정 가능]
 2. 긴급 알림 다운로드        [어제 고정]
 선택 [1/2]:
```

`1`을 고르면 시작일·종료일 입력을 받습니다 (Enter 두 번 → 이전 7일).

### 2. CLI 서브커맨드 (스케줄러/자동화)

```bash
python main.py wav                                    # 이전 7일 (기본)
python main.py wav --start 20260401 --end 20260407    # 특정 기간
python main.py urgent                                 # 어제 하루 (기본)
python main.py urgent --start 20260401 --end 20260407 # 특정 기간
python main.py urgent --start 20260401 --end 20260401 # 특정 하루
```

시작일과 종료일이 동일하면 그날 하루만 다운로드됩니다.

### 3. 개별 스크립트 직접 실행

```bash
python carecall.py --start 20260401 --end 20260407
python carecall_urgent.py --start 20260401 --end 20260401
```

## 동작 흐름

1. `config.ini` 로드 및 검증
2. 날짜 범위 결정 (CLI 인자 → 대화형 → 기본값)
3. Chrome 실행 → CLOVA CareCall 로그인
4. 캠페인 현황 페이지 이동 → 달력에서 시작일·종료일 선택 → 적용
5. 페이지 크기 150으로 변경
6. 모든 페이지 순회하며 전체 선택 → 대화 파일.wav 다운로드
7. 다운로드된 zip을 날짜별 폴더(`CareCall/wav/YYMMDD/`)로 분리·압축 해제

## .exe 빌드 (Windows 배포용)

통합 진입점 `main.py`를 단일 .exe로 빌드합니다:

```bash
pip install pyinstaller
pyinstaller --onefile --name carecall main.py
```

생성된 `dist/carecall.exe`를 원하는 위치로 옮기고, **같은 폴더에 `config.ini`를 함께 두세요**. 하나의 .exe로 두 작업(`wav` / `urgent`)을 모두 실행할 수 있습니다.

예:
```cmd
carecall.exe                                  :: 대화형 메뉴
carecall.exe wav --start 20260401 --end 20260407
carecall.exe urgent
```

주의사항:
- `--noconsole` / `--windowed` 플래그는 사용하지 마세요 — 날짜 입력 프롬프트와 오류 메시지 출력을 위해 콘솔이 필요합니다.
- 첫 실행 시 ChromeDriver를 다운로드하므로 인터넷 연결이 필요합니다.

## 디렉토리 구조

```
Naver-Carecall/
├── main.py              # 통합 진입점 (서브커맨드 디스패처)
├── carecall.py          # 대화 파일 다운로드 로직
├── carecall_urgent.py   # 긴급 알림 다운로드 로직
├── config_loader.py     # 공통 설정 로더
├── date_utils.py        # 공통 날짜 파싱 유틸
├── config.ini           # 로컬 설정 (gitignored)
├── requirements.txt
├── .gitignore
└── README.md
```

다운로드 저장 구조 (예: `~/Downloads/CareCall/`):

```
CareCall/
├── wav/                 # carecall.py
│   ├── 260401/
│   │   ├── 통화1.wav
│   │   └── 통화2.wav
│   └── 260402/
│       └── ...
└── urgent/              # carecall_urgent.py (폴더/파일명은 end_date 기준)
    ├── 20260401/
    │   └── 20260401.xlsx
    └── 20260407/
        └── 20260407.xlsx
```

## 트러블슈팅

- **ChromeDriver 버전 불일치**: Chrome을 최신 버전으로 업데이트한 후 재실행.
- **다운로드가 저장 폴더로 가지 않음**: Chrome의 SafeBrowsing 경고 차단 문제일 수 있음. 코드에서 이미 비활성화 처리되어 있으나, 회사 보안 정책으로 강제 활성화된 경우 관리자 문의 필요.
- **로그인 실패**: `config.ini`의 email/password 오타 확인. CLOVA 웹에서 수동 로그인 테스트.
- **달력에서 다른 달 선택 안 됨**: `_m_prev` / `_m_next` 버튼 클래스명이 바뀐 경우. 개발자 도구로 실제 클래스 확인 후 `carecall.py`의 `_navigate_calendar_*` 함수 셀렉터 수정.