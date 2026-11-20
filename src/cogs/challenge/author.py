"""Pagination for challenges assigned to a GitHub user."""

import asyncio

import discord
from requests.exceptions import RequestException

from bot import BotInteraction
from store import Store


CHALLENGES_PER_PAGE = 10


class AuthorChallengesView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.username = ""
        self.page = 0
        self.cursors: list[str | None] = [None]
        self.lock = asyncio.Lock()

    async def interaction_check(self, interaction: BotInteraction) -> bool:
        ctx = interaction.client.command_context
        return interaction.user.id == self.user_id and not await ctx.deny_if_unauthorized(interaction)

    async def start(self, interaction: BotInteraction, usernames: list[str]):
        for username in usernames:
            self.username = username
            cursor = None
            seen = set()
            while cursor not in seen:
                seen.add(cursor)
                project_url, issues, next_cursor = await self._fetch(interaction, cursor)
                if issues or not next_cursor:
                    break
                cursor = next_cursor
            if issues:
                break
        self.cursors[0] = cursor
        await self._show_page(interaction, 0, (project_url, issues, next_cursor if issues else None))

    async def _fetch(self, interaction: BotInteraction, cursor: str | None):
        ctx = interaction.client.command_context
        return await asyncio.to_thread(
            ctx.gh.get_author_challenges, ctx.project_id, self.username, CHALLENGES_PER_PAGE, cursor
        )

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: BotInteraction, button: discord.ui.Button):
        await self._move(interaction, -1)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: BotInteraction, button: discord.ui.Button):
        await self._move(interaction, 1)

    async def _move(self, interaction: BotInteraction, step: int):
        if self.lock.locked():
            await interaction.response.send_message("A page is already loading.", ephemeral=True)
            return

        async with self.lock:
            page = self.page + step
            await interaction.response.defer()
            if not 0 <= page < len(self.cursors):
                return
            try:
                result = await self._fetch(interaction, self.cursors[page])
            except (RequestException, ValueError) as e:
                interaction.client.command_context.logger.error(f"Failed to load author challenges page: {e}")
                await interaction.followup.send("Could not load that page from the GitHub Project.", ephemeral=True)
                return
            await self._show_page(interaction, page, result)

    async def _show_page(self, interaction: BotInteraction, page: int, result):
        project_url, issues, next_cursor = result
        lines = [
            f"Challenges assigned to `{self.username}` · Page {page + 1}",
            f"[View challenges in GitHub Projects]({project_url})",
        ]
        mapping = Store.get_key("challenges", {})
        channels = {}
        if isinstance(mapping, dict):
            for channel_id, issue_number in mapping.items():
                if channel_id.isdecimal() and interaction.guild.get_channel_or_thread(int(channel_id)):
                    channels[str(issue_number)] = int(channel_id)

        last_cursor = None
        for cursor, issue in issues:
            title = discord.utils.escape_markdown(issue["title"], ignore_links=False)
            labels = (issue.get("labels") or {}).get("nodes") or []
            category = next(
                (label["name"].removeprefix("Category: ") for label in labels
                 if label and label["name"].startswith("Category: ")),
                "Unknown",
            )
            category = discord.utils.escape_markdown(category, ignore_links=False)
            row = f"• {title} ({category}) | [GitHub]({issue['url']})"
            channel = channels.get(str(issue["number"]))
            if channel:
                row += f" | [Discord](https://discord.com/channels/{interaction.guild_id}/{channel})"
            if len("\n".join([*lines, row]).encode("utf-16-le")) > 2 * 2000:
                # Continue after the last displayed item so the next page includes this row.
                next_cursor = last_cursor
                break
            lines.append(row)
            last_cursor = cursor

        if not issues:
            lines.append("No visible challenges on this page." if next_cursor else "No challenges found for this author.")
        if next_cursor == self.cursors[page]:
            next_cursor = None

        prev_disabled, next_disabled = self.previous.disabled, self.next.disabled
        self.previous.disabled = page == 0
        self.next.disabled = next_cursor is None
        try:
            await interaction.edit_original_response(
                content="\n".join(lines),
                view=None if self.previous.disabled and self.next.disabled else self,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.HTTPException:
            self.previous.disabled, self.next.disabled = prev_disabled, next_disabled
            raise

        self.page = page
        self.cursors[page + 1:] = [next_cursor] if next_cursor else []
