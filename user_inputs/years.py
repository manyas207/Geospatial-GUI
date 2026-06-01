"""Year or year-range selection for scene search."""

from dataclasses import dataclass


@dataclass(frozen=True)
class YearRange:
    start: int
    end: int

    def years(self) -> list[int]:
        return list(range(self.start, self.end + 1))


def parse_years(value: str | list[int]) -> list[int]:
    """Parse UI input such as '2019,2020' or '2018-2022'."""
    if isinstance(value, list):
        return sorted({int(y) for y in value})
    text = value.strip()
    if "-" in text and "," not in text:
        start_s, end_s = text.split("-", 1)
        return list(range(int(start_s), int(end_s) + 1))
    return sorted({int(part.strip()) for part in text.split(",") if part.strip()})
