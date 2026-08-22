from datetime import date

from argumenta.domain.habit import current_streak, longest_streak


class TestCurrentStreak:
    def test_no_practice_is_no_streak(self) -> None:
        assert current_streak([], date(2026, 8, 22)) == 0

    def test_today_counts(self) -> None:
        days = [date(2026, 8, 22), date(2026, 8, 21)]
        assert current_streak(days, date(2026, 8, 22)) == 2

    def test_yesterday_still_counts_because_today_is_pending(self) -> None:
        assert current_streak([date(2026, 8, 21)], date(2026, 8, 22)) == 1

    def test_a_gap_of_two_days_breaks_it(self) -> None:
        assert current_streak([date(2026, 8, 20)], date(2026, 8, 22)) == 0


class TestLongestStreak:
    def test_no_practice_is_no_record(self) -> None:
        assert longest_streak([]) == 0

    def test_the_record_survives_a_broken_streak(self) -> None:
        days = [
            date(2026, 8, 1),
            date(2026, 8, 2),
            date(2026, 8, 3),
            date(2026, 8, 10),
        ]
        assert longest_streak(days) == 3

    def test_duplicates_do_not_inflate_the_record(self) -> None:
        assert longest_streak([date(2026, 8, 1), date(2026, 8, 1)]) == 1

    def test_unsorted_days_still_measure(self) -> None:
        assert longest_streak([date(2026, 8, 3), date(2026, 8, 1), date(2026, 8, 2)]) == 3
