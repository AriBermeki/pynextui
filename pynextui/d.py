import os
import time
import inspect
import jwt
from pathlib import Path
from fastapi import FastAPI, Request, File, UploadFile
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
import shutil
import json
from distutils.command.upload import upload
import uuid
import jwt
import inspect
import os
import time
from pathlib import Path
from inspect import signature
from .page import Page
from .element import Element
from typing import Optional, Dict
import platform
import asyncio

if platform.system() == 'Windows':
   asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

class CallbackRegistryType:
    uuid_callback_map = {}
    callback_uuid_map = {}
    def uuid_for_callback(self, callback):
        if callback is None:
            return None
        if callback in self.callback_uuid_map:
            return self.callback_uuid_map[callback]
        else:
            cb_uuid = str(uuid.uuid1())
            self.uuid_callback_map[cb_uuid] = callback
            self.callback_uuid_map[callback] = cb_uuid
            return cb_uuid
    def make_callback(self, uuid, args):
        if uuid in self.uuid_callback_map:
            method = self.uuid_callback_map[uuid]
            param_length = len(signature(method).parameters)
            return method(*args[:param_length])
        else:
            # TODO: Return an error to the frontend
            return None

callbackRegistry = CallbackRegistryType()

class MenuItem(Element):
    """Represents a menu item
    
        Args:
            name (str): the title of the menu
            url (str, optional): the url the menu will navigate to. Defaults to ''.
            icon (str, optional): the icon of the menu. See https://ant.design/components/icon/. Defaults to None.
            auth_needed (str, optional): the permission needed for user to access this page. e.g. 'user' or 'admin'
            children (list, optional): set this if the menu has a sub-menu. Defaults to [].
    """
    def __init__(self, name, url='', icon=None, auth_needed=None, children=[]):
        self.name = name
        self.url = url
        self.icon = icon
        self.auth_needed = auth_needed
        self.children = children
    def has_auth(self, auth=[]):
        if self.auth_needed is None or self.auth_needed in auth:
            return True
        else:
            return False
    def as_dict(self, auth=[]):
        return {
            'name': self.name,
            'path': self.url,
            'icon': self.icon,
            'component': './index',
            'children': [x.as_dict(auth) for x in self.children if x.has_auth(auth)]
        }

DEFAULT_AVATAR = 'https://gw.alipayobjects.com/zos/antfincdn/XAosXuNZyF/BiazfanxmamNRoxxVxka.png'
class LoggedInUser(Element):
    """Returned by login handler, represent a successfully logged in user.
    
    Args:
        display_name: the display name of the user
        auth: a list of permission string the user have. Will be checked against in pages or menus
        avatar: the avatar of the user
        user_info: info for future use, accessible by app.current_user()['user_info']
    """
    def __init__(self, display_name='', auth=['user'], avatar=DEFAULT_AVATAR, user_info=None, redirect_to=None):
        token = jwt.encode({
            "display_name": display_name,
            "auth": auth,
            "user_info": user_info
        }, AdminApp.SECRET, algorithm='HS256')
        super().__init__('LoginAndNavigateTo', status='ok', display_name=display_name, avatar=avatar, redirect_to=redirect_to, token=token)

class LoginFailed(Element):
    """Returned by login handler, represent a failed login attempt
    
    Args:
        title: the title shown in the error message. default: 'Login Failed'
        message: the error message content. default: 'Username or password is incorrect'
    """
    def __init__(self, title="Login Failed", message="Username or password is incorrect"):
        super().__init__('LoginFailed', status='error', error=message, title=title)

class ErrorResponse(Element):
    def __init__(self, title="Something Got Wrong", message="You encountered an Error", error_type="error"):
        super().__init__('Error', status='error', message=message, title=title, error_type=error_type)


