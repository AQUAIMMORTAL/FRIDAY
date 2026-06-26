import webbrowser
from urllib.parse import quote_plus


def weather_action(parameters: dict, **_) -> str:
    city = parameters.get("city", "").strip()
    when = parameters.get("time", "today").strip() or "today"

    if not city:
        return "City is missing for the weather report."

    query = f"weather in {city} {when}"
    url   = f"https://www.google.com/search?q={quote_plus(query)}"

    try:
        webbrowser.open(url)
    except Exception as e:
        return f"Couldn't open the browser for weather: {e}"

    return f"Showing weather for {city}, {when}."