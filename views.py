#importowanie bibliotek i funkcji
from discord import Interaction, Embed, Color, ui, ButtonStyle
from asyncio import sleep

from functions import get_value, set_value, get_today
import state as st

######################################################################################

#główna klasa z przyciskiami dla wszystkich quizów
class BaseQuizView(ui.View):
    def __init__(self, correct_answer: bool, interaction: Interaction, timeout: int):
        super().__init__(timeout=timeout)
        self.correct_answer = correct_answer
        self.interaction = interaction
        self.user = interaction.user
        self.answered = False

    #przycisk prawda
    @ui.button(label="Prawda", style=ButtonStyle.green)
    async def true_button(self, interaction: Interaction, button: ui.Button):
        await self.handle_answer(interaction, True)

    #przycisk fałsz
    @ui.button(label="Fałsz", style=ButtonStyle.red)
    async def false_button(self, interaction: Interaction, button: ui.Button):
        await self.handle_answer(interaction, False)

    #reakcja na odpowiedź gracza
    async def handle_answer(self, interaction: Interaction, chosen_answer: bool):
        return



#przyciski dla quizu rankingowego
class RankedQuizView(BaseQuizView):
    def __init__(self, correct_answer: bool, interaction: Interaction):
        super().__init__(correct_answer, interaction, timeout=10)
        self.user_streaks = st.user_streaks

    #gracz nie zdążył odpowiedzieć w ciągu 10 sekund
    async def on_timeout(self):
        if self.answered:
            return

        self.user_streaks[self.user.id] = 0
        set_value(self.user.id, points=-1)
        self.stop()
        embed = Embed(
            description=f"⏰ Nie odpowiedziałeś/aś w ciągu 10 sekund!\n"
                        f"**-1 punkt**",
            color=Color.from_str("#c71616"))
        await self.interaction.followup.send(embed=embed, ephemeral=True)

    #reakcja na odpowiedź gracza
    async def handle_answer(self, interaction: Interaction, chosen_answer: bool):
        self.answered = True

        #gracz odpowiedział poprawnie
        if chosen_answer == self.correct_answer:
            self.user_streaks[self.user.id] = self.user_streaks.get(self.user.id, 0) + 1
            set_value(self.user.id, points=+1)
            bonus_text = ""

            #punkt bonusowy za 3 poprawne odpowiedzi z rzędu
            if self.user_streaks[self.user.id] == 3:
                set_value(self.user.id, points=+1)
                self.user_streaks[self.user.id] = 0
                bonus_text = "\n🔥 Bonus **+1 punkt** za 3 poprawne odpowiedzi z rzędu!\n"

            #gracz nie ma jeszcze passy 3 poprawnych odpowiedzi z rzędu
            points = get_value(self.user.id, "points")
            self.stop()
            embed = Embed(
                description=f"✅ Poprawna odpowiedź!{bonus_text}\n"
                            f"Twoja liczba punktów: **{points}**",
                color=Color.from_str("#22c716"))
            await interaction.response.edit_message(embed=embed, view=None)

        #gracz odpowiedział niepoprawnie
        else:
            self.user_streaks[self.user.id] = 0
            set_value(self.user.id, points=-1)
            self.stop()
            embed = Embed(
                description=f"❌ Niestety jest to zła odpowiedź!\n"
                            f"**-1 punkt**",
                color=Color.from_str("#c71616"))
            await interaction.response.edit_message(embed=embed, view=None)



