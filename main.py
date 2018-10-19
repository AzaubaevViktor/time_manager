"""Слежение за временем
Что мне нужно:
+ Создавать классы задач и подклассы задач
+ Отмечать время начала и время конца, желательно с коррекцией
+ Сохранять данные куда-нибудь
* Смотреть сводную статистику
* Уведомления
* Автодополнение
    * Работа с текущей строкой и строкой автодополнения
    * Интерфейс для каждой команды
    * Реализация этого интерфейса

"""
import json
import re
from functools import reduce
from time import time
from traceback import print_exc
from typing import Union, Dict, List


class TMException(Exception):
    def __init__(self, msg, *args):
        self.msg = msg
        self.args = args

    def __str__(self):
        return f"{self.msg},{f' {self.args}' if self.args else ''}"


class Time:
    r = re.compile(r"(-?)([0-9]+)([smh]?)")
    coefs = {
        's': 1,
        'm': 60,
        'h': 3600
    }

    def __init__(self, value: Union[str, int, float]):
        self.value = 0
        if value is None:
            return

        if isinstance(value, str):
            if not value:
                return

            match = self.r.match(value)
            if not match.groups():
                raise TMException(f"{value} не является модификатором времени")

            sign, num, tp = match.groups()
            self.value = int(num)
            if sign: self.value = -self.value
            tp = tp or 'm'
            self.value *= self.coefs[tp]
        elif isinstance(value, int):
            self.value = value
        elif isinstance(value, float):
            self.value = value
        else:
            raise TMException(f"{value} не является модификатором времени")

    def __int__(self):
        return int(self.value)

    def __float__(self):
        return float(self.value)

    def __add__(self, other):
        if isinstance(other, int) or isinstance(other, float):
            return Time(self.value + other)
        else:
            raise TypeError(f"Time нельзя складывать с {type(other)}")

    def __radd__(self, other):
        return self + other

    def __sub__(self, other):
        if isinstance(other, int) or isinstance(other, float):
            return Time(self.value - other)
        else:
            raise TypeError(f"Из Time нельзя вычитать {type(other)}")

    def __rsub__(self, other):
        return self - other

    def __format__(self, format_spec):
        v, m = self._get_value_sym()
        return f"{v:{format_spec}}{m}"

    def _get_value_sym(self):
        s = self.value
        if abs(s) < 90:
            return s, 's'
        # minutes
        m = s / 60
        if abs(m) < 90:
            return m, 'm'
        # hours
        h = m / 60
        if abs(h) < 30:
            return h, 'h'
        # days
        d = h / 60
        return d, 'd'

    def __str__(self):
        return f"{self:.1f}"


class Interval:
    def __init__(self, modify: Time = None):
        modify = modify or 0
        self.start = time() + int(modify)
        self.end = None

    def stop(self, modify: Time = None):
        modify = float(modify or 0)
        end = time() + modify
        if end < self.start:
            raise TMException(f"Максимальная коррекция времени: {Time(-time() + self.start):.1f}")

        self.end = end

    def save(self) -> dict:
        return {
            'start': float(self.start),
            'end': float(self.end) if self.end else None
        }

    @classmethod
    def load(cls, raw_data) -> "Interval":
        i = Interval()
        i.start = raw_data['start']
        i.end = raw_data['end']
        return i

    def __str__(self):
        end = self.end or time()
        return str(Time(end - self.start))


class Task:
    VERSION = 0

    def __init__(self, parent: "Task", name):
        self.name: str = name
        self.path: str = (parent.path + name if parent else "") + "/"
        self.decsription = ""
        self.parent: "Task" = parent
        if parent:
            self.parent.childs.setdefault(name, self)
            if self.parent.childs[name] != self:
                raise TMException("Нарушение целостности storage!")

        self.intervals: List[Interval] = []
        self.childs: Dict[str, "Task"] = {}

    def __getitem__(self, item):
        if item not in self.childs:
            # setdefault использовать нельзя, так как Task при создании коннектится к storage
            self.childs[item] = Task(self, item)
        return self.childs[item]

    def __iadd__(self, interval: Interval):
        if self.intervals and self.running:
            raise RuntimeError("Предыдущий интервал не завершён, но добавляется следующий")
        self.intervals.append(interval)
        return self

    def start(self, modif: Time = None):
        self.__iadd__(Interval(modif))

    def stop(self, modif: Time = None):
        self.last_interval.stop(modif)

    def find_running(self):
        if self.running:
            return self

        for child in self.childs.values():
            found = child.find_running()
            if found:
                return found

        return None

    @property
    def last_interval(self) -> Union[Interval, None]:
        if not self.intervals:
            raise TMException("Задача ни разу не запускалась!")

        return self.intervals[-1]

    @property
    def running(self):
        if not self.intervals:
            return False

        i = self.intervals[-1]
        if not i:
            return False
        if i.end is None:
            return True
        return False

    def save(self) -> dict:
        return {
            'name': self.name,
            'description': self.decsription,
            'intervals': [i.save() for i in self.intervals],
            'childs': [c.save() for c in self.childs.values()]
        }

    @classmethod
    def load(cls, raw_data: dict, parent: "Task" = None) -> "Task":
        t = Task(parent, raw_data['name'])
        t.decsription = raw_data['description']
        for i_r in raw_data['intervals']:
            i = Interval.load(i_r)
            t += i

        for c_r in raw_data['childs']:
            # Добавляется автоматически
            cls.load(c_r, t)

        return t

    @property
    def hours(self):
        return reduce(
            lambda x, _i: x + ((_i.end or time()) - _i.start),
            self.intervals,
            0
        )

    @property
    def hours_all(self):
        return self.hours + sum(map(lambda x: x.hours_all, self.childs.values()))

    def __str__(self):
        return f"{self.name}: \tFull: {Time(self.hours_all):.1f} \tThis: {Time(self.hours):.1f}"


