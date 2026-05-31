"""Games cog for ExeGuard.

Merged from Olympus-Bot. Provides interactive games like RPS, 
Tic-Tac-Toe, Wordle, 2048, and Chess.
"""

from __future__ import annotations

import os
import io
import random
import uuid
import bisect
import discord
from PIL import Image
from discord import app_commands
from discord.ext import commands
from typing import List, Tuple

import games as games_pkg
from utils.embed_builder import EmbedBuilder

CARDS_PATH = 'data/cards/'
PICTURES_PATH = 'data/pictures/'

class Card:
    suits = ["clubs", "diamonds", "hearts", "spades"]

    def __init__(self, suit: str, value: int, down=False):
        self.suit = suit
        self.value = value
        self.down = down
        self.symbol = self.name[0].upper()

    @property
    def name(self) -> str:
        if self.value <= 10:
            return str(self.value)
        else:
            return {
                11: 'jack',
                12: 'queen',
                13: 'king',
                14: 'ace',
            }[self.value]

    @property
    def image(self):
        return (
            f"{self.symbol if self.name != '10' else '10'}" \
            f"{self.suit[0].upper()}.png" \
            if not self.down else "red_back.png"
        )

    def flip(self):
        self.down = not self.down
        return self

    def __str__(self) -> str:
        return f'{self.name.title()} of {self.suit.title()}'

