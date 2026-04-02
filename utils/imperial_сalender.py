import json
import threading
from quickjs import Context
from posting.models import Platform
from posting.services import PostFactory, PostFormatter


class ImperialCalendar:
    def __init__(self, js_path: str):
        self.ctx = Context()
        self._lock = threading.Lock()

        with open(js_path, 'r', encoding="utf-8") as f:
            js_code = f.read()
        self.ctx.eval(js_code)

        # проверяем, что библиотека доступна
        self.ctx.eval("""
            if (typeof ImperialCalendar === "undefined") {
                throw new Error("ImperialCalendar is not defined in JS context");
            }
        """)

    # --- internal helpers ---

    def _eval_json(self, js_expression: str) -> dict:
        """
        Evaluate a JavaScript expression and return its value as a native
        Python object by JSON-serializing in the JS context.
        """
        with self._lock:
            json_str = self.ctx.eval(f"JSON.stringify({js_expression})")
        return json.loads(json_str)

    # --- базовый доступ к API ---

    def _api(self):
        with self._lock:
            return self.ctx.eval(
                "ImperialCalendar({ format: 'iso' })"
            )

    # --- публичные методы ---

    def today(self) -> dict:
        """
        Полная информация о текущей имперской дате (как словарь).
        """
        return self._eval_json("ImperialCalendar({ format: 'iso' })")

    def short(self) -> str:
        """
        Короткий формат даты
        """
        with self._lock:
            return self.ctx.eval(
                "ImperialCalendar({ format: 'short' })"
            )

    def full(self) -> str:
        """
        Полный формат даты (строкой)
        """
        with self._lock:
            return self.ctx.eval(
                "ImperialCalendar({ format: 'full' })"
            )

    def event_today(self) -> str | None:
        """
        Название праздника сегодня или None
        """
        api = self.today()
        return api.get("event")

    def next_events(self, n: int = 1) -> list:
        """
        Ближайшие n праздников
        """
        return self._eval_json(f"""
            (() => {{
                const api = ImperialCalendar({{ format: 'iso' }});
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

    def all_events_with_countdown(self) -> list:
        """
        Все праздники с количеством дней до них
        """
        return self._eval_json("""
            (() => {
                const api = ImperialCalendar({ format: 'iso' });
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
        with self._lock:
            return self.ctx.eval(f"""
                (() => {{
                    const api = ImperialCalendar({ format: 'iso' });
                    return api.compareImperialDates(
                        {a},
                        {b}
                    );
                }})()
            """)




def check_imperial_events():
    from config import calendar, channel
    today_info = calendar.today()
    event_today = today_info.get("event")
    if event_today:
        message = f"Сегодня {today_info['day']} {today_info['month']} {today_info['year']} по Имперскому календарю! Праздник: {event_today} 🎉"
    else:
        message = f"Сегодня {today_info['day']} {today_info['month']} {today_info['year']} по Имперскому календарю. Сегодня нет праздников."

    from posting.runtime import post_publisher

    post = PostFactory.create_system_post(
        platform=Platform.TELEGRAM,
        destination_id=channel,
        text=message,
        display_name="Имперский календарь",
    )
    post_publisher.publish_post(
        post,
        rendered_text=PostFormatter.compose_publish_text(post),
        disable_notification=True,
    )
