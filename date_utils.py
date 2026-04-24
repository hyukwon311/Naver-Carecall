"""날짜 범위 파싱 공통 유틸 (carecall.py / carecall_urgent.py 공유)"""

from datetime import datetime, timedelta


def resolve_date_range(
    start_str: str | None,
    end_str: str | None,
    *,
    default_days_back: int = 7,
) -> tuple[datetime, datetime]:
    """
    YYYYMMDD 문자열 → datetime 범위 변환
    - 둘 다 비어있으면 대화형 입력 → 그래도 비어있으면 디폴트
      디폴트: end=어제, start=end - (default_days_back - 1)
      예) default_days_back=7 → 이전 7일 (wav)
          default_days_back=1 → 어제 하루 (urgent)
    - 형식 오류 / 순서 오류 시 ValueError
    """
    if not start_str and not end_str:
        label = f"어제 기준 {default_days_back}일" if default_days_back > 1 else "어제 하루"
        print(f"날짜 범위를 입력하세요 (둘 다 Enter → 기본값: {label})")
        print("  ※ 시작일과 종료일이 동일하면 그날 하루 데이터만 다운로드됩니다.")
        start_str = input("  시작일 (YYYYMMDD, 예: 20260401): ").strip()
        end_str   = input("  종료일 (YYYYMMDD, 예: 20260407): ").strip()

    if not start_str and not end_str:
        end_date   = datetime.now() - timedelta(days=1)
        start_date = end_date - timedelta(days=default_days_back - 1)
        return start_date, end_date

    if not start_str or not end_str:
        raise ValueError("시작일과 종료일을 모두 입력하거나 모두 비워두세요.")

    try:
        start_date = datetime.strptime(start_str, "%Y%m%d")
        end_date   = datetime.strptime(end_str,   "%Y%m%d")
    except ValueError as e:
        raise ValueError(f"날짜 형식 오류 (YYYYMMDD 8자리): {e}")

    if end_date < start_date:
        raise ValueError(f"종료일({end_str})이 시작일({start_str})보다 이전입니다.")

    return start_date, end_date
