import discord
from core.config import is_admin

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
			title="Saved Keys",
			description=f"Saved messages for <@{self.target_user_id}>\n\n" + "\n".join([f"- `{k}`" for k in page_keys]),
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

	@discord.ui.button(label="⏮️", style=discord.ButtonStyle.secondary, custom_id="saved_first")
	async def first_button(self, interaction: discord.Interaction, button: discord.ui.Button):
		self.current_page = 0
		self._update_buttons()
		await interaction.response.edit_message(embed=self.get_embed(), view=self)

	@discord.ui.button(label="◀️", style=discord.ButtonStyle.primary, custom_id="saved_prev")
	async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
		if self.current_page > 0:
			self.current_page -= 1
		self._update_buttons()
		await interaction.response.edit_message(embed=self.get_embed(), view=self)

	@discord.ui.button(label="1/1", style=discord.ButtonStyle.secondary, disabled=True, custom_id="saved_indicator")
	async def page_indicator(self, interaction: discord.Interaction, button: discord.ui.Button):
		pass

	@discord.ui.button(label="▶️", style=discord.ButtonStyle.primary, custom_id="saved_next")
	async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
		if self.current_page < self.total_pages - 1:
			self.current_page += 1
		self._update_buttons()
		await interaction.response.edit_message(embed=self.get_embed(), view=self)

	@discord.ui.button(label="⏭️", style=discord.ButtonStyle.secondary, custom_id="saved_last")
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
