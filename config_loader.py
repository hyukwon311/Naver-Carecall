"""
CLOVA CareCall 매크로 공통 설정 로더
"""

import os
import sys
import configparser

_CONFIG_TEMPLATE = """\
# CLOVA CareCall 매크로 설정 파일
# 값을 채운 뒤 저장하세요. 이 파일은 절대 공유/커밋하지 마세요.

[auth]
email = your-email@example.com
password = your-password

[paths]
# 다운로드 저장 폴더 (비워두면 OS별 기본값 사용)
#   Windows 기본값: C:\\CareCall\\wav  /  C:\\CareCall\\urgent
#   Mac/Linux 기본값: ~/Downloads/CareCall/wav  /  ~/Downloads/CareCall/urgent
download_dir =
urgent_download_dir =
"""

def _get_config_path() -> str:
    """.exe 실행 시 .exe 옆, .py 실행 시 스크립트 옆의 config.ini 경로"""
    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "config.ini")


def default_download_dir(*parts: str) -> str:
    """
    OS별 기본 다운로드 경로
    - Windows: C:\\<parts...>
    - Mac/Linux: ~/Downloads/<parts...>
    예: default_download_dir("CareCall", "wav") → ~/Downloads/CareCall/wav
    """
    if sys.platform == "win32":
        return os.path.join("C:\\", *parts)
    return os.path.join(os.path.expanduser("~"), "Downloads", *parts)


def load_config(download_dir_key: str, fallback_dir: str) -> tuple[str, str, str]:
    """
    config.ini에서 email, password, <download_dir_key> 로드
    - 파일이 없으면 템플릿 생성 후 안내 메시지와 함께 종료
    - 플레이스홀더 값이면 ValueError
    - download_dir_key 값이 비어있으면 fallback_dir 사용
    """
    config_path = _get_config_path()

    if not os.path.exists(config_path):
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(_CONFIG_TEMPLATE)
        print(f"❌ 설정 파일이 없어 템플릿을 생성했습니다:\n   {config_path}")
        print("   파일을 열어 email/password를 입력한 뒤 다시 실행해주세요.")
        sys.exit(1)

    parser = configparser.ConfigParser()
    parser.read(config_path, encoding="utf-8")

    try:
        email    = parser["auth"]["email"].strip()
        password = parser["auth"]["password"].strip()
    except KeyError as e:
        raise ValueError(f"config.ini에 [auth] 섹션 또는 {e} 키가 없습니다.")

    if not email or email == "your-email@example.com":
        raise ValueError(f"config.ini의 email을 실제 값으로 변경하세요: {config_path}")
    if not password or password == "your-password":
        raise ValueError(f"config.ini의 password를 실제 값으로 변경하세요: {config_path}")

    download_dir = parser.get("paths", download_dir_key, fallback="").strip()
    if not download_dir:
        download_dir = fallback_dir
    download_dir = os.path.abspath(download_dir)

    return email, password, download_dir