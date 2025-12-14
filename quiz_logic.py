#importowanie bibliotek, funkcji i widoków
from discord import Interaction, Embed, Color, AllowedMentions
from asyncio import create_task, sleep

from views import RankedQuizView, MarathonQuizView, SpeedrunQuizView, RiskQuizView, RiskQuizBetsView, ServerQuizView
from functions import random_question, get_value, set_value
import state as st

######################################################################################

#rozpoczynanie wybranego rodzaju quizu (rankingowy/maraton/speedrun/tryb ryzyka)
async def quiz_start(interaction: Interaction, chosen_mode: str):
    #gracz ma już aktywny quizó
    if st.active_quizzes.get(interaction.user.id, False):
        embed = Embed(
            description=f"⛔ Masz już aktywny quiz! Poczekaj aż się zakończy lub zamknij go.",
            color=Color.from_str("#961212"))
        return await interaction.response.send_message(embed=embed, ephemeral=True)

    st.active_quizzes[interaction.user.id] = True

    #podłączanie rodzaju quizu do opcji wybranej przez gracza
    if chosen_mode == "ranked":
        set_value(interaction.user.id, played_quizzes=+1)
        return await ranked_quiz(interaction)

    elif chosen_mode == "marathon":
        set_value(interaction.user.id, played_quizzes=+1)
        return await marathon_quiz(interaction)

    elif chosen_mode == "speedrun":
        set_value(interaction.user.id, played_quizzes=+1)
        return await speedrun_quiz(interaction)

    elif chosen_mode == "risk":
        return await risk_quiz_bets(interaction)

    #wybrany rodzaj quizu nie istnieje
    else:
        embed = Embed(
            description="⛔ Nieznany rodzaj quizu!",
            color=Color.from_str("#961212"))
        return await interaction.response.send_message(embed=embed, ephemeral=True)



#quiz rankingowy
async def ranked_quiz(interaction: Interaction):
    st.user_streaks[interaction.user.id] = 0
    embed = Embed(
        description="**Quiz rankingowy** za chwilę się rozpocznie!\nSkłada się z 10 pytań, z których na każde masz równo 10 sekund.\nZebrane punkty zapisują się pod /ranking.\nPrzygotuj się!",
        color=Color.from_str("#ff7b00"))
    await interaction.response.send_message(embed=embed, ephemeral=True)
    await sleep(5)

    #losowanie i wysyłanie pytania
    for i in range(10):
        question, correct_answer = random_question()
        embed = Embed(
            title=f"🤔 **Pytanie {i+1}/10**",
            description=f"{question}\n\n"
                        f"Kliknij odpowiedź poniżej (masz 10 sekund):",
            color=Color.from_str("#ffb900"))
        await interaction.followup.send(embed=embed, view=RankedQuizView(correct_answer, interaction), ephemeral=True)
        await sleep(10.05)

    #podsumowanie punktów na końcu quizu rankingowego
    total_points = get_value(interaction.user.id, "points")
    embed = Embed(
        description=f"**»»----------------------------------------------------------------------««**"
                    f"\n\nTwój quiz dobiegł końca! Twoja łączna liczba punktów wynosi: **{total_points}**\n\n"
                    f"**»»----------------------------------------------------------------------««**",
        color=Color.from_str("#e8742c"))
    await interaction.followup.send(embed=embed, ephemeral=True)
    st.active_quizzes[interaction.user.id] = False



#maraton quizowy
async def marathon_quiz(interaction: Interaction):
    embed = Embed(
        description="**Maraton quizowy** za chwilę się rozpocznie!\nOdpowiadaj tak długo, aż się pomylisz!\nMasz 15 sekund na każdą odpowiedź.\nPrzygotuj się!",
        color=Color.from_str("#3160ad"))
    await interaction.response.send_message(embed=embed, ephemeral=True)
    await sleep(5)
    await next_marathon_question(interaction, 1)


#przechodzenie do kolejnego poziomu maratonu quizowego
async def next_marathon_question(interaction: Interaction, wave: int):
    #losowanie i wysyłanie pytania
    question, correct_answer = random_question()
    embed = Embed(
        title=f"🤔 **Pytanie {wave}**",
        description=f"{question}\n\n"
                    f"Kliknij odpowiedź poniżej (masz 15 sekund):",
        color=Color.from_str("#ffb900"))
    await interaction.followup.send(embed=embed, view=MarathonQuizView(correct_answer, interaction, wave), ephemeral=True)



