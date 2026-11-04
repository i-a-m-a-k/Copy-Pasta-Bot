import asyncio
import random
from typing import Optional, Union
import aiohttp
import discord

from ui.embeds import error_embed, warning_embed
from ui.helpers import get_http_session

TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"
TRANSLATE_TIMEOUT = aiohttp.ClientTimeout(total=10)
RETRY_DELAY = 1.5  # seconds to wait before failing over to the other client on 429

# Requests with the default aiohttp User-Agent get throttled much faster
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'

# Rotated randomly per request to spread load and avoid getting blocked
CLIENTS = ['gtx', 'dict-chrome-ex']

# Maps language names/aliases to Google Translate language codes
LANGUAGES = {
	'abkhaz': 'abk', 'acehnese': 'ace', 'acholi': 'ach', 'afar': 'aar',
	'afrikaans': 'af', 'akan': 'ak', 'albanian': 'sq', 'alur': 'alz',
	'amharic': 'am', 'arabic': 'ar', 'armenian': 'hy', 'assamese': 'as',
	'avar': 'ava', 'awadhi': 'awa', 'aymara': 'ay', 'azerbaijani': 'az',
	'balinese': 'ban', 'baluchi': 'bal', 'bambara': 'bm', 'baoulé': 'bci',
	'bashkir': 'bak', 'basque': 'eu', 'batak karo': 'btx', 'batak simalungun': 'bts',
	'batak toba': 'bbc', 'belarusian': 'be', 'bemba': 'bem', 'bengali': 'bn',
	'betawi': 'bew', 'bhojpuri': 'bho', 'bikol': 'bik', 'bokmal': 'nb',
	'bosnian': 'bs', 'breton': 'bre', 'bulgarian': 'bg', 'burmese': 'my',
	'buryat': 'bua', 'cantonese': 'yue', 'catalan': 'ca', 'cebuano': 'ceb',
	'chamorro': 'cha', 'chechen': 'che', 'chichewa': 'ny', 'chinese': 'zh-CN',
	'chinese (simplified)': 'zh-CN', 'chinese (traditional)': 'zh-TW', 'chinese_simplified': 'zh-CN', 'chinese_traditional': 'zh-TW',
	'chuukese': 'chk', 'chuvash': 'chv', 'corsican': 'co', 'crimean tatar': 'crh',
	'croatian': 'hr', 'czech': 'cs', 'danish': 'da', 'dari': 'fa-AF',
	'dhivehi': 'dv', 'dinka': 'din', 'dogri': 'doi', 'dombe': 'dom',
	'dutch': 'nl', 'dyula': 'dyu', 'dzongkha': 'dzo', 'english': 'en',
	'esperanto': 'eo', 'estonian': 'et', 'faroese': 'fao', 'farsi': 'fa',
	'fijian': 'fij', 'filipino (tagalog)': 'fil', 'finnish': 'fi', 'fon': 'fon',
	'french': 'fr', 'frisian': 'fy', 'friulian': 'fur', 'fulani': 'ful',
	'ga': 'gaa', 'galician': 'gl', 'ganda': 'lg', 'georgian': 'ka',
	'german': 'de', 'greek': 'el', 'guarani': 'gn', 'gujarati': 'gu',
	'haitian': 'ht', 'haitian creole': 'ht', 'haitian_creole': 'ht', 'hakha chin': 'cnh',
	'hausa': 'ha', 'hawaiian': 'haw', 'hebrew': 'iw', 'hiligaynon': 'hil',
	'hindi': 'hi', 'hmong': 'hmn', 'hungarian': 'hu', 'hunsrik': 'hrx',
	'iban': 'iba', 'icelandic': 'is', 'igbo': 'ig', 'ilocano': 'ilo',
	'indonesian': 'id', 'irish': 'ga', 'italian': 'it', 'jamaican patois': 'jam',
	'japanese': 'ja', 'javanese': 'jw', 'jawi': 'ms-Arab', 'jingpo': 'kac',
	'kalaallisut': 'kal', 'kannada': 'kn', 'kanuri': 'kau', 'kapampangan': 'pam',
	'kazakh': 'kk', 'khasi': 'kha', 'khmer': 'km', 'kiga': 'cgg',
	'kikongo': 'kik', 'kinyarwanda': 'rw', 'kituba': 'ktu', 'kokborok': 'trp',
	'komi': 'kom', 'konkani': 'gom', 'korean': 'ko', 'krio': 'kri',
	'kurdish': 'ku', 'kurdish (sorani)': 'ckb', 'kurdish_kurmanji': 'ku', 'kurdish_sorani': 'ckb',
	'kyrgyz': 'ky', 'lao': 'lo', 'latgalian': 'ltg', 'latin': 'la',
	'latvian': 'lv', 'ligurian': 'lij', 'limburgish': 'lim', 'lingala': 'ln',
	'lithuanian': 'lt', 'lombard': 'lmo', 'luganda': 'lg', 'luo': 'luo',
	'luxembourgish': 'lb', 'macedonian': 'mk', 'madurese': 'mad', 'maithili': 'mai',
	'makassar': 'mak', 'malagasy': 'mg', 'malay': 'ms', 'malay (jawi)': 'ms-Arab',
	'malay_jawi': 'ms-Arab', 'malayalam': 'ml', 'maltese': 'mt', 'mam': 'mam',
	'manipuri': 'mni-Mtei', 'manx': 'glv', 'maori': 'mi', 'marathi': 'mr',
	'marshallese': 'mah', 'marwadi': 'mwr', 'mauritian creole': 'mfe', 'meadow mari': 'mhr',
	'meiteilon (manipuri)': 'mni-Mtei', 'minang': 'min', 'mizo': 'lus', 'mongolian': 'mn',
	'myanmar (burmese)': 'my', 'nahuatl (eastern huasteca)': 'nhe', 'ndau': 'ndc-ZW', 'ndebele (south)': 'nde',
	'nepalbhasa (newari)': 'new', 'nepali': 'ne', 'nko': 'bm-Nkoo', 'northern_sotho': 'nso',
	'norwegian': 'no', 'norwegian_bokmal': 'nb', 'nuer': 'nus', 'nyanja': 'ny',
	'nyanja (chichewa)': 'ny', 'occitan': 'oci', 'odia (oriya)': 'or', 'oromo': 'om',
	'ossetian': 'oss', 'pangasinan': 'pag', 'papiamento': 'pap', 'pashto': 'ps',
	'persian': 'fa', 'polish': 'pl', 'portuguese (portugal)': 'por', 'portuguese (portugal, brazil)': 'pt',
	'punjabi': 'pa', 'punjabi (shahmukhi)': 'pa-Arab', 'punjabi_gurmukhi': 'pa', 'punjabi_shahmukhi': 'pa-Arab',
	"q'eqchi'": 'kek', "q'eqchi": 'kek', 'quechua': 'qu', 'romani': 'rom', 'romanian': 'ro',
	'rundi': 'run', 'russian': 'ru', 'sami (north)': 'sme', 'samoan': 'sm',
	'sango': 'sag', 'sanskrit': 'sa', 'santali': 'sat', 'scots gaelic': 'gd',
	'scots_gaelic': 'gd', 'scottish': 'gd', 'sepedi': 'nso', 'serbian': 'sr',
	'sesotho': 'st', 'seychellois creole': 'crs', 'shahmukhi': 'pa-Arab', 'shan': 'shn',
	'shona': 'sn', 'sicilian': 'scn', 'silesian': 'szl', 'sindhi': 'sd',
	'sinhala (sinhalese)': 'si', 'slovak': 'sk', 'slovenian': 'sl', 'somali': 'so',
	'spanish': 'es', 'sundanese': 'su', 'susu': 'sus', 'swahili': 'sw',
	'swati': 'ssw', 'swedish': 'sv', 'tagalog': 'fil', 'tagalog (filipino)': 'tl',
	'tahitian': 'tah', 'tajik': 'tg', 'tamazight': 'ber-Latn', 'tamazight (tifinagh)': 'ber-Tfng',
	'tamil': 'ta', 'tatar': 'tt', 'telugu': 'te', 'tetum': 'tet',
	'thai': 'th', 'tibetan': 'bod', 'tigrinya': 'ti', 'tiv': 'tiv',
	'tok pisin': 'tpi', 'tongan': 'ton', 'tsonga': 'ts', 'tswana': 'tsn',
	'tulu': 'tcy', 'tumbuka': 'tum', 'turkish': 'tr', 'turkmen': 'tk',
	'tuvan': 'tuk', 'twi': 'ak', 'twi (akan)': 'ak', 'udmurt': 'udm',
	'ukrainian': 'uk', 'urdu': 'ur', 'uyghur': 'ug', 'uzbek': 'uz',
	'venda': 'ven', 'venetian': 'vec', 'vietnamese': 'vi', 'waray': 'war',
	'welsh': 'cy', 'wolof': 'wol', 'xhosa': 'xh', 'yakut': 'sah',
	'yiddish': 'yi', 'yoruba': 'yo', 'yucatec maya': 'yua', 'zapotec': 'zap',
	'zulu': 'zu',
	'zh': 'zh', 'he': 'iw', 'jv': 'jw',
}

