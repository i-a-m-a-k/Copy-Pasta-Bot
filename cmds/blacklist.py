import constants
import do_not_push

# def _is_admin(func:callable)-> callable:
# 	def func_wrapper(user_id:str, args:list):
# 		if user_id in do_not_push.ADMINS:
# 			return func(user_id, args)
# 		else:
# 			return constants.ADMIN_ONLY

# 	return func_wrapper

def _validate_id(func:callable) -> callable:
	def func_wrapper(user_id:str):
		if user_id[:2] == '<@' and user_id[-1] == '>':
			return func(int(user_id[2:-1]))
		else:
			return constants.WRONG_ARGS

	return func_wrapper

def is_blacklisted(user_id: int) -> bool:
	return user_id not in do_not_push.BLACKLIST

# @_is_admin
def handle_blacklist(user_id: str, args: list) -> str:
	# user_id is the person who called the command
	match args[1]:
		case 'add':
			return _blacklist_add(args[2])

		case 'remove':
			return _blacklist_remove(args[2])

		case 'list':
			return _blacklist_list()

		case _:
			return constants.WRONG_ARGS

@_validate_id
def _blacklist_add(user_id_to_blacklist:int) -> str:
	if user_id_to_blacklist in do_not_push.ADMINS:
		return constants.BLACKLIST_NO_FOUL
	if user_id_to_blacklist in do_not_push.BLACKLIST:
		return constants.BLACKLISTED_AlREADY

	do_not_push.BLACKLIST.add(user_id_to_blacklist)
	return constants.BLACKLIST_SUCCESS + f'<@{user_id_to_blacklist}>'

@_validate_id
def _blacklist_remove(user_id_to_unblacklist:int) -> str:
	if user_id_to_unblacklist not in do_not_push.BLACKLIST:
		return constants.NOT_BLACKLISTED

	do_not_push.BLACKLIST.remove(user_id_to_unblacklist)
	return constants.UNBLACKLIST_SUCCESS + f'<@{user_id_to_unblacklist}>'

def _blacklist_list() -> str:
	return '- ' + '\n- '.join([f'<@{i}>' for i in do_not_push.BLACKLIST]) if do_not_push.BLACKLIST else constants.BLACKLIST_EMPTY
