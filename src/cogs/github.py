"""Cog for GitHub links."""

from discord import app_commands
from discord.ext import commands

from bot import BotInteraction


class GitHubCog(commands.Cog):
    github_group = app_commands.Group(name="github", description="GitHub links.")

    @github_group.command(name="links", description="Show links to the GitHub repository and its issues.")
    async def links(self, interaction: BotInteraction):
        ctx = interaction.client.command_context
        if await ctx.deny_if_unauthorized(interaction):
            return

        repo_url = ctx.gh_repo.html_url
        message = f"[View Repository]({repo_url})\n[View Issues]({repo_url}/issues)"
        await interaction.response.send_message(message, ephemeral=True)

    @github_group.command(name="project", description="Show the GitHub Project link.")
    async def project(self, interaction: BotInteraction):
        ctx = interaction.client.command_context
        if await ctx.deny_if_unauthorized(interaction):
            return

        if ctx.project_url:
            message = f"[View GitHub Project]({ctx.project_url})"
        else:
            message = "No GitHub Project is configured or could be resolved."
        await interaction.response.send_message(message, ephemeral=True)


async def setup(bot):
    await bot.add_cog(GitHubCog())