class Games(commands.Cog):
    """Interactive games for server members."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── Blackjack Helpers ───────────────────────────────────────────

    @staticmethod
    def hand_to_images(hand: List[Card]) -> List[Image.Image]:
        return [Image.open(os.path.join(CARDS_PATH, card.image)) for card in hand]

    @staticmethod
    def center(*hands: Tuple[Image.Image]) -> Image.Image:
        bg: Image.Image = Image.open(os.path.join(CARDS_PATH, 'table.png'))
        bg_center_x = bg.size[0] // 2
        bg_center_y = bg.size[1] // 2
        img_w = hands[0][0].size[0]
        img_h = hands[0][0].size[1]
        start_y = bg_center_y - (((len(hands) * img_h) + ((len(hands) - 1) * 15)) // 2)
        for hand in hands:
            start_x = bg_center_x - (((len(hand) * img_w) + ((len(hand) - 1) * 10)) // 2)
            for card in hand:
                bg.alpha_composite(card, (start_x, start_y))
                start_x += img_w + 10
            start_y += img_h + 15
        return bg

    @staticmethod
    def calc_hand(hand: List[Card]) -> int:
        non_aces = [c for c in hand if c.symbol != 'A']
        aces = [c for c in hand if c.symbol == 'A']
        total_sum = 0
        for card in non_aces:
            if not card.down:
                if card.symbol in 'JQK':
                    total_sum += 10
                else:
                    total_sum += card.value
        for card in aces:
            if not card.down:
                if total_sum <= 10:
                    total_sum += 11
                else:
                    total_sum += 1
        return total_sum

    # ── Game Commands ───────────────────────────────────────────────

    @app_commands.command(name="blackjack", description="Play a game of Blackjack")
    async def blackjack(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        
        deck = [Card(suit, value) for suit in Card.suits for value in range(2, 15)]
        random.shuffle(deck)

        player_hand = [deck.pop(), deck.pop()]
        dealer_hand = [deck.pop(), deck.pop().flip()]

        def get_file():
            img = self.center(self.hand_to_images(dealer_hand), self.hand_to_images(player_hand))
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            buf.seek(0)
            return discord.File(buf, filename='blackjack.png')

        class BlackjackView(discord.ui.View):
            def __init__(self, cog, player, p_hand, d_hand, deck_ref):
                super().__init__(timeout=60)
                self.cog = cog
                self.player = player
                self.p_hand = p_hand
                self.d_hand = d_hand
                self.deck = deck_ref
                self.interaction = None

            @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary)
            async def hit(self, btn_interaction: discord.Interaction, button: discord.ui.Button):
                if btn_interaction.user != self.player:
                    return await btn_interaction.response.send_message("This is not your game!", ephemeral=True)
                
                self.p_hand.append(self.deck.pop())
                p_val = self.cog.calc_hand(self.p_hand)
                
                if p_val > 21:
                    self.d_hand[1].flip()
                    embed = discord.Embed(title="Blackjack - Bust!", description=f"You busted with {p_val}!", color=discord.Color.red())
                    embed.set_image(url="attachment://blackjack.png")
                    await btn_interaction.response.edit_message(embed=embed, attachments=[get_file()], view=None)
                    self.stop()
                else:
                    embed = discord.Embed(title="Blackjack", description=f"Your hand: {p_val}", color=discord.Color.blue())
                    embed.set_image(url="attachment://blackjack.png")
                    await btn_interaction.response.edit_message(embed=embed, attachments=[get_file()], view=self)

            @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary)
            async def stand(self, btn_interaction: discord.Interaction, button: discord.ui.Button):
                if btn_interaction.user != self.player:
                    return await btn_interaction.response.send_message("This is not your game!", ephemeral=True)
                
                self.d_hand[1].flip()
                while self.cog.calc_hand(self.d_hand) < 17:
                    self.d_hand.append(self.deck.pop())
                
                p_val = self.cog.calc_hand(self.p_hand)
                d_val = self.cog.calc_hand(self.d_hand)
                
                if d_val > 21 or p_val > d_val:
                    result = "You won!"
                    color = discord.Color.green()
                elif p_val < d_val:
                    result = "Dealer won!"
                    color = discord.Color.red()
                else:
                    result = "It's a tie!"
                    color = discord.Color.gold()
                
                embed = discord.Embed(title=f"Blackjack - {result}", description=f"You: {p_val} | Dealer: {d_val}", color=color)
                embed.set_image(url="attachment://blackjack.png")
                await btn_interaction.response.edit_message(embed=embed, attachments=[get_file()], view=None)
                self.stop()

        p_val = self.calc_hand(player_hand)
        embed = discord.Embed(title="Blackjack", description=f"Your hand: {p_val}", color=discord.Color.blue())
        embed.set_image(url="attachment://blackjack.png")
        view = BlackjackView(self, interaction.user, player_hand, dealer_hand, deck)
        await interaction.followup.send(embed=embed, file=get_file(), view=view)

    @app_commands.command(name="slots", description="Play the slots")
    async def slots(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        try:
            facade = Image.open(os.path.join(PICTURES_PATH, 'slot-face.png')).convert('RGBA')
            reel = Image.open(os.path.join(PICTURES_PATH, 'slot-reel.png')).convert('RGBA')

            rw, rh = reel.size
            item = 180
            items = rh // item

            s1 = random.randint(1, items - 1)
            s2 = random.randint(1, items - 1)
            s3 = random.randint(1, items - 1)

            win_rate = 0.25
            if random.random() < win_rate:
                symbols_weights = [3.5, 7, 15, 25, 55]
                x = round(random.random() * 100, 1)
                pos = bisect.bisect(symbols_weights, x)
                s1 = pos + (random.randint(1, (items // 6) - 1) * 6)
                s2 = pos + (random.randint(1, (items // 6) - 1) * 6)
                s3 = pos + (random.randint(1, (items // 6) - 1) * 6)
                s1 = s1 - 6 if s1 == items else s1
                s2 = s2 - 6 if s2 == items else s2
                s3 = s3 - 6 if s3 == items else s3

            images = []
            speed = 6
            for i in range(1, (item // speed) + 1):
                bg = Image.new('RGBA', facade.size, color=(255, 255, 255))
                bg.paste(reel, (25 + rw * 0, 100 - (speed * i * s1)))
                bg.paste(reel, (25 + rw * 1, 100 - (speed * i * s2)))
                bg.paste(reel, (25 + rw * 2, 100 - (speed * i * s3)))
                bg.alpha_composite(facade)
                images.append(bg)

            buf = io.BytesIO()
            images[0].save(buf, format='GIF', save_all=True, append_images=images[1:], duration=50, loop=0)
            buf.seek(0)

            filename = f"slots_{uuid.uuid4()}.gif"
            file = discord.File(buf, filename=filename)

            if (1 + s1) % 6 == (1 + s2) % 6 == (1 + s3) % 6:
                result = "won"
                color = discord.Color.green()
            else:
                result = "lost"
                color = discord.Color.red()

            embed = discord.Embed(title=f"Slots - You {result}!", color=color)
            embed.set_image(url=f"attachment://{filename}")
            await interaction.followup.send(embed=embed, file=file)

        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)

    @app_commands.command(name="rps", description="Play Rock Paper Scissors")
    @app_commands.describe(opponent="The user you want to play against (optional)")
    async def rps(self, interaction: discord.Interaction, opponent: discord.Member | None = None) -> None:
        if opponent and opponent.bot:
            await interaction.response.send_message("You cannot play with bots!", ephemeral=True)
            return
        
        game = games_pkg.BetaRockPaperScissors(opponent)
        # The game.start method in olympus expects a Context or Interaction
        # We need to adapt it or use a wrapper.
        # Based on Games.py, it takes ctx.
        # We'll try to pass interaction if it supports it, or a mock ctx.
        ctx = await self.bot.get_context(interaction) # type: ignore
        await game.start(ctx, timeout=120)

    @app_commands.command(name="tictactoe", description="Play Tic-Tac-Toe with a user")
    @app_commands.describe(opponent="The user you want to play against")
    async def tictactoe(self, interaction: discord.Interaction, opponent: discord.Member) -> None:
        if opponent == interaction.user:
            await interaction.response.send_message("You cannot play against yourself!", ephemeral=True)
            return
        if opponent.bot:
            await interaction.response.send_message("You cannot play with bots!", ephemeral=True)
            return
        
        game = games_pkg.BetaTictactoe(cross=interaction.user, circle=opponent)
        ctx = await self.bot.get_context(interaction)
        await game.start(ctx, timeout=60)

    @app_commands.command(name="wordle", description="Play Wordle")
    async def wordle(self, interaction: discord.Interaction) -> None:
        game = games_pkg.Wordle()
        ctx = await self.bot.get_context(interaction)
        await game.start(ctx, timeout=120)

    @app_commands.command(name="twenty48", description="Play 2048")
    async def twenty48(self, interaction: discord.Interaction) -> None:
        game = games_pkg.BetaTwenty48()
        ctx = await self.bot.get_context(interaction)
        await game.start(ctx, win_at=2048)

    @app_commands.command(name="chess", description="Play Chess with a user")
    @app_commands.describe(opponent="The user you want to play against")
    async def chess(self, interaction: discord.Interaction, opponent: discord.Member) -> None:
        if opponent == interaction.user:
            await interaction.response.send_message("You cannot play against yourself!", ephemeral=True)
            return
        if opponent.bot:
            await interaction.response.send_message("You cannot play with bots!", ephemeral=True)
            return
            
        game = games_pkg.BetaChess(white=interaction.user, black=opponent)
        ctx = await self.bot.get_context(interaction)
        await game.start(ctx)

    @app_commands.command(name="connectfour", description="Play Connect Four with a user")
    @app_commands.describe(opponent="The user you want to play against")
    async def connectfour(self, interaction: discord.Interaction, opponent: discord.Member) -> None:
        if opponent == interaction.user:
            await interaction.response.send_message("You cannot play against yourself!", ephemeral=True)
            return
        if opponent.bot:
            await interaction.response.send_message("You cannot play with bots!", ephemeral=True)
            return
            
        game = games_pkg.ConnectFour(red=interaction.user, blue=opponent)
        ctx = await self.bot.get_context(interaction)
        await game.start(ctx, timeout=300)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Games(bot))
