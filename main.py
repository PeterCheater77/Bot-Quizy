import discord
import sqlite3
import asyncio
import os
from discord import app_commands
from random import choice
from dotenv import load_dotenv



#pobieranie tokenu bota
load_dotenv("token.env")
TOKEN = os.getenv("DISCORD_TOKEN")


#zmienne i dzienniki
user_streaks = {}
local_scores = {}
active_quizes = {}
server_quiz_mode = True



#pobieranie pytań z plików txt
def load_questions(file):
    questions = []
    try:
        with open(file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or "|" not in line:
                    continue
                question, answer = line.split("|", 1)
                answer_bool = answer.strip().lower() == "true"
                questions.append((question.strip(), answer_bool))
    #plik nie istnieje
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



#tworzenie bazy danych
conn = sqlite3.connect('quiz.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS points (user_id INTEGER PRIMARY KEY, points INTEGER DEFAULT 0, waves INTEGER DEFAULT 0)''')
try:
    conn.commit()
except sqlite3.OperationalError:
    pass


#pobieranie ilości punktów rankingowych z bazy danych
def get_points(user_id: int) -> int:
    c.execute("SELECT points FROM points WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    return row[0] if row else 0

#dodawanie punktów
def add_point(user_id: int):
    c.execute("INSERT OR IGNORE INTO points (user_id, points, waves) VALUES (?, 0, 0)", (user_id,))
    c.execute("UPDATE points SET points = points + 1 WHERE user_id = ?", (user_id,))
    conn.commit()

#odejmowanie punktów
def remove_point(user_id: int):
    c.execute("INSERT OR IGNORE INTO points (user_id, points, waves) VALUES (?, 0, 0)", (user_id,))
    c.execute("UPDATE points SET points = CASE WHEN points > 0 THEN points - 1 ELSE 0 END WHERE user_id = ?", (user_id,))
    conn.commit()

#pobieranie ilości poziomów maratonu quizowego z bazy danych
def get_waves(user_id: int) -> int:
    c.execute("SELECT waves FROM points WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    return row[0] if row else 0

#ustawianie graczowi rekordu poziomów maratonu quizowego
def set_waves(user_id: int, value: int):
    c.execute("SELECT waves FROM points WHERE user_id = ?", (user_id,))
    row = c.fetchone()

    #jeśli rekord nie istnieje
    if row is None:
        c.execute("INSERT INTO points (user_id, points, waves) VALUES (?, 0, ?, 0)", (user_id, value))
        conn.commit()
        return

    record = row[0] if row[0] is not None else 0
    #jeśli gracz pobił swój rekord
    if value > record:
        c.execute("UPDATE points SET waves = ? WHERE user_id = ?", (value, user_id))
        conn.commit()



#przyciski - quiz rankingowy i pytanie z wybranej kategorii
class buttons(discord.ui.View):
    def __init__(self, correct_answer: bool, user_id: int, count_points: bool = True):
        super().__init__(timeout=10)
        self.correct_answer = correct_answer
        self.user_id = user_id
        self.answered = False
        self.count_points = count_points

    #przycisk prawda
    @discord.ui.button(label="Prawda", style=discord.ButtonStyle.green)
    async def true_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_answer(interaction, True)

    #przycisk fałsz
    @discord.ui.button(label="Fałsz", style=discord.ButtonStyle.red)
    async def false_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_answer(interaction, False)

    #odpowiedź na kliknięcie przycisku prawda lub fałsz
    async def handle_answer(self, interaction: discord.Interaction, chosen_answer: bool):
        #gracz odpowiedział już na dane pytanie
        if self.answered:
            embed = discord.Embed(description="⛔ Już odpowiedziałeś/aś na to pytanie!",
                                color=discord.Color.from_str("#de043b"))
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        self.answered = True

        #gracz odpowiedział poprawnie
        if chosen_answer == self.correct_answer:
            #gra rankingowa
            if self.count_points:
                user_streaks[self.user_id] = user_streaks.get(self.user_id, 0) + 1
                add_point(interaction.user.id)
                bonus_text = ""
                #dodawanie punktu za bonus 3 poprawne odpowiedzi pod rząd
                if user_streaks[self.user_id] == 3:
                    add_point(interaction.user.id)
                    bonus_text = "\n\n🔥 Bonus +1 punkt za 3 poprawne odpowiedzi z rzędu!"
                    user_streaks[self.user_id] = 0

                points = get_points(interaction.user.id)
                embed = discord.Embed(description=f"✅ Poprawna odpowiedź!{bonus_text}\nTwoja liczba punktów: **{points}**",
                                      color=discord.Color.from_str("#22c716"))
            #gra nierankigowa
            else:
                embed = discord.Embed(description=f"✅ Poprawna odpowiedź!\n\n"
                                                  f"(Bez punktów rankingowych)",
                                      color=discord.Color.from_str("#22c716"))

            await interaction.response.edit_message(embed=embed, view=None)

        #gracz odpowiedział niepoprawnie
        else:
            # gra rankingowa
            if self.count_points:
                user_streaks[self.user_id] = 0
                remove_point(interaction.user.id)
                embed = discord.Embed(description=f"❌ Niestety jest to zła odpowiedź!\n\n-1 punkt",
                                      color=discord.Color.from_str("#c71616"))
            # gra nierankigowa
            else:
                embed = discord.Embed(description=f"❌ Niestety jest to zła odpowiedź!\n\n"
                                                  f"(Nie tracisz punktów)",
                                      color=discord.Color.from_str("#c71616"))

            await interaction.response.edit_message(embed=embed, view=None)



#ustawienia bota
class aclient(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.synced = False


    #włączanie bota
    async def on_ready(self):
        await tree.sync(guild=discord.Object(id=1350416675761029121))
        self.synced = True
        print(f"Zalogowano jako: {self.user}")

client = aclient()
tree = app_commands.CommandTree(client)



#quiz rankingowy
@tree.command(guild=discord.Object(id=1350416675761029121), name='quiz', description='Rozpoczyna quiz rankingowy')
async def quiz(interaction: discord.Interaction):
    if active_quizes.get(interaction.user.id, False):
        embed = discord.Embed(description="Masz już aktywny quiz! Poczekaj aż się zakończy.",
                              color=discord.Color.from_str("#961212"))

        return await interaction.response.send_message(embed=embed, ephemeral=True)

    active_quizes[interaction.user.id] = True

    user_streaks[interaction.user.id] = 0
    embed = discord.Embed(
        description="Quiz za chwilę się rozpocznie! Składa się z 10 pytań, z których na każde masz równo 10 sekund. Przygotuj się!",
        color=discord.Color.from_str("#26d7ff"))

    await interaction.response.send_message(embed=embed, ephemeral=True)
    await asyncio.sleep(5)

    #losowanie i wysyłanie pytania
    for i in range(10):
        category = choice([questions_programming, questions_history, questions_geography, questions_science, questions_math, questions_arts, questions_sports])
        question, correct_answer = choice(category)

        embed = discord.Embed(title=f"🤔 **Pytanie {i+1}/10**",
                          description=f"{question}\n\nKliknij odpowiedź poniżej (masz 10 sekund):",
                          color=discord.Color.from_str("#ffb900"))

        await interaction.followup.send(embed=embed, view=buttons(correct_answer,interaction.user.id, True), ephemeral=True)
        await asyncio.sleep(10)

    #podsumowanie punktów na końcu
    total_points = get_points(interaction.user.id)
    embed = discord.Embed(
        description=f"**»»--------------------------------------------------------------------««**"
        f"\nTwój quiz dobiegł końca! Twoja łączna liczba punktów wynosi: **{total_points}**\n"
        f"**»»--------------------------------------------------------------------««**",
        color=discord.Color.from_str("#ff8000"))

    await interaction.followup.send(embed=embed, ephemeral=True)
    active_quizes[interaction.user.id] = False



#jedno losowe pytanie z wybranej kategorii
@tree.command(guild=discord.Object(id=1350416675761029121), name="pytanie-kategoria", description="Daje ci jedno pytanie z wybranej kategorii (bez punktów rankingowych)")
@app_commands.describe(kategoria="Wybierz kategorię pytania")
@app_commands.choices(kategoria=[
    app_commands.Choice(name="💻 Programowanie", value="programming"),
    app_commands.Choice(name="🏰 Historia", value="history"),
    app_commands.Choice(name="🗺️ Geografia", value="geography"),
    app_commands.Choice(name="🔬 Nauki ścisłe", value="science"),
    app_commands.Choice(name="📐 Matematyka", value="math"),
    app_commands.Choice(name="🎨 Sztuka", value="arts"),
    app_commands.Choice(name="⚽ Sport", value="sports")])

async def category_quiz(interaction: discord.Interaction, kategoria: app_commands.Choice[str]):
    #podłączanie kategorii pytań do wybranych opcji przez gracza
    if kategoria.value == "programming":
        category = questions_programming
        category_name = "Programowanie"

    elif kategoria.value == "history":
        category = questions_history
        category_name = "Historia"

    elif kategoria.value == "geography":
        category = questions_geography
        category_name = "Geografia"

    elif kategoria.value == "science":
        category = questions_science
        category_name = "Nauka"

    elif kategoria.value == "math":
        category = questions_math
        category_name = "Matematyka"

    elif kategoria.value == "arts":
        category = questions_arts
        category_name = "Sztuka"

    elif kategoria.value == "sports":
        category = questions_sports
        category_name = "Sport"

    #wybrana kategoria nie istnieje
    else:
        embed = discord.Embed(
            description="Nieznana kategoria!",
            color=discord.Color.from_str("#961212"))
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    #losowanie i wysyłanie pytania
    question, correct_answer = choice(category)

    embed = discord.Embed(
        title=f"🤔 **Pytanie z kategorii: {category_name}**",
        description=f"{question}\n\nKliknij odpowiedź poniżej:",
        color=discord.Color.from_str("#ffdd00"))

    await interaction.response.send_message(embed=embed, view=buttons(correct_answer, interaction.user.id, False), ephemeral=True)



#quiz serwerowy - przyciski
class server_quiz_view(discord.ui.View):
    def __init__(self, correct_answer: bool, answered_users: set, local_scores: dict):
        super().__init__(timeout=15)
        self.correct_answer = correct_answer
        self.answered_users = answered_users
        self.local_scores = local_scores

    #przycisk prawda
    @discord.ui.button(label="Prawda", style=discord.ButtonStyle.green)
    async def true_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_answer(interaction, True)

    #przycisk fałsz
    @discord.ui.button(label="Fałsz", style=discord.ButtonStyle.red)
    async def false_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_answer(interaction, False)

    #odpowiedź na kliknięcie przycisku prawda lub fałsz
    async def handle_answer(self, interaction: discord.Interaction, chosen_answer: bool):
        #gracz odpowiedział już na dane pytanie
        if interaction.user.id in self.answered_users:
            embed = discord.Embed(description="⛔ Już odpowiedziałeś/aś na to pytanie!",
                                color=discord.Color.from_str("#de043b"))
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        self.answered_users.add(interaction.user.id)

        #gracz odpowiedział poprawnie
        if chosen_answer == self.correct_answer:
            self.local_scores[interaction.user.id] = self.local_scores.get(interaction.user.id, 0) + 1
            embed = discord.Embed(description=f"✅ Poprawna odpowiedź!",
                                  color=discord.Color.from_str("#22c716"))

        #gracz odpowiedział niepoprawnie
        else:
            embed = discord.Embed(description=f"❌ Niestety jest to zła odpowiedź!",
                                  color=discord.Color.from_str("#c71616"))

        await interaction.response.send_message(embed=embed, ephemeral=True)


#quiz serwerowy
@tree.command(guild=discord.Object(id=1350416675761029121), name="quiz-serwerowy", description="Rozpoczyna quiz dla wszystkich użytkowników serwera")
@app_commands.default_permissions(manage_guild=True)
async def server_quiz(interaction: discord.Interaction):
    if server_quiz_mode == True:
        local_scores.clear()
        embed = discord.Embed(
            description=f"@everyone **Quiz serwerowy za chwilę się rozpocznie!**\nSkłada się z 10 pytań, z których na każde masz 15 sekund.\nPrzygotuj się!",
            color=discord.Color.from_str("#2679ff"))

        await interaction.response.send_message(allowed_mentions=discord.AllowedMentions(everyone=True), embed=embed, delete_after=15)
        await asyncio.sleep(10)

        #losowanie i wysyłanie pytania
        for i in range(10):
            if server_quiz_mode == True:
                category = choice([questions_programming, questions_history, questions_geography, questions_science, questions_math, questions_arts, questions_sports])
                question, correct_answer = choice(category)

                embed = discord.Embed(
                    title=f"🤔 **Pytanie {i+1}/10**",
                    description=f"{question}\n\nKliknij odpowiedź poniżej (masz 15 sekund):",
                    color=discord.Color.from_str("#ffb900"))

                answered_users = set()
                view = server_quiz_view(correct_answer, answered_users, local_scores)
                await interaction.channel.send(embed=embed, view=view, delete_after=15)
                await asyncio.sleep(15)

            #jeśli quiz został zatrzymany
            else:
                embed = discord.Embed(
                    description="@everyone Quiz serwerowy został zatrzymany.\n"
                                "Przepraszamy za komplikacje.",
                    color=discord.Color.from_str("#ff2626"))
                return await interaction.channel.send(allowed_mentions=discord.AllowedMentions(everyone=True), embed=embed, delete_after=15)


        #ranking końcowy
        if local_scores:
            sorted_scores = sorted(local_scores.items(), key=lambda x: x[1], reverse=True)
            top = sorted_scores[:10]

            embed = discord.Embed(
                title="🏆 **Wyniki quizu serwerowego:**",
                description="\n".join(
                [f"**{i+1}.** <@{uid}> — {points} pkt" for i, (uid, points) in enumerate(top)]),
                color=discord.Color.gold())

        #nikt nie zabrał udziału w quizie lub nie odpowiedział poprawnie
        else:
            embed = discord.Embed(
                description="Nikt nie odpowiedział poprawnie na żadne pytanie...",
                    color=discord.Color.from_str("#961212"))

        await interaction.channel.send(embed=embed, delete_after=120)

    #jeśli wystartowanie quizu został o zatrzymane
    else:
        embed = discord.Embed(
            description="⛔ Nie możesz aktywować nowego quizu serwerowego, ponieważ ta funkcja jest aktualnie blokowana. Poczekaj do 15 sekund i spróbuj ponownie.",
            color=discord.Color.from_str("#961212"))
        return await interaction.response.send_message(embed=embed, ephemeral=True)



#zatrzymywanie quizu serwerowego
@tree.command(guild=discord.Object(id=1350416675761029121), name="quiz-serwerowy-stop", description="Zatrzymuje wszystkie aktywne quizy serwerowe")
@app_commands.default_permissions(manage_guild=True)
async def server_quiz_stop(interaction: discord.Interaction):
    global server_quiz_mode
    server_quiz_mode = False
    embed = discord.Embed(
        description="Pomyślnie zatrzymano wszystkie aktywne quizy serwerowe.",
        color=discord.Color.from_str("#961212"))

    await interaction.response.send_message(embed=embed, ephemeral=True)
    await asyncio.sleep(15)
    server_quiz_mode = True



#maraton quizowy - przyciski
class marathon_quiz_view(discord.ui.View):
    def __init__(self, correct_answer: bool, interaction: discord.Interaction, current_wave: int):
        super().__init__(timeout=15)
        self.correct_answer = correct_answer
        self.interaction = interaction
        self.user = interaction.user
        self.current_wave = current_wave
        self.answered = False


    #gracz nie zdążył odpowiedzieć w ciągu wyznaczonego czasu
    async def on_timeout(self):
        if self.answered:
            return

        active_quizes[self.user.id] = False
        old_record = get_waves(self.user.id)
        #gracz pobił swój rekord
        if (self.current_wave - 1) > old_record:
            set_waves(self.user.id, self.current_wave - 1)
            embed = discord.Embed(
                title="⏰ Czas minął!",
                description=f"Nie odpowiedziałeś/aś w ciągu 15 sekund!\n"
                            f"🎉 Pobiłeś swój poprzedni rekord poziomów: **{old_record}**, osiągając **{self.current_wave - 1}**!",
                color=discord.Color.from_str("#343d91"))
        #gracz nie pobił swojego rekordu
        else:
            embed = discord.Embed(
                title="⏰ Czas minął!",
                description=f"Nie odpowiedziałeś/aś w ciągu 15 sekund!\n"
                            f"Twój wynik: **{self.current_wave - 1}** poziomów.\n"
                            f"Twój rekord to nadal **{old_record}**.",
                color=discord.Color.from_str("#159c9e"))

        await self.interaction.followup.send(embed=embed, ephemeral=True)
        self.stop()


    #przycisk prawda
    @discord.ui.button(label="Prawda", style=discord.ButtonStyle.green)
    async def true_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_answer(interaction, True)

    #przycisk fałsz
    @discord.ui.button(label="Fałsz", style=discord.ButtonStyle.red)
    async def false_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_answer(interaction, False)

    #odpowiedź na kliknięcie przycisku prawda lub fałsz
    async def handle_answer(self, interaction: discord.Interaction, chosen_answer: bool):
        #gracz odpowiedział już na dane pytanie
        if self.answered:
            embed = discord.Embed(description="⛔ Już odpowiedziałeś/aś na to pytanie!",
                                color=discord.Color.from_str("#de043b"))
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        self.answered = True

        #gracz odpowiedział poprawnie
        if chosen_answer == self.correct_answer:
            embed = discord.Embed(
                description=f"✅ Poprawna odpowiedź!\n\nPrzechodzisz do **poziomu {self.current_wave + 1}**!",
                color=discord.Color.from_str("#22c716"))

            #różne progi poziomów
            if self.current_wave in (10, 20, 40, 60, 80):
                embed = discord.Embed(
                    description=f"✅ Poprawna odpowiedź!\n\nPrzechodzisz do **poziomu {self.current_wave + 1}**!\n\n"
                                f"🎉 Pokonałeś/aś już **{self.current_wave}** poziomów, tak trzymaj!",
                    color=discord.Color.from_str("#cdff42"))

            #easter egg - po osiągnięciu 100 poziomu dostajesz rangę "mistrz quizów"
            elif self.current_wave == 100:
                embed = discord.Embed(
                    description=f"✅ Poprawna odpowiedź!\n\n"
                                f"💀 Pokonałeś/aś już **100** poziomów! 💀\n"
                                f"W nagrodę dostajesz rangę **mistrz quizów**!\n",
                    color=discord.Color.from_str("#fffb00"))
                master_role = self.interaction.guild.get_role(1441141637831987372)
                await self.user.add_roles(master_role, reason="Nagroda za pokonanie 100 poziomów w quizie")

            await interaction.response.edit_message(embed=embed, view=None)
            self.stop()
            await asyncio.sleep(2)
            await next_marathon_question(self.interaction, self.current_wave + 1)

        #gracz odpowiedział niepoprawnie
        else:
            active_quizes[self.user.id] = False
            old_record = get_waves(self.user.id)
            #gracz pobił swój rekord
            if (self.current_wave - 1) > old_record:
                set_waves(self.user.id, self.current_wave - 1)
                embed = discord.Embed(
                    title="❌ Niestety jest to zła odpowiedź!",
                    description=f"🎉 Pobiłeś/aś swój poprzedni rekord poziomów: **{old_record}**, osiągając **{self.current_wave - 1}**!",
                    color=discord.Color.from_str("#fc6565"))
            #gracz nie pobił swojego rekordu
            else:
                embed = discord.Embed(
                    title="❌ Niestety jest to zła odpowiedź!",
                    description=f"Twój wynik: **{self.current_wave - 1}** poziomów.\n"
                                f"Twój rekord to nadal **{old_record}**.",
                    color=discord.Color.from_str("#c71616"))

            await interaction.response.edit_message(embed=embed, view=None)
            self.stop()


#przechodzenie do kolejnego poziomu po poprawnej odpowiedzi
async def next_marathon_question(interaction: discord.Interaction, wave: int):
    #losowanie i wysyłanie pytania
    category = choice([questions_programming, questions_history, questions_geography, questions_science, questions_math, questions_arts, questions_sports])
    question, correct_answer = choice(category)

    embed = discord.Embed(
        title=f"🤔 **Pytanie {wave}**",
        description=f"{question}\n\nKliknij odpowiedź poniżej (masz 15 sekund):",
        color=discord.Color.from_str("#ffb900"))

    view = marathon_quiz_view(correct_answer, interaction, wave)
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)

#maraton quizowy
@tree.command(guild=discord.Object(id=1350416675761029121), name='quiz-maraton', description='Rozpoczyna maraton quizowy')
async def marathon_quiz(interaction: discord.Interaction):
    if active_quizes.get(interaction.user.id, False):
        embed = discord.Embed(description="Masz już aktywny quiz! Poczekaj aż się zakończy.",
                            color=discord.Color.from_str("#961212"))

        return await interaction.response.send_message(embed=embed, ephemeral=True)

    active_quizes[interaction.user.id] = True

    embed = discord.Embed(
        description="Maraton quizowy za chwilę się rozpocznie! Odpowiadaj tak długo, aż się pomylisz!\nMasz 15 sekund na każdą odpowiedź.\nPrzygotuj się!",
        color=discord.Color.from_str("#3160ad"))

    await interaction.response.send_message(embed=embed, ephemeral=True)
    await asyncio.sleep(5)
    await next_marathon_question(interaction, 1)



#speedrun quizowy
class speedrun_quiz_view(discord.ui.View):
    def __init__(self, correct_answer: bool, speedrun_data: dict, interaction: discord.Interaction):
        super().__init__(timeout=8)
        self.correct_answer = correct_answer
        self.data = speedrun_data
        self.interaction = interaction
        self.answered = False

    async def handle_answer(self, interaction: discord.Interaction, chosen: bool):
        if self.data["time_left"] <= 0:
            return

        if self.answered:
            embed = discord.Embed(description="⛔ Już odpowiedziałeś/aś na to pytanie!",
                                  color=discord.Color.from_str("#de043b"))

            return await interaction.response.send_message(embed=embed, ephemeral=True)

        self.answered = True

        if chosen == self.correct_answer:
            self.data["score"] += 1
            embed = discord.Embed(description=f"✅ Poprawna odpowiedź!",
                                  color=discord.Color.from_str("#22c716"))
        else:
            embed = discord.Embed(description=f"❌ Niestety jest to zła odpowiedź!",
                                  color=discord.Color.from_str("#c71616"))

        await interaction.response.edit_message(embed=embed, view=None)
        await asyncio.sleep(0.2)
        await next_speedrun_question(self.interaction, self.data)


    @discord.ui.button(label="Prawda", style=discord.ButtonStyle.green)
    async def true_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_answer(interaction, True)

    @discord.ui.button(label="Fałsz", style=discord.ButtonStyle.red)
    async def false_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_answer(interaction, False)


async def next_speedrun_question(interaction: discord.Interaction, speedrun_data: dict):
    if speedrun_data["time_left"] <= 0:
        return

    category = choice([questions_programming, questions_history, questions_geography, questions_science, questions_math, questions_arts, questions_sports])
    question, answer = choice(category)

    embed = discord.Embed(
        title=f"⏳ Speedrun quizowy - pozostało **{speedrun_data['time_left']}s**",
        description=f"{question}\n\nKliknij odpowiedź poniżej:",
        color=discord.Color.from_str("#ffb900"))

    view = speedrun_quiz_view(answer, speedrun_data, interaction)
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)


@tree.command(guild=discord.Object(id=1350416675761029121), name="quiz-speedrun", description="Rozpoczyna speedrun quizowy")
async def quiz_speedrun(interaction: discord.Interaction):
    if active_quizes.get(interaction.user.id, False):
        embed = discord.Embed(
            description="Masz już aktywny quiz! Poczekaj aż się zakończy.",
            color=discord.Color.from_str("#961212"))

        return await interaction.response.send_message(embed=embed, ephemeral=True)

    active_quizes[interaction.user.id] = True
    embed = discord.Embed(
        description="Speedrun quizowy za chwilę się rozpocznie!\nMasz 60 sekund, aby odpowiedzieć na jak najwięcej pytań!\nPrzygotuj się!",
        color=discord.Color.from_str("#7aceff"))

    await interaction.response.send_message(embed=embed, ephemeral=True)
    await asyncio.sleep(5)

    # dane speedrunu
    speedrun_data = {"score": 0, "time_left": 60}

    # odpalenie odliczania czasu
    async def countdown():
        while speedrun_data["time_left"] > 0:
            await asyncio.sleep(1)
            speedrun_data["time_left"] -= 1

        # koniec speedrunu
        active_quizes[interaction.user.id] = False
        embed = discord.Embed(
            title="⏰ Czas minął!",
            description=f"Twój wynik: **{speedrun_data['score']} poprawnych odpowiedzi!**",
            color=discord.Color.from_str("#159c9e"))

        await interaction.followup.send(embed=embed, ephemeral=True)

    asyncio.create_task(countdown())
    await next_speedrun_question(interaction, speedrun_data)



#ranking punktów graczy
@tree.command(guild=discord.Object(id=1350416675761029121), name="ranking", description="Pokazuje ranking graczy")
async def ranking(interaction: discord.Interaction):
    c.execute("SELECT user_id, points FROM points ORDER BY points DESC LIMIT 5")
    rows = c.fetchall()

    #jeśli nie ma żadnych graczy w bazie
    if not rows:
        embed = discord.Embed(
            description="Brak danych w rankingu!",
            color=discord.Color.from_str("#961212"))
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    #wysyłanie wiadomości z rankingiem
    top_ranked = "\n".join(
        [f"»»-----------------------------«« \n **{i+1}.** ||<@{r[0]}> — {r[1]} pkt||" for i, r in enumerate(rows)])

    embed = discord.Embed(title="**🏆 Ranking Top 5:**",
                          description=top_ranked,
                          color=discord.Color.gold())
    await interaction.response.send_message(embed=embed, ephemeral=True)



#resetowanie rankingu wybranego gracza
@tree.command(guild=discord.Object(id=1350416675761029121), name="ranking-reset", description="Resetuje cały ranking wybranego użytkownika")
@app_commands.describe(uzytkownik="Wybierz użytkownika, którego ranking chcesz zresetować")
@app_commands.default_permissions(manage_guild=True)
async def ranking_reset(interaction: discord.Interaction, uzytkownik: discord.Member):
    user_id = uzytkownik.id

    #sprawdzenie, czy użytkownik istnieje w bazie
    c.execute("SELECT * FROM points WHERE user_id = ?", (user_id,))
    if c.fetchone() is None:
        embed = discord.Embed(description=f"Użytkownik {uzytkownik.mention} nie ma żadnych punktów rankingowych.",
                            color=discord.Color.from_str("#961212"))
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    #reset punktów
    c.execute("UPDATE points SET points = 0, waves = 0 WHERE user_id = ?", (user_id,))
    conn.commit()

    embed = discord.Embed(description=f"Punkty i rekord maratonu quizowego użytkownika {uzytkownik.mention} zostały zresetowane.",
                          color=discord.Color.from_str("#ff5c5c"))
    await interaction.response.send_message(embed=embed, ephemeral=True)



#informacje na temat bota
@tree.command(guild=discord.Object(id=1350416675761029121), name="info", description="Pokazuje wszystkie informacje na temat bota")
async def info(interaction: discord.Interaction):
    embed = discord.Embed(
        title="**🤖 Informacje:**",
        description=f"**Nazwa bota:** Bot Quizy\n"
                    f"**Opis:** Bot Discord zajmujący się działaniem quizów z wiedzy ogólnej na serwerze.\n\n"
                    f"**Komendy:**\n"
                    f"• */info* - pokazuje informacje, które właśnie widzisz\n\n"
                    f"• */quiz* - startuje quiz, widoczny tylko dla Ciebie. Składa się z 10 pytań, z których na każde masz 10 sekund. Twój wynik zapisuje się do ogólnej puli punktów.\n\n"
                    f"• */quiz-kategoria* - daje jedno pytanie, widoczne tylko dla Ciebie z wybranej przez kategorii, ale punkty się nie zapisują.\n\n"
                    f"• */quiz-maraton* - startuje quiz, widoczny tylko dla Ciebie, który składa się z nieskończonej liczby pytań, ana każde masz 15 sekund. Grasz tak długo, aż się pomylisz.\n\n"
                    f"• */quiz-speedrun* - startuje quiz, widoczny tylko dla Ciebie, w którym masz 60 sekund, aby odpowiedzieć na jak najwięcej pytań..\n\n"
                    f"• */ranking* - wyświetla ranking 5 najlepszych graczy z największą ilością punktów rankingowych (zdobytych z /quiz).\n\n"
                    f"• */ranking-reset* - usuwa wszystkie punkty rankingowe wybranego gracza (komenda tylko dla administratorów).\n\n"
                    f"• */quiz-serwerowy* - rozpoczyna quiz dla wszystkich użytkowników serwera, który składa się z 10 pytań, z których na każde masz 15 sekund. Zebrane punkty nie zapisują się, ale są widoczne w mini-rankingu na końcu quizu. (komenda tylko dla administratorów)\n\n"
                    f"• */quiz-serwerowy-stop* - zatrzymuje wszystkie aktywne quizy serwerowe i uniemożliwia startowanie nowych przez 15 sekund (komenda tylko dla administratorów)\n\n",
        color=discord.Color.from_str("#a8ffd9"))

    await interaction.response.send_message(embed=embed, ephemeral=True)



#błędy
@tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    await interaction.response.send_message(f"⚠️ Wystąpił błąd: {error}", ephemeral=True)


#uruchamianie bota (token w osobnym pliku)
client.run(TOKEN)
