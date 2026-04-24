"""
CLOVA CareCall 통합 진입점

사용법:
  python main.py                                   (대화형 메뉴)
  python main.py wav                               (대화 파일, 이전 7일 기본)
  python main.py wav --start 20260401 --end 20260407
  python main.py urgent                            (긴급 알림, 어제)
"""

import argparse
import sys

from date_utils import resolve_date_range


def _interactive_menu() -> argparse.Namespace:
    """CLI 인자 없이 실행됐을 때 대화형으로 작업 선택"""
    print("=" * 55)
    print(" CLOVA CareCall 자동 다운로드")
    print("=" * 55)
    print(" 1. 대화 파일(.wav) 다운로드")
    print(" 2. 긴급 알림(.xlsx) 다운로드")
    print("=" * 55)
    choice = input(" 선택 [1/2]: ").strip()

    if choice == "1":
        return argparse.Namespace(command="wav", start=None, end=None)
    if choice == "2":
        return argparse.Namespace(command="urgent", start=None, end=None)

    print(f"❌ 잘못된 선택: {choice!r}")
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CLOVA CareCall 통합 진입점 (대화 파일 / 긴급 알림)",
    )
    subparsers = parser.add_subparsers(dest="command")

    _same_day_note = "시작일과 종료일이 동일하면 그날 하루 데이터만 다운로드됩니다."

    wav_parser = subparsers.add_parser(
        "wav",
        help="대화 파일(.wav) 다운로드 [기본: 이전 7일]",
        description=_same_day_note,
    )
    wav_parser.add_argument("--start", help="시작일 (YYYYMMDD)")
    wav_parser.add_argument("--end",   help="종료일 (YYYYMMDD)")

    urgent_parser = subparsers.add_parser(
        "urgent",
        help="긴급 알림 다운로드 [기본: 어제 하루]",
        description=_same_day_note,
    )
    urgent_parser.add_argument("--start", help="시작일 (YYYYMMDD)")
    urgent_parser.add_argument("--end",   help="종료일 (YYYYMMDD)")

    args = parser.parse_args()

    # 인자가 하나도 없으면 대화형 메뉴
    if args.command is None:
        args = _interactive_menu()

    # 서브커맨드별 기본 범위: wav=7일, urgent=1일(어제 하루)
    default_days = 7 if args.command == "wav" else 1
    try:
        start_date, end_date = resolve_date_range(
            args.start, args.end, default_days_back=default_days
        )
    except ValueError as e:
        print(f"❌ 입력 오류: {e}")
        sys.exit(1)

    if args.command == "wav":
        import carecall
        carecall.run(start_date, end_date)
    elif args.command == "urgent":
        import carecall_urgent
        carecall_urgent.run(start_date, end_date)


if __name__ == "__main__":
    main()