#speedrun quizowy
async def speedrun_quiz(interaction: Interaction):
    embed = Embed(
        description="**Speedrun quizowy** za chwilę się rozpocznie!\nMasz 60 sekund, aby odpowiedzieć na jak najwięcej pytań!\nPrzygotuj się!",
        color=Color.from_str("#b587ff"))
    await interaction.response.send_message(embed=embed, ephemeral=True)
    await sleep(5)
    speedrun_data = {"score": 0, "time_left": 60}

    #odliczanie czasu
    async def countdown():
        while speedrun_data["time_left"] > 0:
            await sleep(1)
            speedrun_data["time_left"] -= 1

        #koniec speedrunu
        st.active_quizzes[interaction.user.id] = False
        speedrun_data["question_active"] = False
        old_record = get_value(interaction.user.id, "speedrun_record")

        #gracz pobił swój rekord
        if speedrun_data['score'] > old_record:
            set_value(interaction.user.id, speedrun_record=speedrun_data['score'])
            embed = Embed(
                title="⏰ Czas minął!",
                description=f"🎉 Pobiłeś/aś swój poprzedni rekord poprawnych odpowiedzi: **{old_record}**, osiągając **{speedrun_data['score']}**!",
                color=Color.from_str("#8851c9"))

        #gracz nie pobił swojego rekordu
        else:
            embed = Embed(
                title="⏰ Czas minął!",
                description=f"Twój wynik: **{speedrun_data['score']}** poprawnych odpowiedzi.\n"
                            f"Twój rekord to nadal: **{old_record}**",
                color=Color.from_str("#5f3491"))

        await interaction.followup.send(embed=embed, ephemeral=True)

    create_task(countdown())
    await next_speedrun_question(interaction, speedrun_data)


#przechodzenie do kolejnego pytania speedrunu quizowego
async def next_speedrun_question(interaction: Interaction, speedrun_data: dict):
    if speedrun_data["time_left"] <= 0 or not st.active_quizzes.get(interaction.user.id, False):
        return

    if speedrun_data.get("question_active", False):
        return

    #losowanie i wysyłanie pytania
    question, correct_answer = random_question()
    speedrun_data["question_active"] = True
    embed = Embed(
        title=f"⏳ Speedrun quizowy - pozostało **{speedrun_data['time_left']}s**",
        description=f"{question}\n\n"
                    f"Kliknij odpowiedź poniżej:",
        color=Color.from_str("#ffb900"))
    await interaction.followup.send(embed=embed, view=SpeedrunQuizView(correct_answer, interaction, speedrun_data), ephemeral=True)



#wybieranie zakładu trybu ryzyka
async def risk_quiz_bets(interaction: Interaction):
    risk_uses = get_value(interaction.user.id, "risk_uses")

    #graczowi skończył się limit gier na godzinę
    if risk_uses >= 3:
        embed = Embed(
            description="⛔ Możesz zagrać tylko **3 razy w ciągu godziny** w tryb ryzyka!\n"
                        "Poczekaj aż twój licznik gier się zresetuje.",
            color=Color.from_str("#961212"))
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        embed = Embed(
            title="🎯 Tryb ryzyka",
            description=f"Ile punktów rankingowych chcesz obstawić?\n\n"
                        f"Jeśli choć raz się pomylisz – **tracisz tyle ile obstawiłeś**.\n"
                        f"Jeśli odpowiesz na wszystkie 10 pytań poprawnie – wygrywasz!\n\n"
                        f"Ilość pozostałych gier w trybie ryzyka: {3-risk_uses}",
            color=Color.from_str("#f03043"))
        return await interaction.response.send_message(embed=embed, view=RiskQuizBetsView(interaction), ephemeral=True)