#przyciski dla maratonu quizowego
class MarathonQuizView(BaseQuizView):
    def __init__(self, correct_answer: bool, interaction: Interaction, current_wave: int):
        super().__init__(correct_answer, interaction, timeout=15)
        self.current_wave = current_wave

    #gracz nie zdążył odpowiedzieć w ciągu 15 sekund
    async def on_timeout(self):
        if self.answered:
            return

        st.active_quizzes[self.user.id] = False
        old_record = get_value(self.user.id, "marathon_record")

        #gracz pobił swój rekord
        if (self.current_wave - 1) > old_record:
            set_value(self.user.id, marathon_record=self.current_wave - 1)
            description_continuation = (
                f"🎉 Pobiłeś/aś swój poprzedni rekord poziomów: **{old_record}**, osiągając **{self.current_wave - 1}**!")
            color = Color.from_str("#343d91")

        #gracz nie pobił swojego rekordu
        else:
            description_continuation = (
                f"Twój wynik: **{self.current_wave - 1}** poziomów.\n"
                f"Twój rekord to nadal: **{old_record}**")
            color = Color.from_str("#093e99")

        self.stop()
        embed = Embed(
            title="⏰ Czas minął!",
            description=f"Nie odpowiedziałeś/aś w ciągu 15 sekund!\n\n"
                        f"{description_continuation}",
            color=color)
        await self.interaction.followup.send(embed=embed, ephemeral=True)

    #reakcja na odpowiedź gracza
    async def handle_answer(self, interaction: Interaction, chosen_answer: bool):
        from quiz_logic import next_marathon_question

        self.answered = True

        #gracz odpowiedział poprawnie
        if chosen_answer == self.correct_answer:
            description_continuation = f"Przechodzisz do **poziomu {self.current_wave + 1}**!"
            color = Color.from_str("#22c716")

            #nagroda punktów rankingowych za 10 poziom
            if self.current_wave == 10:
                set_value(self.user.id, points=+2)
                description_continuation = f"\n🎉 Otrzymujesz **2 punkty rankingowe** za pokonanie **10** poziomów, tak trzymaj!"

            #nagroda punktów rankingowych za 20, 40, 60, 80 poziom
            elif self.current_wave in (20, 40, 60, 80):
                bonus_points = {20: 5, 40: 10, 60: 15, 80: 20}[self.current_wave]
                set_value(self.user.id, points=+bonus_points)
                description_continuation = (
                    f"\n🎉 Otrzymujesz **{bonus_points} punktów rankingowych** za pokonanie **{self.current_wave}** poziomów, tak trzymaj!")
                color = Color.from_str("#a8ff6e")

            #nagroda punktów rankingowych i rangi "Mistrz Quizów" za osiągnięcie 100 poziom
            elif self.current_wave == 100:
                set_value(self.user.id, points=+30)
                description_continuation = (
                    f"\n💀 Pokonałeś/aś już **100** poziomów! 💀\n"
                    f"W nagrodę dostajesz **30 punktów rankingowych** i rangę **Mistrz Quizów**!")
                color = Color.from_str("#ccec3e")

                quiz_master_role = self.interaction.guild.get_role(1441141637831987372)
                if quiz_master_role is not None:
                    await self.user.add_roles(quiz_master_role)

            self.stop()
            embed = Embed(
                description=f"✅ Poprawna odpowiedź!\n"
                            f"{description_continuation}",
                color=color)
            await interaction.response.edit_message(embed=embed, view=None)
            await sleep(1)
            await next_marathon_question(self.interaction, self.current_wave + 1)

        #gracz odpowiedział niepoprawnie
        else:
            st.active_quizzes[self.user.id] = False
            old_record = get_value(self.user.id, "marathon_record")

            #gracz pobił swój rekord
            if (self.current_wave - 1) > old_record:
                set_value(self.user.id, marathon_record=self.current_wave - 1)
                description = (
                    f"🎉 Pobiłeś/aś swój poprzedni rekord poziomów: **{old_record}**, "
                    f"osiągając **{self.current_wave - 1}**!")
                color = Color.from_str("#fc6f6f")

            #gracz nie pobił swojego rekordu
            else:
                description = (
                    f"Twój wynik: **{self.current_wave - 1}** poziomów.\n"
                    f"Twój rekord to nadal: **{old_record}**")
                color = Color.from_str("#c71616")

            self.stop()
            embed = Embed(
                title="❌ Niestety jest to zła odpowiedź!",
                description=description,
                color=color)
            await interaction.response.edit_message(embed=embed, view=None)



#przyciski dla speedrunu quizowego
class SpeedrunQuizView(BaseQuizView):
    def __init__(self, correct_answer: bool, interaction: Interaction, speedrun_data: dict):
        super().__init__(correct_answer, interaction, timeout=8)
        self.data = speedrun_data

    #gracz nie zdążył odpowiedzieć w ciągu 15 sekund
    async def on_timeout(self):
        from quiz_logic import next_speedrun_question

        if self.answered:
            return

        if self.data.get("time_left", 0) <= 0:
            self.data["question_active"] = False
            self.stop()
            return

        self.data["question_active"] = False
        self.stop()
        await next_speedrun_question(self.interaction, self.data)

    #reakcja na odpowiedź gracza
    async def handle_answer(self, interaction: Interaction, chosen_answer: bool):
        from quiz_logic import next_speedrun_question

        #pytanie nieaktywne lub czas minął
        if self.data.get("time_left", 0) <= 0 or not self.data.get("question_active", False):
            embed = Embed(
                description="⛔ To pytanie już nie jest aktywne!",
                color=Color.from_str("#961212"))
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        #gracz odpowiedział już na dane pytanie
        if self.answered:
            embed = Embed(
                description="⛔ Już odpowiedziałeś/aś na to pytanie!",
                color=Color.from_str("#961212"))
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        self.answered = True
        self.data["question_active"] = False

        #gracz odpowiedział poprawnie
        if chosen_answer == self.correct_answer:
            self.data["score"] += 1
            embed = Embed(
                description="✅ Poprawna odpowiedź!",
                color=Color.from_str("#22c716"))

        #gracz odpowiedział niepoprawnie
        else:
            embed = Embed(
                description="❌ Niestety jest to zła odpowiedź!",
                color=Color.from_str("#c71616"))

        self.stop()
        await interaction.response.edit_message(embed=embed, view=None)
        await sleep(0.2)

        #następne pytanie
        if self.data.get("time_left", 0) > 0:
            await next_speedrun_question(self.interaction, self.data)
        return None



