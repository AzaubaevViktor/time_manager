"""Слежение за временем
Что мне нужно:
* Создавать классы задач и подклассы задач
* Отмечать время начала и время конца, желательно с коррекцией +10m
* Сохранять данные куда-нибудь
* Смотреть сводную статистику

"""
from time import time
from traceback import print_exc


class Modifier:
    def __init__(self, value: str):
        self.value = value

    def __int__(self):
        return self.value


class Interval:
    def __init__(self, modify: Modifier):
        self.start = time() + int(modify)
        self.end = None

    def end(self, modify: Modifier):
        self.end = time() + int(modify)


class Task:
    VERSION = 0

    def __init__(self, parent, name):
        self.name = name
        self.decsriiption = ""
        self.parent = parent
        self.intervals = []
        self.childs = {}

    def __getitem__(self, item):
        self.childs.setdefault(item, Task(self, item))
        return self.childs[item]

    def __iadd__(self, interval: Interval):
        self.intervals.append(interval)

    def save(self) -> dict:
        pass

    @classmethod
    def load(cls, raw_data) -> dict:
        pass

# ======= MAIN CYCLE ========


class TimeManager:
    def __init__(self):
        self._running = True
        self.funcs = {
            attr: getattr(self, attr)
            for attr
            in self.__dir__()
            if not attr.startswith("_")
        }
        del self.funcs['run']

    def test(self, *args):
        print("Test function")
        print(f"Arguments: {args}")

    test.description = "Just test function"

    def exit(self, *args):
        print("Bye!")
        self._running = False

    def _incorrect_name(self, func_name, *args):
        print(f"{func_name} not found in this scope.")
        print("Existing names:")
        for name, func in self.funcs.items():
            description = getattr(func, "description", "")
            print(f"  `{name}`: {description}")

    def run(self):
        while self._running:
            try:
                self._cycle()
            except Exception:
                print_exc()

    def _cycle(self):
        a = input("> ")
        f_name, *args = self._split_tokens(a)
        func = self.funcs.get(
            f_name,
            lambda *args: self._incorrect_name(f_name, *args)
        )
        func(*args)
        print()

    def _split_tokens(self, raw: str):
        return [word for word in raw.split(" ") if word]


tm = TimeManager()
tm.run()
