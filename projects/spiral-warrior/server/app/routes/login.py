from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from app.security.logic_token import issue_logic_token
from app.storage.profile_store import ProfileStore

router = APIRouter()

LOCAL_SERVER = {
    'id': 1,
    'server_id': 1,
    'name': '本地离线服',
    'server_name': '本地离线服',
    'status': 'smooth',
    'host': '10.0.2.2',
    'port': 80,
    'notice': '本地离线保存服务器',
}

LOGIN_RESPONSE = {
    'ok': True,
    'code': 0,
    'result': 0,
    'message': '登录成功',
    'account_id': 'local_player',
    'uid': 'local_player',
    'token': 'local-offline-token',
    'session_id': 'local-offline-session',
    'language': 'zh',
    'servers': [LOCAL_SERVER],
}

@router.api_route('/DHSDK/Action_UserLogin.aspx', methods=['GET', 'POST'])
@router.api_route('/Wbsrv/Check_Login_DH.aspx', methods=['GET', 'POST'])
async def dh_login(request: Request):
    return LOGIN_RESPONSE

@router.api_route('/login/1/', methods=['GET', 'POST'])
@router.api_route('/login/1', methods=['GET', 'POST'])
async def game_login(request: Request):
    return LOGIN_RESPONSE


@router.get('/auth/es')
def apply_logic_server(account: str = "local") -> PlainTextResponse:
    # The retired SDK account is accepted for compatibility; offline mode
    # intentionally maps every request to one stable local preservation save.
    profile = ProfileStore().load("local")
    return PlainTextResponse(issue_logic_token(profile), media_type="text/plain")

@router.api_route('/GetAllEntryFaild', methods=['GET', 'POST'])
async def get_all_entry_failed(request: Request):
    """Chinese client reports failed entry discovery here; keep it harmless."""
    return {'ok': True, 'code': 0, 'message': '本地服务器已接管'}

@router.get('/server/list')
def server_list():
    return {'ok': True, 'servers': [LOCAL_SERVER]}