#przyciski dla obstawiania stawki trybu ryzyka
class RiskQuizBetsView(ui.View):
    def __init__(self, interaction):
        super().__init__(timeout=30)
        self.interaction = interaction
        self.user = interaction.user

    #gracz nie wybrał niczego przez 30 sekund
    async def on_timeout(self):
        st.active_quizzes[self.user.id] = False
        self.stop()
        embed = Embed(
            description=f"⏰ Nie wybrałeś nic przez 30 sekund, więc twój quiz został zatrzymany.",
            color=Color.from_str("#961212"))
        return await self.interaction.followup.send(embed=embed, ephemeral=True)

    #reakcja na wybór gracza
    async def handle_bet(self, interaction, bet):
        from quiz_logic import risk_quiz

        points = get_value(self.user.id, "points")

        #gracz chce obstawić punktów rankingowych więcej niż posiada
        if points < bet:
            self.stop()
            embed = Embed(
                description=f"⛔ Nie masz tylu punktów! Masz tylko **{points}**.",
                color=Color.from_str("#961212"))
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        self.stop()
        embed = Embed(
            description=f"**Quiz w trybie ryzyka** za chwilę się rozpocznie!\n"
                        f"Składa się z 10 pytań, z których na każde masz równo 10 sekund.\n"
                        f"Obstawiono **{bet} punktów rankingowych**.\n"
                        f"Przygotuj się!",
            color=Color.from_str("#cf3b38"))
        await interaction.response.edit_message(embed=embed, view=None)
        await sleep(5)
        return await risk_quiz(self.interaction, bet)

    #przycisk do obstawienia 5 punktów
    @ui.button(label="5", style=ButtonStyle.blurple)
    async def bet5(self, interaction: Interaction, button: ui.Button):
        await self.handle_bet(interaction, 5)

    #przycisk do obstawienia 5 punktów
    @ui.button(label="10", style=ButtonStyle.blurple)
    async def bet10(self, interaction: Interaction, button: ui.Button):
        await self.handle_bet(interaction, 10)

    #przycisk do obstawienia 5 punktów
    @ui.button(label="20", style=ButtonStyle.blurple)
    async def bet20(self, interaction: Interaction, button: ui.Button):
        await self.handle_bet(interaction, 20)

    #przycisk do obstawienia 5 punktów
    @ui.button(label="25", style=ButtonStyle.blurple)
    async def bet25(self, interaction: Interaction, button: ui.Button):
        await self.handle_bet(interaction, 25)

    #przycisk do zamknięcia wybierania zakładów
    @ui.button(label="❌ Zamknij", style=ButtonStyle.red)
    async def close(self, interaction: Interaction, button: ui.Button):
        st.active_quizzes[self.user.id] = False
        self.stop()
        embed = Embed(
            description="⛔ Zamknięto tryb ryzyka.",
            color=Color.from_str("#961212"))
        return await interaction.response.edit_message(embed=embed, view=None)