_CODES_LOWER = {code.lower(): code for code in LANGUAGES.values()}

def resolve_language(language: str) -> Optional[str]:
	"""Resolve a language name, alias, or code to a Google Translate language code."""
	language = language.lower()
	if language in _CODES_LOWER:
		return _CODES_LOWER[language]
	return LANGUAGES.get(language)

async def fetch_translation(text: str, target: str) -> tuple[Optional[str], Optional[discord.Embed]]:
	"""
	Calls the Google Translate endpoint with sl=auto (auto-detect source).
	Uses a browser User-Agent and tries clients in random order, failing over
	to the next client with a brief backoff when rate limited (HTTP 429).
	Returns (translated_text, error_embed).
	"""
	session = await get_http_session()
	headers = {'User-Agent': USER_AGENT}
	clients = CLIENTS.copy()
	random.shuffle(clients)

	for attempt, client in enumerate(clients):
		if attempt > 0:
			await asyncio.sleep(RETRY_DELAY)

		params = {
			'client': client,
			'dt': 't',
			'sl': 'auto',
			'tl': target,
			'q': text,
		}

		async with session.get(TRANSLATE_URL, params=params, headers=headers, timeout=TRANSLATE_TIMEOUT) as resp:
			if resp.status == 429:
				continue  # Rate limited - back off and fail over to the next client
			if resp.status != 200:
				return None, error_embed(
					f"Translation service returned HTTP {resp.status}.",
					title="❌ API Error"
				)
			data = await resp.json(content_type=None)

		try:
			translated = ''.join(segment[0] for segment in data[0] if segment[0])
		except (TypeError, IndexError, KeyError):
			return None, error_embed("Could not parse the translation response.", title="❌ Invalid Response")

		if not translated:
			return None, error_embed("The translation service returned nothing.", title="❌ Empty Translation")

		return translated, None

	return None, error_embed(
		"Rate limited by the translation service (HTTP 429). Please try again in a bit.",
		title="⏳ Rate Limited"
	)

