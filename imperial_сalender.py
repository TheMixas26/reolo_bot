from quickjs import Context


class ImperialCalendar:
    def __init__(self, js_path: str):
        self.ctx = Context()

        with open(js_path, 'r', encoding="utf-8") as f:
            js_code = f.read()
        self.ctx.eval(js_code)

        # проверяем, что библиотека доступна
        self.ctx.eval("""
            if (typeof ImperialCalendar === "undefined") {
                throw new Error("ImperialCalendar is not defined in JS context");
            }
        """)

    # --- базовый доступ к API ---

    def _api(self):
        return self.ctx.eval(
            "ImperialCalendar({}, { format: 'iso' })"
        )

    # --- публичные методы ---

    def today(self) -> dict:
        """
        Полная информация о текущей имперской дате
        """
        return self._api()

    def short(self) -> str:
        """
        Короткий формат даты
        """
        return self.ctx.eval(
            "ImperialCalendar({}, { format: 'short' })"
        )

    def full(self) -> str:
        """
        Полный формат даты (строкой)
        """
        return self.ctx.eval(
            "ImperialCalendar({}, { format: 'full' })"
        )

    def event_today(self):
        """
        Название праздника сегодня или None
        """
        api = self._api()
        return api["event"] if "event" in api else None

    def next_events(self, n: int = 1):
        """
        Ближайшие n праздников
        """
        return self.ctx.eval(f"""
            (() => {{
                const api = ImperialCalendar({{}}, {{ format: 'iso' }});
                return api.nextEvents(
                    {{
                        day: api.day,
                        monthIndex: api.monthIndex,
                        year: api.year
                    }},
                    {n}
                );
            }})()
        """)

    def all_events_with_countdown(self):
        """
        Все праздники с количеством дней до них
        """
        return self.ctx.eval("""
            (() => {
                const api = ImperialCalendar({}, { format: 'iso' });
                return api.getEventsWithCountdown({
                    day: api.day,
                    monthIndex: api.monthIndex,
                    year: api.year
                });
            })()
        """)

    def compare(self, a: dict, b: dict) -> int:
        """
        Сравнение двух имперских дат
        """
        return self.ctx.eval(f"""
            (() => {{
                const api = ImperialCalendar({{}}, {{ format: 'iso' }});
                return api.compareImperialDates(
                    {a},
                    {b}
                );
            }})()
        """)