#przyciski dla trybu ryzyka
class RiskQuizView(BaseQuizView):
    def __init__(self, correct_answer, interaction, bet, risk_data):
        super().__init__(correct_answer, interaction, timeout=10)
        self.bet = bet
        self.risk_data = risk_data

    #gracz nie zdążył odpowiedzieć w ciągu 10 sekund
    async def on_timeout(self):
        if self.answered:
            return

        self.risk_data["active"] = False
        st.active_quizzes[self.user.id] = False
        set_value(self.user.id, points=-self.bet)
        self.stop()
        embed = Embed(
            title="⏰ Czas minął!",
            description=f"Przegrałeś zakład: **-{self.bet} pkt**",
            color=Color.from_str("#c71616"))
        await self.interaction.followup.send(embed=embed, ephemeral=True)
        return

        #reakcja na odpowiedź gracza
    async def handle_answer(self, interaction, chosen_answer):
        self.answered = True

        #gracz odpowiedział poprawnie
        if chosen_answer == self.correct_answer:
            self.risk_data["correct_count"] += 1
            self.stop()
            embed = Embed(
                description="✅ Poprawna odpowiedź!",
                color=Color.from_str("#22c716"))
            return await interaction.response.edit_message(embed=embed, view=None)

        #gracz odpowiedział niepoprawnie
        else:
            self.risk_data["active"] = False
            st.active_quizzes[self.user.id] = False
            set_value(self.user.id, points=-self.bet)
            self.stop()
            embed = Embed(
                title="❌ Niestety jest to zła odpowiedź!",
                description=f"Przegrałeś zakład: **-{self.bet} pkt**",
                color=Color.from_str("#c71616"))
            return await interaction.response.edit_message(embed=embed, view=None)



#przyciski dla quizu serwerowego
class ServerQuizView(BaseQuizView):
    def __init__(self, correct_answer: bool, interaction: Interaction, answered_users: set):
        super().__init__(correct_answer, interaction, timeout=15)
        self.answered_users = answered_users
        self.local_scores = st.local_scores

    #reakcja na odpowiedź gracza
    async def handle_answer(self, interaction: Interaction, chosen_answer: bool):
        #gracz odpowiedział już na dane pytanie
        if interaction.user.id in self.answered_users:
            embed = Embed(
                description="⛔ Już odpowiedziałeś/aś na to pytanie!",
                color=Color.from_str("#961212"))
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        self.answered_users.add(interaction.user.id)

        #gracz odpowiedział poprawnie
        if chosen_answer == self.correct_answer:
            self.local_scores[interaction.user.id] = self.local_scores.get(interaction.user.id, 0) + 1
            embed = Embed(
                description="✅ Poprawna odpowiedź!",
                color=Color.from_str("#22c716"))

        #gracz odpowiedział niepoprawnie
        else:
            embed = Embed(
                description="❌ Niestety jest to zła odpowiedź!",
                color=Color.from_str("#c71616"))

        await interaction.response.send_message(embed=embed, ephemeral=True)
        return self.stop()



#przyciski dla pytania z wybranej kategorii
class CategoryQuestionView(BaseQuizView):
    def __init__(self, correct_answer: bool, interaction: Interaction):
        super().__init__(correct_answer, interaction, timeout=None)

    #reakcja na odpowiedź gracza
    async def handle_answer(self, interaction: Interaction, chosen_answer: bool):
        self.answered = True

        #gracz odpowiedział poprawnie
        if chosen_answer == self.correct_answer:
            embed = Embed(
                description="✅ Poprawna odpowiedź!",
                color=Color.from_str("#22c716"))

        #gracz odpowiedział niepoprawnie
        else:
            embed = Embed(
                description="❌ Niestety jest to zła odpowiedź!",
                color=Color.from_str("#c71616"))

        self.stop()
        await interaction.response.edit_message(embed=embed, view=None)



#przyciski dla pytania dziennego
class DailyQuestionView(BaseQuizView):
    def __init__(self, correct_answer, interaction, daily_streak):
        super().__init__(correct_answer, interaction, timeout=None)
        self.streak = daily_streak

    #reakcja na odpowiedź gracza
    async def handle_answer(self, interaction, chosen_answer):
        if self.answered:
            return

        self.answered = True

        #gracz odpowiedział poprawnie
        if chosen_answer == self.correct_answer:
            description_continuation = ""
            #nagroda punktu rankingowego za minimum 5 dni passy z rzędu
            if get_value(self.user.id, "daily_streak") >= 5:
                set_value(self.user.id, points=+1)
                description_continuation = "\n**+1 punkt**!"

            embed = Embed(
                description=f"✅ Poprawna odpowiedź!\n"
                            f"Twoja passa aktywności: **{self.streak} dni**.{description_continuation}",
                color=Color.from_str("#22c716"))

        #gracz odpowiedział niepoprawnie
        else:
            embed = Embed(
                description=f"❌ Niestety jest to zła odpowiedź!\n"
                            f"Twoja passa aktywności: **{self.streak} dni**.",
                color=Color.from_str("#c71616"))

        self.stop()
        set_value(self.user.id, last_daily=get_today().isoformat(), daily_streak=self.streak)
        await interaction.response.edit_message(embed=embed, view=None)