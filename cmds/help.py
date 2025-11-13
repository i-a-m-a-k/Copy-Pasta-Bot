import utils.Constants as constants

def help(args:list) -> str:
	if len(args) != 2:
		return constants.HELP_TEXT

	match args[1].lower():
		case 'copypasta':
			return constants.HELP_TEXT_CP
		case 'memes':
			return constants.HELP_TEXT_MEMES
		case _:
			return constants.HELP_TEXT