class AdminApp(FastAPI):
    SECRET = "admin ui super &*#*$ secret"

    def __init__(self, upload_folder=None):
        super().__init__()
        self.app_title = None
        self.copyright_text = None
        self.footer_links = None
        self.register_link = None
        self.forget_password_link = None
        self.app_logo = None
        self.app_favicon = None
        self.app_styles = None
        self.static_files = {}

        if upload_folder is None:
            frame = inspect.stack()[1]
            module = inspect.getmodule(frame[0])
            upload_folder = os.path.join(os.path.dirname(os.path.abspath(module.__file__)), 'upload')
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        self.upload_folder = upload_folder
        self.pages = {}
        self.menu = []
        self.on_login = {}

        self.init_fastapi_routes()
    
    def config(self,
        app_title: str = 'Admin UI App',
        copyright_text: str = 'Professional UI with Python',
        footer_links: Dict[str, str] = {'Github': 'https://github.com/bigeyex/python-adminui', 'Ant Design': 'https://ant.design'},
        register_link: Optional[str] = None,
        forget_password_link: Optional[str] = None,
        app_logo: Optional[str] = None,
        app_favicon: Optional[str] = None,
        app_styles: Dict[str, str] = {'nav_theme': 'dark', 'layout': 'sidemenu'},
        static_files: Dict[str, str] = {}
    ):
        self.app_favicon =app_favicon
        self.static_files =static_files
        self.serve_setting = self.jsonify({'title': app_title, 'appLogo': app_logo, 'copyrightText': copyright_text,
                             'footerLinks': footer_links, 'navTheme': app_styles['nav_theme'], 'layout': app_styles['layout'],
                             'forgetPasswordLink': forget_password_link, 'registerLink': register_link})

    def page(self, url, name, auth_needed=None):
        def decorator(func):
            self.pages[url] = Page(url, name, builder=func, auth_needed=auth_needed)
        return decorator

    def login(self, method='password'):
        def decorator(func):
            self.on_login[method] = func
        return decorator

    def set_menu(self, menu):
        self.menu = menu

    def current_user(self, request=None):
        auth_header = self.get_header('Authorization', request)
        if auth_header is not None:
            return jwt.decode(bytes(auth_header, 'utf-8'), AdminApp.SECRET, algorithms=['HS256'])
        else:
            return {'display_name': None, 'auth': [], 'user_info': None}

    async def serve_page(self, url='', request=None):
        def has_permission(page):
            return page.auth_needed is None or page.auth_needed in self.current_user(request)['auth']

        url_parts = url.split('/')
        full_url = '/' + url
        base_url = '/' + url_parts[0]
        args = self.get_url_args(request)
        if full_url in self.pages:
            if has_permission(self.pages[full_url]):
                return self.jsonify(self.pages[full_url].as_list(all_params=args))
            else:
                return ErrorResponse("No Permission", "Please login first or contact your administrator", "403").as_dict()
        elif base_url in self.pages and len(url_parts) > 1:
            if has_permission(self.pages[base_url]):
                return self.jsonify(self.pages[base_url].as_list(url_parts[1], all_params=args))
            else:
                return ErrorResponse("No Permission", "Please login first or contact your administrator", "403").as_dict()
        else:
            return ErrorResponse("Page not Found", error_type="404").as_dict()

    async def handle_page_action(self, request=None):
        msg = await self.get_request_json(request)
        if 'args' not in msg:
            msg['args'] = []
        response = callbackRegistry.make_callback(msg['cb_uuid'], msg['args'])
        if response is not None:
            return self.jsonify(response)
        else:
            return ErrorResponse("No Action", error_type="204").as_dict()

    async def handle_login_action(self, request=None):
        msg = await self.get_request_json(request)
        if 'password' in self.on_login:
            return self.on_login['password'](msg['username'], msg['password']).as_dict()
        else:
            return ErrorResponse("Login type not supported", error_type="501").as_dict()

    def serve_menu(self, request=None):
        token = self.current_user(request)
        return self.jsonify({
            'menu': [x.as_dict() for x in self.menu if x.has_auth(token['auth'])]
        })

    def serve_settings(self):
        return self.serve_setting 

    def serve_root(self, path=''):
        return FileResponse(os.path.join(Path(__file__).parent.absolute(), "static", "index.html"))

    def serve_favicon(self, path=''):
        if self.app_favicon is not None:
            return FileResponse(path)
        else:
            return FileResponse(os.path.join(Path(__file__).parent.absolute(), "static", "favicon.png"))

    async def serve_upload_fastapi(self, upload: UploadFile):
        with open(os.path.join(self.upload_folder, upload.filename), 'wb') as buffer:
            shutil.copyfileobj(upload.file, buffer)
        return upload.filename

    def uploaded_file_name(self, uploaded_file):
        if 'file_name' in uploaded_file:
            return uploaded_file['file_name']
        elif 'response' in uploaded_file:
            return uploaded_file['response']
        elif 'file' in uploaded_file:
            return self.uploaded_file_name(uploaded_file['file'])
        else:
            return None

    def uploaded_file_location(self, uploaded_file):
        return os.path.join(self.upload_folder, self.uploaded_file_name(uploaded_file))

    def run(self, *args, **kwargs):
        import uvicorn
        uvicorn.run(self, *args, **kwargs)

    def init_fastapi_routes(self):
        class ElementJSONEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, Element):
                    return obj.as_dict()

        self.jsonify = lambda x: Response(content=json.dumps(x, cls=ElementJSONEncoder), media_type='application/json')

        async def get_request_json_method(request):
            return await request.json()

        self.get_request_json = get_request_json_method
        self.get_header = lambda name, request: request.headers[name] if name in request.headers else None
        self.get_url_args = lambda request: request.query_params._dict

        @self.get('/favicon.png')
        async def get_favicon():
            return self.serve_favicon()

        @self.get('/api/page_layout/{page_path:path}')
        async def get_page_layout(page_path: str, request: Request):
            return await self.serve_page(page_path, request)

        @self.get('/api/main_menu')
        def get_main_menu(request: Request):
            return self.serve_menu(request)

        @self.get('/api/app_settings')
        def get_app_settings():
            return self.serve_settings()

        @self.post("/api/upload")
        async def post_upload(upload: UploadFile = File(...)):
            return await self.serve_upload_fastapi(upload)

        @self.post('/api/login')
        async def post_login_action(request: Request):
            return await self.handle_login_action(request)

        @self.post('/api/page_action')
        async def post_page_action(request: Request):
            return await self.handle_page_action(request)

        for path_name, file_path in self.static_files.items():
            self.mount(path_name, StaticFiles(directory=file_path, html=True), name=path_name)

        self.mount("/", StaticFiles(directory=os.path.join(Path(__file__).parent.absolute(), "static"), html=True), name="static")

        @self.exception_handler(StarletteHTTPException)
        async def custom_http_exception_handler(request, exc):
            return FileResponse(os.path.join(Path(__file__).parent.absolute(), "static", "index.html"))

