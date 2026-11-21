"""Commands for managing a user's saved GitHub username."""

import re

from discord import app_commands
from discord.ext import commands

from bot import BotClient, BotInteraction
from store import Store


GITHUB_ACCOUNTS_KEY = "github_accounts"


class GitHubAccountCog(commands.Cog):
    account_group = app_commands.Group(name="github-account", description="Manage your linked GitHub account.")

    @account_group.command(name="link", description="Save your GitHub username for challenge lookups.")
    @app_commands.describe(username="Your GitHub username.")
    async def link(self, interaction: BotInteraction, username: str):
        if await interaction.client.command_context.deny_if_unauthorized(interaction):
            return

        username = username.strip().removeprefix("@").lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,38}", username):
            await interaction.response.send_message("Enter a GitHub username.", ephemeral=True)
            return

        user_id = str(interaction.user.id)
        Store.update_key(GITHUB_ACCOUNTS_KEY, lambda accounts: {
            **(accounts if isinstance(accounts, dict) else {}), user_id: username,
        })
        accounts = Store.get_key(GITHUB_ACCOUNTS_KEY, {})
        if isinstance(accounts, dict) and accounts.get(user_id) == username:
            message = f"Saved GitHub username `{username}`."
        else:
            message = "The bot could not save your GitHub username. Contact an administrator."
        await interaction.response.send_message(message, ephemeral=True)

    @account_group.command(name="unlink", description="Remove your saved GitHub username from the bot.")
    async def unlink(self, interaction: BotInteraction):
        user_id = str(interaction.user.id)
        Store.update_key(GITHUB_ACCOUNTS_KEY, lambda accounts: {
            discord_id: username for discord_id, username in accounts.items() if discord_id != user_id
        } if isinstance(accounts, dict) else {})
        accounts = Store.get_key(GITHUB_ACCOUNTS_KEY, {})
        if isinstance(accounts, dict) and user_id in accounts:
            message = "The bot could not remove your GitHub account. Contact an administrator."
        else:
            message = "Your GitHub account is unlinked."
        await interaction.response.send_message(message, ephemeral=True)


async def setup(bot: BotClient):
    await bot.add_cog(GitHubAccountCog())