class Storage:
    FILENAME = "data.json"

    def __init__(self):
        self.root = self._load()
        self.cur = self.root

    @property
    def dir(self):
        return self.cur.path

    def rm(self, path):
        obj = self[path]
        if obj == self.root:
            raise TMException("Нельзя удалить безделье, алё")
        name = obj.name

        del obj.parent.childs[obj.name]

        return self._rm(obj)

    def _rm(self, obj: Task):
        count, tm = 0, 0
        for child in obj.childs.values():
            _c, _= self._rm(child)
            count += _c
        # Переносим интервалы в родительскую папку
        pi = obj.parent.intervals
        # TODO: Сделать сортировку
        if pi:
            last = pi.pop()
        else:
            last = None
        pi += obj.intervals
        if last: pi.append(last)

        hours = obj.hours
        del obj
        return count + 1, hours

    def save(self):
        print("Saving: ", end="")
        d = self.root.save()
        json.dump(d, open(self.FILENAME, "wt"), indent=2)
        print('Ok')

    def _load(self):
        print(f"Load data from `{self.FILENAME}`: ", end='')
        try:
            d = json.load(open(self.FILENAME, "rt"))
            print("Ok")
            return Task.load(d)
        except Exception as e:
            print("Error")
            print(f"Couldn't load datafile: {e}")
            print("Create new data")
            return Task(None, "/")

    def __getitem__(self, path: str):
        if not path:  # ``
            return self.cur

        if path[0] == "/":
            obj = self.root
            path = path[1:]
        else:
            obj = self.cur
            while path.startswith("../"):
                path = path[3:]
                obj = obj.parent
                if obj is None:
                    raise TMException("Невозможно перейти выше корня")

        if path == "":
            return obj

        for name in path.split("/"):
            name = name.strip()

            if not name:
                raise ValueError("Имя задачи не может быть пустым")
            obj = obj[name]

        return obj

    def change_dir(self, path: str):
        self.cur = self[path]


# ======= MAIN CYCLE ========


class TimeManager:
    def __init__(self):
        self._running = True
        self.s = Storage()

        self._funcs = {
            attr: getattr(self, attr)
            for attr
            in self.__dir__()
            if not attr.startswith("_") and callable(getattr(self, attr))
        }
        del self._funcs['run']

        self._task: Task = self.s.root.find_running()
        if self._task is None:
            self._unclassified()

    def _unclassified(self):
        self._task: Task = self.s.root
        self._task += Interval()

    def test(self, *args):
        print("Test function")
        print(f"Arguments: {args}")
    test.description = "Just test function"

    def start(self, path="", modif=None):

        self._task.stop(modif)

        self._task = self.s[path]
        self._task.start(modif)

        self.s.save()
        self.status()

    start.description = "Start a new task, use `start` `path` `modifier`"

    def stop(self, modif=None):
        self._task.stop(modif)

        self._unclassified()
        self.s.save()
        self.status()
    stop.description = "Stop current task"

    def ls(self, path=""):
        task = self.s[path]

        print(task)
        for task in task.childs.values():
            print(f"  {task}")

    def rm(self, path=""):
        print("Удаляю... ", end="")
        count, tm = self.s.rm(path)
        print(f"{count} объектов и {tm:.1f} времени")
        self.s.save()

    def status(self):
        if self._task == self.s.root:
            print("Unclassified: ", end='')
        else:
            print("Task       :", end='')
        print(f" {self._task}")
        print(f"Interval   : {self._task.last_interval}")

    def cd(self, path: str):
        self.s.change_dir(path)

    def exit(self):
        print("Bye!")
        self._running = False
        self.s.save()

    def _incorrect_name(self, func_name, *args):
        print(f"{func_name} not found in this scope.")
        print("Existing names:")
        for name, func in self._funcs.items():
            description = getattr(func, "description", "")
            print(f"  `{name}`: {description}")

    def run(self):
        while self._running:
            try:
                self._cycle()
            except TMException as tme:
                print_exc()
                print(tme)

    def _cycle(self):
        a = input(f"{self.s.dir}> ", )
        if not a:
            return
        f_name, *args = self._split_tokens(a)
        func = self._funcs.get(
            f_name,
            lambda *args: self._incorrect_name(f_name, *args)
        )
        func(*args)
        print()

    def _split_tokens(self, raw: str):
        return [word for word in raw.split(" ") if word]


tm = TimeManager()
tm.run()