#tryb ryzyka
async def risk_quiz(interaction: Interaction, bet: int):
    set_value(interaction.user.id, played_quizzes=+1)
    set_value(interaction.user.id, risk_uses=+1)
    risk_data = {"correct_count": 0, "active": True}

    #losowanie i wysyłanie pytania
    for i in range(10):
        question, answer = random_question()
        embed = Embed(
            title=f"🎯 Tryb ryzyka - pytanie {i + 1}/10",
            description=f"{question}\n\n"
                        f"Kliknij odpowiedź poniżej (masz 10 sekund):",
            color=Color.from_str("#ffb900"))
        await interaction.followup.send(embed=embed, view=RiskQuizView(answer, interaction, bet, risk_data), ephemeral=True)
        await sleep(10)

        if not st.active_quizzes.get(interaction.user.id, False) or not risk_data["active"]:
            return

    #gracz wygrał zakład
    if risk_data["correct_count"] == 10:
        set_value(interaction.user.id, points=+bet)
        st.active_quizzes[interaction.user.id] = False
        embed = Embed(
            title="🥳 Gratulacje!",
            description=f"Odpowiedziałeś/aś poprawnie na 10 pytań!\nWygrywasz: **{bet} punktów rankingowych**.",
            color=Color.from_str("#9fff5e"))
        await interaction.followup.send(embed=embed, ephemeral=True)



#quiz serwerowy
async def server_quiz(interaction: Interaction):
    #jeżeli włączanie quizu serwerowego nie jest zablokowane
    if st.server_quiz_allowed:
        st.local_scores.clear()

        #jeżeli użytkownik próbuje wystartować quiz serwerowy na złym kanale
        if interaction.channel.id != 1436475920952070335:
            embed = Embed(
                description=f"⛔ Quiz serwerowy można włączać tylko na kanale do tego przeznaczonym: **#quizy-serwerowe**",
                color=Color.from_str("#961212"))
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        embed1 = Embed(
            description=f"Pomyślnie wystartowano quiz serwerowy!",
            color=Color.from_str("#7df0ec"))

        embed2 = Embed(
            description=f"@everyone **Quiz serwerowy za chwilę się rozpocznie!**\nSkłada się z 10 pytań, z których na każde macie 15 sekund.\nPrzygotujcie się!",
            color=Color.from_str("#159995"))
        await interaction.response.send_message(embed=embed1, ephemeral=True)
        await interaction.channel.send(allowed_mentions=AllowedMentions(everyone=True), embed=embed2, delete_after=15)
        await sleep(10)

        #losowanie i wysyłanie pytania
        for i in range(10):
            if st.server_quiz_allowed:
                question, correct_answer = random_question()
                answered_users = set()
                embed = Embed(
                    title=f"🤔 **Pytanie {i+1}/10**",
                    description=f"{question}\n\n"
                                f"Kliknij odpowiedź poniżej (masz 15 sekund):",
                    color=Color.from_str("#ffb900"))
                await interaction.channel.send(embed=embed, view=ServerQuizView(correct_answer, interaction, answered_users), delete_after=15)
                await sleep(15)

            #jeżeli quiz został zatrzymany
            else:
                embed = Embed(
                    description="@everyone Quiz serwerowy został zatrzymany.\n"
                                "Przepraszamy za komplikacje.",
                    color=Color.from_str("#ff2626"))
                return await interaction.channel.send(allowed_mentions=AllowedMentions(everyone=True), embed=embed, delete_after=15)

        #ranking końcowy quizu serwerowego
        if st.local_scores:
            sorted_scores = sorted(st.local_scores.items(), key=lambda x: x[1], reverse=True)
            top = sorted_scores[:10]
            embed = Embed(
                title="🏆 **Wyniki quizu serwerowego:**",
                description="\n".join([f"**{i+1}.** <@{uid}> — {points} pkt" for i, (uid, points) in enumerate(top)]),
                color=Color.from_str("#23dbc3"))

        #nikt nie zabrał udziału w quizie lub nie odpowiedział poprawnie
        else:
            embed = Embed(
                description="Nikt nie odpowiedział poprawnie na żadne pytanie...",
                color=Color.from_str("#c9103f"))
        return await interaction.channel.send(embed=embed, delete_after=120)

    #jeżeli wystartowanie quizu zostało zatrzymane
    else:
        embed = Embed(
            description="⛔ Nie możesz aktywować nowego quizu serwerowego, ponieważ ta funkcja jest aktualnie blokowana. Poczekaj do 15 sekund i spróbuj ponownie.",
            color=Color.from_str("#961212"))
        return await interaction.response.send_message(embed=embed, ephemeral=True)