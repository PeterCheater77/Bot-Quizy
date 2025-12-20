#importowanie bibliotek i funkcji
from datetime import datetime, timedelta
from discord import Interaction, Embed, Color
from dotenv import load_dotenv
from functools import wraps
from os import getenv
from random import choice
from sqlite3 import connect, OperationalError, Error
from threading import RLock
from time import time
from traceback import print_exc
from zoneinfo import ZoneInfo

import state as st

######################################################################################

#pobieranie tokenu bota
load_dotenv("token.env")
TOKEN = getenv("DISCORD_TOKEN")

######################################################################################

#tworzenie bazy danych
conn = connect('quiz.db', check_same_thread=False)
c = conn.cursor()
c.execute('''
CREATE TABLE IF NOT EXISTS quiz_data (
user_id INTEGER PRIMARY KEY,
points INTEGER DEFAULT 0,
marathon_record INTEGER DEFAULT 0,
speedrun_record INTEGER DEFAULT 0,
risk_uses INTEGER DEFAULT 0,
played_quizzes INTEGER DEFAULT 0,
daily_streak INTEGER DEFAULT 0,
last_daily TEXT DEFAULT NULL)''')

sql_lock = RLock()

try:
    conn.commit()
except OperationalError:
    pass


#zabezpieczenie funkcji działających na bazie danych
def sqlite_safe(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        with sql_lock:
            try:
                return func(*args, **kwargs)
            except Error as e:
                print(f"[BŁĄD] Funkcja {func.__name__} nie powiodła się: {e}")
                print_exc()
                raise
    return wrapper

#zapobieganie zbyt wielu akcjom na bazie danych
def get_cursor():
    return conn.cursor()


#obsługa cooldownów
def global_cooldown(seconds: int = 3):
    def decorator(func):
        @wraps(func)
        async def wrapper(interaction: Interaction, *args, **kwargs):
            key = (interaction.user.id, interaction.guild.id)
            now = time()
            last_used = st.cooldowns.get(key, 0)

            #cooldown jest aktywny
            if now - last_used < seconds:
                wait_time = seconds - (now - last_used)
                embed = Embed(
                    description=f"⏳ Poczekaj {wait_time:.1f}s przed ponownym użyciem komendy!",
                    color=Color.from_str("#961212"))
                return await interaction.response.send_message(embed=embed, ephemeral=True)

            #zapis użycia komendy
            st.cooldowns[key] = now

            #wywołanie właściwej funkcji
            return await func(interaction, *args, **kwargs)

        return wrapper
    return decorator


#pobieranie wybranej wartości z bazy danych
@sqlite_safe
def get_value(user_id: int, column: str, default: int = 0):
    allowed_columns = ["points", "marathon_record", "speedrun_record", "risk_uses", "played_quizzes", "daily_streak", "last_daily"]

    #zapobieganie sprawdzaniu nieistniejących wartości
    if column not in allowed_columns:
        raise ValueError("Nieprawidłowa kolumna")

    cur = get_cursor()
    cur.execute(f"SELECT {column} FROM quiz_data WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    return row[0] if row else default


#dodawanie i odejmowanie lub modyfikowanie wybranej wartości z bazy danych
@sqlite_safe
def set_value(user_id: int, points: int = 0, marathon_record: int = 0, speedrun_record: int = 0, risk_uses: int = 0,
              played_quizzes: int = 0, daily_streak: int = 0, last_daily: str = None):

    cur = get_cursor()
    cur.execute("""
            INSERT INTO quiz_data (user_id, points, marathon_record, speedrun_record, risk_uses, played_quizzes, daily_streak, last_daily) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                points = MAX(0, points + excluded.points),
                marathon_record = MAX(marathon_record, excluded.marathon_record),
                speedrun_record = MAX(speedrun_record, excluded.speedrun_record),
                risk_uses = MAX(0, risk_uses + excluded.risk_uses),
                played_quizzes = MAX(0, played_quizzes + excluded.played_quizzes),
                daily_streak = excluded.daily_streak,
                last_daily = excluded.last_daily
            """, (user_id, points, marathon_record, speedrun_record, risk_uses, played_quizzes, daily_streak, last_daily))
    conn.commit()


#resetowanie ilości gier w trybie ryzyka, w które gracz zagrał
@sqlite_safe
def reset_risk_uses():
    cur = get_cursor()
    cur.execute("UPDATE quiz_data SET risk_uses = 0")
    conn.commit()


#pobranie obecnego czasu dla pytania dziennego
def get_today():
    return datetime.now(ZoneInfo("Europe/Warsaw")).date()


#pobieranie rankingu top 5 najlepszych graczy według punktów rankingowych, rekordu maratonu quizowego i rekordu speedrunu quizowego
@sqlite_safe
def get_top(column: str):
    allowed_columns = ["points", "marathon_record", "speedrun_record", "played_quizzes"]

    #zapobieganie sprawdzaniu nieistniejących wartości
    if column not in allowed_columns:
        raise ValueError("Nieprawidłowa kolumna")

    cur = get_cursor()
    cur.execute(f"SELECT user_id, {column} FROM quiz_data ORDER BY {column} DESC LIMIT 5")
    return cur.fetchall()


#pobieranie pytań z plików txt
def load_questions(file):
    questions = []
    try:
        with open(file, encoding="utf-8") as f:
            for line in f:
                if "|" not in line:
                    continue
                parts = line.strip().split("|", 1)

                question, answer = parts
                questions.append((question.strip(), answer.strip().lower() == "true"))

    #plik nie istnieje lub ma niepoprawną nazwę
    except FileNotFoundError:
        print(f"[BŁĄD] Nie znaleziono pliku: {file}")
    return questions

questions_programming = load_questions("questions/programming.txt")
questions_history = load_questions("questions/history.txt")
questions_geography = load_questions("questions/geography.txt")
questions_science = load_questions("questions/science.txt")
questions_math = load_questions("questions/math.txt")
questions_arts = load_questions("questions/arts.txt")
questions_sports = load_questions("questions/sports.txt")


#losowanie pytania i kategorii
def random_question(category: list = None):
    #kategoria pytania nie została podana
    if category is None:
        category = choice([
            questions_programming,
            questions_history,
            questions_geography,
            questions_science,
            questions_math,
            questions_arts,
            questions_sports])

    question, correct_answer = choice(category)
    return question, correct_answer


#podłączanie kategorii pytań do opcji wybranej przez gracza
def set_category(chosen_category: str):
    #lista wszystkich kategorii
    categories_list = {
        "programming": ("Programowanie", questions_programming),
        "math": ("Matematyka", questions_math),
        "science": ("Nauki Ścisłe", questions_science),
        "geography": ("Geografia", questions_geography),
        "history": ("Historia", questions_history),
        "arts": ("Sztuka", questions_arts),
        "sports": ("Sport", questions_sports)}

    #wybrana kategoria nie istnieje
    if chosen_category not in categories_list:
        correct_answer = None
        return correct_answer, Embed(
            description="⛔ Nieznana kategoria!",
            color=Color.from_str("#961212"))


    #losowanie i wysyłanie pytania
    name, category = categories_list[chosen_category]
    question, correct_answer = random_question(category)

    return correct_answer, Embed(
        title=f"🧐 **Pytanie z kategorii: {name}**",
        description=f"{question}\n\n"
                    f"Kliknij odpowiedź poniżej:",
        color=Color.from_str("#ffdd00"))


#jedno losowe pytanie dzienne
def daily_question(user_id: int):
    today = get_today()
    daily_streak = get_value(user_id, "daily_streak")
    last_daily_str = get_value(user_id, "last_daily")

    #zamienianie last_daily z tekstu w datę
    if last_daily_str is not None:
        last_daily = datetime.fromisoformat(last_daily_str).date()
    else:
        last_daily = None

    #gracz już odpowiedział na dzisiejsze pytanie
    if last_daily == today:
        return None, None, None, Embed(
            description=f"⛔ Już odebrałeś dzisiaj pytanie dzienne! Twoja passą aktywności: **{daily_streak} dni**.",
            color=Color.from_str("#961212"))

    #gracz ma już aktywną passę
    elif last_daily == today - timedelta(days=1):
        daily_streak += 1
    #gracz nie ma żadnej aktywnej passy
    else:
        daily_streak = 1

    #losowanie pytania dziennego
    question, correct_answer = random_question()
    return question, correct_answer, daily_streak, Embed(
        title="🗓️ Pytanie dzienne",
        description=f"{question}\n\n"
                    f"Kliknij odpowiedź poniżej:",
        color=Color.from_str("#ffdd00"))


#pobieranie danych quizowych gracza
@sqlite_safe
def get_player_info(user_id: int, user_name: str, color: Color):
    cur = get_cursor()
    cur.execute("SELECT points, marathon_record, speedrun_record, played_quizzes, daily_streak FROM quiz_data WHERE user_id = ?", (user_id,))
    row = cur.fetchone()

    #dane gracza istnieją
    if row:
        points = row[0]
        marathon_record = row[1]
        speedrun_record = row[2]
        played_quizzes = row[3]
        daily_streak = row[4]

    #dane gracza nie istnieją
    else:
        points = 0
        marathon_record = 0
        speedrun_record = 0
        played_quizzes = 0
        daily_streak = 0

    return Embed(
        title=f"📊 Dane quizowe użytkownika **{user_name}**:",
        description=f"Punkty rankingowe: **{points} punktów**\n"
                    f"Rekord maratonu quizowego: **{marathon_record} poziomów**\n"
                    f"Rekord speedrunu quizowego: **{speedrun_record} poprawnych odpowiedzi**\n"
                    f"Liczba zagranych quizów: **{played_quizzes}**\n"
                    f"Aktualna passa odbierania pytania dziennego: **{daily_streak} dni**",
        color=color)


#modyfikowanie rankingu wybranego gracza
@sqlite_safe
def ranking_embed():
    #pobieranie rankingu top 5 z wszystkich kategorii
    points = get_top("points")
    marathon = get_top("marathon_record")
    speedrun = get_top("speedrun_record")
    quizzes = get_top("played_quizzes")

    long_line = "»»------------------------------------------------------------««"

    #punkty rankingowe
    filtered_points = [r for r in points if r[1] > 0]
    if filtered_points:
        top_ranked = "\n".join([
            f"{long_line}\n**{i + 1}.** ||<@{r[0]}> - {r[1]} punktów||"
            for i, r in enumerate(filtered_points)])
    else:
        top_ranked = f"{long_line}\nBrak danych..."

    #rekordy maratonu quizowego
    filtered_marathon = [r for r in marathon if r[1] > 0]
    if filtered_marathon:
        top_marathon = "\n".join([
            f"{long_line}\n**{i + 1}.** ||<@{r[0]}> - {r[1]} poziomów||"
            for i, r in enumerate(filtered_marathon)])
    else:
        top_marathon = f"{long_line}\nBrak danych..."

    #rekordy speedrunu quizowego
    filtered_speedrun = [r for r in speedrun if r[1] > 0]
    if filtered_speedrun:
        top_speedrun = "\n".join([
            f"{long_line}\n**{i + 1}.** ||<@{r[0]}> - {r[1]} poprawnych odpowiedzi||"
            for i, r in enumerate(filtered_speedrun)])
    else:
        top_speedrun = f"{long_line}\nBrak danych..."

    #liczby zagranych quizów
    filtered_quizzes = [r for r in quizzes if r[1] > 0]
    if filtered_quizzes:
        top_quizzes = "\n".join([
            f"{long_line}\n**{i + 1}.** ||<@{r[0]}> - {r[1]}||"
            for i, r in enumerate(filtered_quizzes)])
    else:
        top_quizzes = f"{long_line}\nBrak danych..."

    return Embed(
        title="**🏆 Ranking Top 5:**",
        description=f"**💎 Punkty rankingowe:**\n"
                    f"{top_ranked}\n"
                    f"{long_line}\n\n"
                    f"**📈 Rekord maratonu:**\n"
                    f"{top_marathon}\n"
                    f"{long_line}\n\n"
                    f"**⏳ Rekord speedrunu:**\n"
                    f"{top_speedrun}\n"
                    f"{long_line}\n\n"
                    f"**📑 Liczba zagranych quizów:**\n"
                    f"{top_quizzes}\n"
                    f"{long_line}",
        color=Color.gold())


#modyfikowanie rankingu wybranego gracza
@sqlite_safe
def set_ranking(user_id: int, points_value: int = None, marathon_value: int = None,
                speedrun_value: int = None,quizzes_value: int = None):

    #pobieranie starego rankingu gracza przed aktualizacją wartości
    old_points = get_value(user_id, "points")
    old_marathon = get_value(user_id, "marathon_record")
    old_speedrun = get_value(user_id, "speedrun_record")
    old_quizzes = get_value(user_id, "played_quizzes")

    #sprawdzanie, czy użytkownik istnieje w bazie
    cur = get_cursor()
    cur.execute("SELECT * FROM quiz_data WHERE user_id = ?", (user_id,))
    if cur.fetchone() is None:
        return None, Embed(
            description=f"⛔ Nie możesz zmienić rankingu tego użytkownika, ponieważ nie istnieje on jeszcze w bazie danych!",
            color=Color.from_str("#961212")), None

    #gracz nie wpisał żadnej wartości
    if points_value is None and marathon_value is None and speedrun_value is None and quizzes_value is None:
        return "nothing", Embed(
            description=f"⛔ Musisz podać przynajmniej jedną wartość do zmiany!",
            color=Color.from_str("#961212")), None

    #modyfikowanie konkretnej kolumny
    updates = {
        "points": points_value,
        "marathon_record": marathon_value,
        "speedrun_record": speedrun_value,
        "played_quizzes": quizzes_value}

    for column, value in updates.items():
        if value is not None:
            cur.execute(f"UPDATE quiz_data SET {column} = ? WHERE user_id = ?", (max(value, 0), user_id))

    conn.commit()

    return (
        {k: v for k, v in
         {"Punkty rankingowe": points_value,
         "Rekord maratonu quizowego": marathon_value,
         "Rekord speedrunu quizowego": speedrun_value,
         "Liczba zagranych quizów": quizzes_value}.items() if v is not None},
        None,
        {"Punkty rankingowe": old_points,
         "Rekord maratonu quizowego": old_marathon,
         "Rekord speedrunu quizowego": old_speedrun,
         "Liczba zagranych quizów": old_quizzes})


#pobieranie opisów komend z plików txt
def load_help_texts(file):
    try:
        with open(file, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"[BŁĄD] Nie znaleziono pliku: {file}")


#wysyłanie embedów dla /pomoc
def help_embed(help_value: str, command_name: str):
    #pobieranie opisów komend
    help_all = load_help_texts("help_texts/all.txt")
    help_quiz = load_help_texts("help_texts/quiz.txt")
    help_category_question = load_help_texts("help_texts/category_question.txt")
    help_daily_question = load_help_texts("help_texts/daily_question.txt")
    help_player_info = load_help_texts("help_texts/player_info.txt")
    help_ranking = load_help_texts("help_texts/ranking.txt")
    help_set_ranking = load_help_texts("help_texts/set_ranking.txt")
    help_server_quiz = load_help_texts("help_texts/server_quiz.txt")
    help_server_quiz_stop = load_help_texts("help_texts/server_quiz_stop.txt")

    command_choices = ""

    #gracz nie wybrał żadnej komendy
    if help_value is None:
        return Embed(
            title="**Lista komend i ich opis:**",
            description=help_all,
            color=Color.from_str("#a8ffd9"))

    #podłączanie opisów komend do opcji wybranej przez gracza
    if help_value == "quiz":
        help_text = help_quiz
        command_choices = " [tryb]"

    elif help_value == "category_question":
        help_text = help_category_question
        command_choices = " [kategoria]"

    elif help_value == "daily_question":
        help_text = help_daily_question

    elif help_value == "player_info":
        help_text = help_player_info
        command_choices = " [użytkownik]"

    elif help_value == "ranking":
        help_text = help_ranking

    elif help_value == "set_ranking":
        help_text = help_set_ranking
        command_choices = " [użytkownik] [opcja i wartość]"

    elif help_value == "server_quiz":
        help_text = help_server_quiz

    elif help_value == "server_quiz_stop":
        help_text = help_server_quiz_stop

    #komenda nie istnieje
    else:
        return Embed(
        description="⚠️ Nie znaleziono komendy!",
        color=Color.from_str("#961212"))

    return Embed(
        title=f"**Komenda {command_name}{command_choices}**:",
        description=help_text,
        color=Color.from_str("#1fff9d"))