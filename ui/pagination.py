from typing import Optional, Any, Callable
import asyncio
import discord
from core.config import is_admin
from .embeds import info_embed, error_embed

class SavedPaginationView(discord.ui.View):
	"""
	Interactive Discord UI button pagination view for saved keys.
	Provides 5-button navigation with permission isolation so only
	the invoking user (or bot admins) can interact with it.
	"""
	def __init__(self, invoking_user_id: int, target_user_id: int, keys: list[str], timeout: float = 180.0):
		super().__init__(timeout=timeout)
		self.invoking_user_id = invoking_user_id
		self.target_user_id = target_user_id
		self.keys = keys
		self.current_page = 0
		self.per_page = 10
		self.total_pages = max(1, (len(keys) + self.per_page - 1) // self.per_page)
		self.message = None
		self._update_buttons()

	def get_embed(self) -> discord.Embed:
		start_idx = self.current_page * self.per_page
		end_idx = start_idx + self.per_page
		page_keys = self.keys[start_idx:end_idx]

		embed = discord.Embed(
			title="🔑 Saved Keys",
			description=f"Saved keys for <@{self.target_user_id}>\n\n" + "\n".join([f"- `{k}`" for k in page_keys]),
			color=discord.Color.blurple()
		)
		embed.set_footer(text=f"Page {self.current_page + 1} of {self.total_pages} • Total: {len(self.keys)} key(s)")
		return embed

	def _update_buttons(self):
		self.first_button.disabled = (self.current_page == 0)
		self.prev_button.disabled = (self.current_page == 0)
		self.page_indicator.label = f"{self.current_page + 1}/{self.total_pages}"
		self.next_button.disabled = (self.current_page >= self.total_pages - 1)
		self.last_button.disabled = (self.current_page >= self.total_pages - 1)

	async def interaction_check(self, interaction: discord.Interaction) -> bool:
		if interaction.user.id != self.invoking_user_id and not is_admin(interaction.user.id):
			await interaction.response.send_message(
				"You cannot interact with these buttons because you did not invoke this command.",
				ephemeral=True
			)
			return False
		return True

	@discord.ui.button(label="⏮️", style=discord.ButtonStyle.secondary)
	async def first_button(self, interaction: discord.Interaction, button: discord.ui.Button):
		self.current_page = 0
		self._update_buttons()
		await interaction.response.edit_message(embed=self.get_embed(), view=self)

	@discord.ui.button(label="◀️", style=discord.ButtonStyle.primary)
	async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
		if self.current_page > 0:
			self.current_page -= 1
		self._update_buttons()
		await interaction.response.edit_message(embed=self.get_embed(), view=self)

	@discord.ui.button(label="1/1", style=discord.ButtonStyle.secondary, disabled=True)
	async def page_indicator(self, interaction: discord.Interaction, button: discord.ui.Button):
		pass

	@discord.ui.button(label="▶️", style=discord.ButtonStyle.primary)
	async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
		if self.current_page < self.total_pages - 1:
			self.current_page += 1
		self._update_buttons()
		await interaction.response.edit_message(embed=self.get_embed(), view=self)

	@discord.ui.button(label="⏭️", style=discord.ButtonStyle.secondary)
	async def last_button(self, interaction: discord.Interaction, button: discord.ui.Button):
		self.current_page = self.total_pages - 1
		self._update_buttons()
		await interaction.response.edit_message(embed=self.get_embed(), view=self)

	async def on_timeout(self):
		for child in self.children:
			child.disabled = True
		if self.message:
			try:
				await self.message.edit(view=self)
			except Exception:
				pass

class SavedPromptView(discord.ui.View):
	"""
	Interactive trigger view for ;;saved.
	Presents a 'View Saved Keys' button. When clicked by ANY user,
	fetches that specific user's saved keys and responds with a private
	ephemeral paginated embed that only they can see.
	"""
	def __init__(
		self,
		db_manager: Any,
		target_user_id: Optional[int] = None,
		timeout: Optional[float] = 300.0
	):
		super().__init__(timeout=timeout)
		self.db_manager = db_manager
		self.target_user_id = target_user_id
		self.message = None

	@discord.ui.button(label="View Saved Keys", emoji="🔑", style=discord.ButtonStyle.primary)
	async def view_saved_keys(self, interaction: discord.Interaction, button: discord.ui.Button):
		user_id = interaction.user.id
		# If an admin invoked for another user, show that user's keys to the admin
		if self.target_user_id is not None and is_admin(user_id):
			keys_user_id = self.target_user_id
		else:
			keys_user_id = user_id

		keys = sorted(self.db_manager.get_user_keys(keys_user_id))
		if len(keys) == 0:
			msg = "You have not saved any keys yet." if keys_user_id == user_id else f"<@{keys_user_id}> has not saved any keys yet."
			await interaction.response.send_message(embed=info_embed(msg), ephemeral=True)
			return

		view = SavedPaginationView(
			invoking_user_id=user_id,
			target_user_id=keys_user_id,
			keys=keys
		)
		await interaction.response.send_message(
			embed=view.get_embed(),
			view=view,
			ephemeral=True
		)

	async def on_timeout(self):
		for child in self.children:
			child.disabled = True
		if self.message:
			try:
				await self.message.edit(view=self)
			except Exception:
				pass

class DreamBanlistPaginationView(discord.ui.View):
	"""
	Interactive Discord UI button pagination view for dream banlist.
	Provides 5-button navigation with permission isolation so only
	bot admins can interact with it.
	"""
	def __init__(self, invoking_user_id: int, entries: list[dict], timeout: float = 180.0):
		super().__init__(timeout=timeout)
		self.invoking_user_id = invoking_user_id
		self.entries = entries
		self.current_page = 0
		self.per_page = 5
		self.total_pages = max(1, (len(entries) + self.per_page - 1) // self.per_page)
		self.message = None
		self._update_buttons()

	def get_embed(self) -> discord.Embed:
		start_idx = self.current_page * self.per_page
		end_idx = start_idx + self.per_page
		page_entries = self.entries[start_idx:end_idx]

		embed = discord.Embed(
			title="🚫 Dream Command Banlist",
			description=f"Total banned users: **{len(self.entries)}**\n",
			color=discord.Color.dark_red()
		)

		for i, entry in enumerate(page_entries, start=start_idx + 1):
			uid = entry.get('user_id', 'Unknown')
			uname = entry.get('username', 'Unknown')
			ts = entry.get('timestamp', 'Unknown')
			prompt = entry.get('banned_prompt', 'No prompt specified')
			prompt_display = prompt.replace('\n', ' ')
			if len(prompt_display) > 80:
				prompt_display = prompt_display[:77] + "..."

			embed.add_field(
				name=f"{i}. {uname} (<@{uid}>)",
				value=f"• **ID:** `{uid}`\n• **Date:** `{ts}`\n• **Prompt:** *{prompt_display}*",
				inline=False
			)

		embed.set_footer(text=f"Page {self.current_page + 1} of {self.total_pages} • Total: {len(self.entries)} banned user(s)")
		return embed

	def _update_buttons(self):
		self.first_button.disabled = (self.current_page == 0)
		self.prev_button.disabled = (self.current_page == 0)
		self.page_indicator.label = f"{self.current_page + 1}/{self.total_pages}"
		self.next_button.disabled = (self.current_page >= self.total_pages - 1)
		self.last_button.disabled = (self.current_page >= self.total_pages - 1)

	async def interaction_check(self, interaction: discord.Interaction) -> bool:
		if not is_admin(interaction.user.id):
			await interaction.response.send_message(
				"Only bot admins can interact with the dream banlist.",
				ephemeral=True
			)
			return False
		return True

	@discord.ui.button(label="⏮️", style=discord.ButtonStyle.secondary)
	async def first_button(self, interaction: discord.Interaction, button: discord.ui.Button):
		self.current_page = 0
		self._update_buttons()
		await interaction.response.edit_message(embed=self.get_embed(), view=self)

	@discord.ui.button(label="◀️", style=discord.ButtonStyle.primary)
	async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
		if self.current_page > 0:
			self.current_page -= 1
		self._update_buttons()
		await interaction.response.edit_message(embed=self.get_embed(), view=self)

	@discord.ui.button(label="1/1", style=discord.ButtonStyle.secondary, disabled=True)
	async def page_indicator(self, interaction: discord.Interaction, button: discord.ui.Button):
		pass

	@discord.ui.button(label="▶️", style=discord.ButtonStyle.primary)
	async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
		if self.current_page < self.total_pages - 1:
			self.current_page += 1
		self._update_buttons()
		await interaction.response.edit_message(embed=self.get_embed(), view=self)

	@discord.ui.button(label="⏭️", style=discord.ButtonStyle.secondary)
	async def last_button(self, interaction: discord.Interaction, button: discord.ui.Button):
		self.current_page = self.total_pages - 1
		self._update_buttons()
		await interaction.response.edit_message(embed=self.get_embed(), view=self)

	async def on_timeout(self):
		for child in self.children:
			child.disabled = True
		if self.message:
			try:
				await self.message.edit(view=self)
			except Exception:
				pass

class DreamBanlistPromptView(discord.ui.View):
	"""
	Interactive trigger view for ;;dream_banlist.
	Presents a 'View Dream Banlist' button. When clicked by a bot admin,
	fetches the banned users and responds with a private ephemeral
	paginated embed that only they can see.
	"""
	def __init__(
		self,
		get_banned_users_fn: Optional[Callable[[], list[dict]]] = None,
		timeout: Optional[float] = 300.0
	):
		super().__init__(timeout=timeout)
		self.get_banned_users_fn = get_banned_users_fn
		self.message = None

	@discord.ui.button(label="View Dream Banlist", emoji="🚫", style=discord.ButtonStyle.danger)
	async def view_banlist(self, interaction: discord.Interaction, button: discord.ui.Button):
		if not is_admin(interaction.user.id):
			await interaction.response.send_message(
				embed=error_embed("You don't have permission to view the dream banlist."),
				ephemeral=True
			)
			return

		fn = self.get_banned_users_fn
		if fn is None:
			from cmds.memes.dream import get_banned_users
			fn = get_banned_users

		banned_users = await asyncio.to_thread(fn)
		if not banned_users:
			await interaction.response.send_message(
				embed=info_embed("The dream banlist is currently empty.", title="📋 Dream Banlist"),
				ephemeral=True
			)
			return

		view = DreamBanlistPaginationView(
			invoking_user_id=interaction.user.id,
			entries=banned_users
		)
		if view.total_pages <= 1:
			await interaction.response.send_message(
				embed=view.get_embed(),
				ephemeral=True
			)
		else:
			await interaction.response.send_message(
				embed=view.get_embed(),
				view=view,
				ephemeral=True
			)

	async def on_timeout(self):
		for child in self.children:
			child.disabled = True
		if self.message:
			try:
				await self.message.edit(view=self)
			except Exception:
				pass
