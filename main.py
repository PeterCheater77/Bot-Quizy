#importowanie bibliotek, funkcji i widoków
from asyncio import create_task, sleep
from discord import app_commands as command, Client, Intents, Interaction, Embed, Color, Member, errors

from quiz_logic import quiz_start, server_quiz
from views import CategoryQuestionView, DailyQuestionView
from functions import (TOKEN, global_cooldown, reset_risk_uses, set_category, daily_question, ranking_embed, set_ranking,
                       get_player_info, help_embed)
import state as st

######################################################################################

#ustawienia bota
class AClient(Client):
    def __init__(self):
        intents = Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.synced = False

    #włączanie bota
    async def on_ready(self):
        await tree.sync()
        self.synced = True
        print(f"Zalogowano jako {self.user}")
        st.cooldowns = {}

        #resetowanie użyć tryb ryzyka przez graczy
        if hasattr(client, "risk_task_started"):
            return

        client.risk_task_started = True
        create_task(reset_risk_uses_loop())

client = AClient()
tree = command.CommandTree(client)
Choice = command.Choice


#resetowanie co godzinę limitu quizów ryzyka (3/godzinę)
async def reset_risk_uses_loop():
    await client.wait_until_ready()
    while not client.is_closed():
        await sleep(3600)
        reset_risk_uses()

######################################################################################

#wybieranie rodzaju quizu (rankingowy/maraton/speedrun/ryzyko)
@tree.command(name="quiz", description="Startuje wybrany przez Ciebie quiz")
@command.describe(tryb="Wybierz tryb quizowy")
@command.choices(tryb=[
    Choice(name="🏆 Rankingowy", value="ranked"),
    Choice(name="📈 Maraton", value="marathon"),
    Choice(name="⏳ Speedrun", value="speedrun"),
    Choice(name="🔥 Ryzyko", value="risk")])
@global_cooldown()

async def quiz(interaction: Interaction, tryb: Choice[str]):
    chosen_mode = tryb.value
    await quiz_start(interaction, chosen_mode)


#quiz serwerowy
@tree.command(name="quiz-serwerowy", description="Rozpoczyna quiz dla wszystkich użytkowników serwera")
@command.default_permissions(manage_guild=True)
@global_cooldown(5)

async def server_quiz_command(interaction: Interaction):
    await server_quiz(interaction)


#jedno losowe pytanie z wybranej kategorii
@tree.command(name="pytanie-kategoria",
              description="Dostajesz jedno pytanie, widoczne tylko dla Ciebie z wybranej kategorii (bez punktów rankingowych)")
@command.describe(kategoria="Wybierz kategorię pytania")
@command.choices(kategoria=[
    Choice(name="💻 Programowanie", value="programming"),
    Choice(name="📐 Matematyka", value="math"),
    Choice(name="🔬 Nauki Ścisłe", value="science"),
    Choice(name="🗺️ Geografia", value="geography"),
    Choice(name="🏰 Historia", value="history"),
    Choice(name="🎨 Sztuka", value="arts"),
    Choice(name="⚽ Sport", value="sports")])
@global_cooldown()

async def category_question(interaction: Interaction, kategoria: Choice[str]):
    chosen_category = kategoria.value
    correct_answer, embed = set_category(chosen_category)

    if correct_answer is None:
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, view=CategoryQuestionView(correct_answer, interaction), ephemeral=True)
        return None


#jedno losowe pytanie dzienne
@tree.command(name="pytanie-dzienne",
              description="Odpowiedz na jedno pytanie każdego dnia, aby zwiększać swoją passę i zdobywać punkty rankingowe")
@global_cooldown()

async def daily_question_command(interaction: Interaction):
    user_id = interaction.user.id

    question, correct_answer, daily_streak, embed = daily_question(user_id)

    if question is None and correct_answer is None and daily_streak is None:
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, view=DailyQuestionView(correct_answer, interaction, daily_streak), ephemeral=True)

######################################################################################

#ranking punktów graczy
@tree.command(name="ranking", description="Wyświetla 5 najlepszych graczy z czterech kategorii według rankingu")
@global_cooldown()

async def ranking(interaction: Interaction):
    embed = ranking_embed()
    await interaction.response.send_message(embed=embed, ephemeral=True)


#modyfikowanie rankingu wybranego gracza
@tree.command(name="ranking-ustaw", description="Zmienia cały ranking wybranego użytkownika na wartości, które wybierzesz")
@command.describe(uzytkownik="Wybierz użytkownika, którego ranking chcesz zmienić",
                  punkty="Wartość punktów rankingowych",
                  rekord_maratonu="Wartość rekordu maratonu quizowego",
                  rekord_speedrunu="Wartość rekordu speedrunu quizowego",
                  zagrane_quizy="Ilość zagranych przez użytkownika quizów")
