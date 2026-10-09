from typing import Optional
import discord
from core.database import DatabaseManager
from core.config import is_admin
from ui.embeds import success_embed, info_embed, warning_embed

class ImportConfirmView(discord.ui.View):
	"""
	Interactive confirmation view presented when an imported JSON contains
	keys that already exist in the user's database and will be overwritten.
	"""
	def __init__(
		self,
		user_id: int,
		keys_dict: dict[str, str],
		overlapping_keys: list[str],
		db_manager: DatabaseManager,
		timeout: float = 60.0
	):
		super().__init__(timeout=timeout)
		self.user_id = user_id
		self.keys_dict = keys_dict
		self.overlapping_keys = overlapping_keys
		self.db_manager = db_manager
		self.message: Optional[discord.Message] = None

	async def interaction_check(self, interaction: discord.Interaction) -> bool:
		if interaction.user.id != self.user_id and not is_admin(interaction.user.id):
			await interaction.response.send_message(
				"You cannot interact with this confirmation because you did not invoke this command.",
				ephemeral=True
			)
			return False
		return True

	@discord.ui.button(label="Confirm & Overwrite", style=discord.ButtonStyle.danger, emoji="⚠️", custom_id="import_confirm")
	async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
		for child in self.children:
			if isinstance(child, discord.ui.Button):
				child.disabled = True

		new_count, overwritten_count = self.db_manager.import_user_keys(
			self.user_id,
			self.keys_dict,
			overwrite=True
		)

		total = new_count + overwritten_count
		embed = success_embed(
			f"Successfully imported **{total}** key(s) (**{new_count}** new, **{overwritten_count}** overwritten)!",
			title="✅ Import Complete"
		)

		await interaction.response.edit_message(embed=embed, view=self)
		self.stop()

	@discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="✖️", custom_id="import_cancel")
	async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
		for child in self.children:
			if isinstance(child, discord.ui.Button):
				child.disabled = True

		embed = info_embed(
			"Import cancelled. No changes were made to your saved keys.",
			title="❌ Import Cancelled"
		)

		await interaction.response.edit_message(embed=embed, view=self)
		self.stop()

	async def on_timeout(self):
		for child in self.children:
			if isinstance(child, discord.ui.Button):
				child.disabled = True

		if self.message:
			try:
				embed = warning_embed(
					"Import request timed out. No changes were made to your saved keys.",
					title="⏱️ Import Timed Out"
				)
				await self.message.edit(embed=embed, view=self)
			except Exception:
				pass
