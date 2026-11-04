from .transforms import create_transform_handler
from .puppets import handle_flirt, handle_roast
from .mock import handle_mock
from .deepfry import handle_deepfry
from .dream import handle_dream
from .thonkify import handle_thonkify_command
from .dadjoke import handle_dadjoke
from .cat import handle_cat
from .lmgtfy import handle_lmgtfy
from .translate import handle_translate
from . import regexc

__all__ = [
	'create_transform_handler',
	'handle_flirt',
	'handle_roast',
	'handle_mock',
	'handle_deepfry',
	'handle_dream',
	'handle_thonkify_command',
	'handle_dadjoke',
	'handle_cat',
	'handle_lmgtfy',
	'handle_translate',
	'regexc',
]