@command.default_permissions(manage_guild=True)
@global_cooldown()

async def set_ranking_command(interaction: Interaction, uzytkownik: Member,
                      punkty: int = None, rekord_maratonu: int = None, rekord_speedrunu: int = None, zagrane_quizy: int = None):

    changes, embed, old_values = set_ranking(
        user_id=uzytkownik.id,
        points_value=punkty,
        marathon_value=rekord_maratonu,
        speedrun_value=rekord_speedrunu,
        quizzes_value=zagrane_quizy)

    #gracz nie istnieje w bazie lub użytkownik, używający komendy, nie wpisał żadnej wartości
    if changes is None or changes == "nothing":
        return await interaction.response.send_message(embed=embed, ephemeral=True)

    #wysyłanie wiadomości o modyfikacji rankingu
    else:
        changes_text = "\n".join(f"• {key}: **{old_values[key]}** → **{value}**" for key, value in changes.items())
        embed = Embed(
            title=f"📄 Zmodyfikowano ranking użytkownika **{uzytkownik.display_name}**:",
            description=f"{changes_text}",
            color=Color.from_str("#ffffff"))
        return await interaction.response.send_message(embed=embed, ephemeral=True)


#zatrzymywanie quizu serwerowego
@tree.command(name="quiz-serwerowy-stop",
              description="Zatrzymuje wszystkie aktywne quizy serwerowe i uniemożliwia startowanie nowych przez 15 sekund")
@command.default_permissions(manage_guild=True)
@global_cooldown()

async def server_quiz_stop(interaction: Interaction):
    st.server_quiz_allowed = False
    embed = Embed(
        description="Pomyślnie zatrzymano wszystkie aktywne quizy serwerowe.",
        color=Color.from_str("#961212"))
    await interaction.response.send_message(embed=embed, ephemeral=True)
    await sleep(15)
    st.server_quiz_allowed = True


#informacje quizowe wybranego gracza
@tree.command(name="gracz-info", description="Pokazuje dane quizowe wybranego użytkownika")
@command.describe(uzytkownik="Wybierz użytkownika, którego dane chcesz zobaczyć")
@global_cooldown()

async def player_info(interaction: Interaction, uzytkownik: Member):
    user_id = uzytkownik.id

    #kolor wiadomości ustawia się na kolor najwyższej roli użytkownika
    if uzytkownik.top_role.color.value != 0:
        color = uzytkownik.top_role.color

    #kolor wiadomości ustawia się na domyślny jeśli gracz nie ma roli
    else:
        color = Color.from_str("#737373")

    embed = get_player_info(user_id, user_name=uzytkownik.display_name, color=color)
    embed.set_thumbnail(url=uzytkownik.avatar.url if uzytkownik.avatar else uzytkownik.default_avatar.url)
    await interaction.response.send_message(embed=embed, ephemeral=True)


#informacje na temat wszystkich komend lub wybranej komendy
@tree.command(name="pomoc", description="Pokazuje informacje o wszystkich komendach lub o wybranej komendzie")
@command.describe(komenda="Wybierz komendę, o której chcesz się czegoś dowiedzieć")
@command.choices(komenda=[
    Choice(name="/quiz", value="quiz"),
    Choice(name="/pytanie-kategoria", value="category_question"),
    Choice(name="/pytanie-dzienne", value="daily_question"),
    Choice(name="/gracz-info", value="player_info"),
    Choice(name="/ranking", value="ranking"),
    Choice(name="/ranking-ustaw", value="set_ranking"),
    Choice(name="/quiz-serwerowy", value="server_quiz"),
    Choice(name="/quiz-serwerowy-stop", value="server_quiz_stop")])
@global_cooldown()

async def help_command(interaction: Interaction, komenda: Choice[str] = None):
    help_value = komenda.value if komenda else None
    command_name = komenda.name if komenda else None

    embed = help_embed(help_value, command_name)
    await interaction.response.send_message(embed=embed, ephemeral=True)

######################################################################################

#błędy
@tree.error
async def on_app_command_error(interaction: Interaction, error: command.AppCommandError):
    try:
        await interaction.response.send_message(f"⚠️ Wystąpił błąd: {error}", ephemeral=True)
    except errors.InteractionResponded:
        await interaction.followup.send(f"⚠️ Wystąpił błąd: {error}", ephemeral=True)


#uruchamianie bota (token w pliku token.env)
client.run(TOKEN)