async def handle_translate(
	user: discord.User,
	args: list[str],
	reply: Optional[discord.MessageReference] = None,
	message: Optional[discord.Message] = None
) -> Union[str, discord.Embed]:
	"""
	Handles the ;;tr command.
	Detects the source language of the replied-to message and translates it
	into the given language (name or code).
	"""
	if len(args) != 2:
		return warning_embed("Usage: `;;tr <language>` and reply to a message.", title="⚠️ Wrong Arguments")

	if reply is None or not hasattr(reply, 'resolved') or reply.resolved is None:
		return warning_embed("You need to reply to a message to use this command.", title="⚠️ No Message")

	text = reply.resolved.content.strip() if reply.resolved.content else ''
	if not text:
		return warning_embed("Cannot translate an empty message or a message with only attachments.", title="⚠️ No Text Found")

	target = resolve_language(args[1])
	if not target:
		return warning_embed(
			f"Unknown language: `{args[1]}`. Use a language name (e.g. `french`) or code (e.g. `fr`).",
			title="⚠️ Unknown Language"
		)

	try:
		translated, err_embed = await fetch_translation(text, target)
		if err_embed:
			return err_embed
		return translated

	except aiohttp.ClientError as e:
		return error_embed(f"Network error communicating with translation service: {e}", title="🌐 Network Error")
	except Exception as e:
		return error_embed(f"Translation failed: {e}", title="❌ Error")


__all__ = ['handle_translate', 'resolve_language', 'LANGUAGES', 'CLIENTS']
