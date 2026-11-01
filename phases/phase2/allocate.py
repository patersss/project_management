import argparse
import csv
import sys
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from statistics import median


MEMBERS = (
    ("leonid", "Челяпин Леонид"),
    ("dmitry", "Засыпко Дмитрий"),
    ("andrey", "Сопельняк Андрей"),
)
HOUR_COLUMNS = tuple(f"hours_{key}" for key, _ in MEMBERS)
PREFERENCE_COLUMNS = tuple(f"preference_{key}" for key, _ in MEMBERS)


@dataclass(frozen=True)
class Task:
    code: str
    title: str
    hours: int
    preferences: tuple[int, ...]


@dataclass(frozen=True)
class Allocation:
    members: tuple[int, ...]
    hours: tuple[int, ...]
    score: int

    def rank(self) -> tuple[int, int, tuple[int, ...]]:
        spread = max(self.hours) - min(self.hours)
        return -self.score, spread, self.members


def read_integer(row: dict[str, str], column: str, low: int, high: int | None = None) -> int:
    bounds = f"от {low} до {high}" if high is not None else f"от {low}"
    message = f"{column}: ожидается целое число {bounds}"
    try:
        value = int(row[column])
    except ValueError:
        raise ValueError(message) from None
    if value < low or (high is not None and value > high):
        raise ValueError(message)
    return value


def read_tasks(path: Path) -> list[Task]:
    tasks = []
    seen_codes = set()
    columns = ("id", "task", *HOUR_COLUMNS, *PREFERENCE_COLUMNS)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter=";", strict=True)
        if sorted(reader.fieldnames or []) != sorted(columns):
            raise ValueError(f"{path.name}: ожидаются столбцы {', '.join(columns)}")
        for row in reader:
            line = f"{path.name}, строка {reader.line_num}"
            if None in row or None in row.values():
                raise ValueError(f"{line}: неверное число полей")
            code, title = row["id"].strip(), row["task"].strip()
            if not code or not title:
                raise ValueError(f"{line}: нужны код и название задачи")
            if code in seen_codes:
                raise ValueError(f"{line}: повторяется код задачи {code}")
            try:
                hours = median(read_integer(row, column, 1) for column in HOUR_COLUMNS)
                preferences = tuple(read_integer(row, column, 1, 5) for column in PREFERENCE_COLUMNS)
            except ValueError as error:
                raise ValueError(f"{line}: {error}") from error
            tasks.append(Task(code, title, hours, preferences))
            seen_codes.add(code)
    if not tasks:
        raise ValueError(f"{path.name}: нет задач для распределения")
    return tasks


def solve(
    tasks: list[Task], min_hours: int, max_hours: int,
) -> tuple[Allocation | None, Allocation]:
    member_indices = range(len(MEMBERS))
    balanced = None
    unrestricted = None
    for members in product(member_indices, repeat=len(tasks)):
        hours = [0] * len(MEMBERS)
        score = 0
        for task, member in zip(tasks, members):
            hours[member] += task.hours
            score += task.preferences[member]
        allocation = Allocation(members, tuple(hours), score)
        if unrestricted is None or allocation.rank() < unrestricted.rank():
            unrestricted = allocation
        if all(min_hours <= hours_worked <= max_hours for hours_worked in hours):
            if balanced is None or allocation.rank() < balanced.rank():
                balanced = allocation
    assert unrestricted is not None  # product всегда даёт хотя бы одно назначение.
    return balanced, unrestricted


def print_allocation(title: str, tasks: list[Task], allocation: Allocation) -> None:
    print(title)
    print("Код | Задача | Ответственный | Часы | Балл")
    for task, member in zip(tasks, allocation.members):
        print(f"{task.code} | {task.title} | {MEMBERS[member][1]} | {task.hours} | {task.preferences[member]}")
    for (_, name), hours in zip(MEMBERS, allocation.hours):
        print(f"{name}: {hours} ч")
    print(f"Сумма предпочтений: {allocation.score}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, default=Path(__file__).with_name("estimates.csv"),
        help="путь к CSV с оценками",
    )
    parser.add_argument("--min-hours", type=int, default=7, help="нижняя граница нагрузки")
    parser.add_argument("--max-hours", type=int, default=10, help="верхняя граница нагрузки")
    arguments = parser.parse_args()
    if not 0 <= arguments.min_hours <= arguments.max_hours:
        parser.error("границы нагрузки должны удовлетворять 0 <= --min-hours <= --max-hours")
    try:
        tasks = read_tasks(arguments.input)
    except (OSError, ValueError, csv.Error) as error:
        parser.error(str(error))

    balanced, unrestricted = solve(tasks, arguments.min_hours, arguments.max_hours)
    limits = f"{arguments.min_hours}–{arguments.max_hours} ч на участника"
    if balanced is None:
        print(f"Нет допустимого решения при ограничении {limits}.")
    else:
        print_allocation(f"Распределение с ограничением {limits}", tasks, balanced)
    print()
    print_allocation("Распределение без ограничения нагрузки", tasks, unrestricted)
    return 0 if balanced is not None else 1


if __name__ == "__main__":
    # Сохраняем кириллицу при перенаправлении вывода в Windows.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
