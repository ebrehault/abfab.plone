from zope.interface import implementer
from zope.component import provideUtility
from zope.publisher.interfaces import IPublishTraverse
from souper.soup import get_soup, Record
from souper.interfaces import ICatalogFactory
from repoze.catalog.query import Eq
from plone import api
from datetime import datetime
from pathlib import Path
from .catalog import CatalogFactory
import json
import mimetypes

ABFAB_ROOT = '/++api++/~'

@implementer(IPublishTraverse)
class AbFabTraverser(object):

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.path = []
        provideUtility(CatalogFactory(), ICatalogFactory, name='abfab')
        self.soup = get_soup('abfab', context)

    def publishTraverse(self, request, name):
        self.path.append(name)
        return self
    
    def __call__(self):
        method = getattr(self, self.request.method, None)
        if method:
            return method()
        else:
            self.request.response.setStatus(405)
            return "Method not allowed"

    def GET(self):
        path = self.get_path()
        accept = self.request.get_header('Accept')
        if path.endswith('/@basic'):
            return self.view_basic(self.get_path(raw=False))
        if path.endswith('/@edit-data'):
            obj = self.get_object(self.get_path(raw=False))
            if obj:
                return self.view_source(obj, 'text/plain')
            else:
                data = self.view_basic(self.get_path(raw=False))
                return json.dumps(data)
        if path.endswith('/@edit'):
            path = self.get_path(raw=False)
            editor_component = self.get_object('/abfab/editor/editor.svelte')
            return self.wrap_component(editor_component, path + '/@edit-data', 'text')
        if path.endswith('.svelte') and 'raw' not in self.request:
            path += '.js'
            js_component = self.get_object(path)
            if "text/html" in accept:
                return self.wrap_component(js_component, None)
            else:
                return self.view_source(js_component)
        object = self.get_object(path)
        if object:
            if 'application/json' in accept:
                return self.view_json(object)
            else:
                return self.view_source(object)
        else:
            js = self.get_object(path + '.js')
            if js:
                return self.request.response.redirect(ABFAB_ROOT + path + '.js')
            index_mjs = self.get_object(path + '/index.mjs')
            if index_mjs:
                return self.request.response.redirect(ABFAB_ROOT + path + '/index.mjs')
            index_js = self.get_object(path + '/index.js')
            if index_js:
                return self.request.response.redirect(ABFAB_ROOT + path + '/index.js')
            package = self.get_object(path + '/package.json')
            if package:
                packageJson = json.loads(package.attrs['file'])
                module = packageJson.get('module', None)
                if module:
                    return self.request.response.redirect(ABFAB_ROOT + path + '/' + module)
            self.request.response.setStatus(404)
            return "Record not found"
    
    def POST(self):
        if can_manage(self.request) is False:
            return
        body = self.request.get('BODY')
        data = json.loads(body)
        id = data.get('id', None)
        if not id:
            self.request.response.setHeader('Content-Type', 'application/json')
            self.request.response.setStatus(400)
            return {"error": "id is missing"}
        path = "/".join([''] + self.path + [id])
        existing = False
        record = self.get_object(path)
        if record:
            existing = True
        else:
            record = Record()
            record.attrs["path"] = path
        for key, value in data.items():
            record.attrs[key] = value
        if not existing:
            self.soup.add(record)
        self.set_last_modified()
        self.request.response.setHeader('Content-Type', 'application/json')
        return {"path": path}
    
    def PATCH(self):
        if can_manage(self.request) is False:
            return
        body = self.request.get('BODY')
        data = json.loads(body)
        path = self.get_path()
        record = self.get_object(path)
        if not record:
            self.request.response.setStatus(404)
            return "Record not found"
        for key, value in data.items():
            record.attrs[key] = value
        self.set_last_modified()
        self.request.response.setHeader('Content-Type', 'application/json')
        return {"path": path}
    
    def DELETE(self):
        if can_manage(self.request) is False:
            return
        path = self.get_path()
        for resource in self.soup.query(Eq('path', path)):
            del self.soup[resource]

    def HEAD(self):
        path = self.get_path()
        object = self.get_object(path)
        if object:
            self.request.response.setStatus(200)
            return ""
        else:
            self.request.response.setStatus(404)
            return "Record not found"

    def get_path(self, raw=True):
        path = self.path
        if path[-1] == self.request.method:
            path = path[:-1]
        if not raw and path[-1].startswith('@'):
            path = path[:-1]
        return "/".join([''] + path)
    
    def get_object(self, path):
        search = [r for r in self.soup.query(Eq('path', path))]
        if len(search) == 1:
            return search[0]
        elif len(search) == 0:
            return None
        else:
            exact = [obj for obj in search if obj.attrs['path'] == path]
            if len(exact) == 1:
                return exact[0]
            else:
                return None

    def wrap_component(self, js_component, path_to_content, type='json'):
        if not js_component:
            self.request.response.setStatus(404)
            return "Not found"
        get_content = ""
        if path_to_content:
            path_to_content = (path_to_content.startswith('/') and ABFAB_ROOT + path_to_content) or path_to_content
            get_content = """import {{API, redirectToLogin}} from '{root}/abfab/core.js';
    let content;
    try {{
        let response = await API.fetch('{path_to_content}');
        content = await response.{type}();
    }} catch (e) {{
        redirectToLogin();
    }}""".format(path_to_content=path_to_content, type=type, root=ABFAB_ROOT)
        else:
            content = self.request.get('content', {})
            get_content = """let content = {content}""".format(content=content)
        body = """<!DOCTYPE html>
    <html lang="en">
    <script type="module">
        import Component from '{root}{component}';
        import Main from '{root}/abfab/main.svelte.js';
        {get_content}
        const component = new Main({{
            target: document.body,
            props: {{content, component: Component}},
        }});
        export default component;
    </script>
    </html>
    """.format(component=js_component.attrs['path'], get_content=get_content, root=ABFAB_ROOT)
        self.request.response.setHeader('Content-Type', 'text/html')
        self.request.response.setHeader('ETag-Type', self.get_last_modified())
        return body

    def view_source(self, object, content_type=None):
        if not object:
            self.request.response.setStatus(404)
            return "Not found"
        if not content_type:
            content_type = mimetypes.guess_type(object.attrs['path'])[0]
        self.request.response.setHeader('Content-Type', content_type)
        return object.attrs['file']
 
    def view_basic(self, path):
        object = self.get_object(path)
        if not object:
            return {"type": "Directory", "path": path}
        else:
            return {"type": "File", "path": path}

    def view_json(self, object):
        self.request.response.setHeader('Content-Type', 'application/json')
        if not object:
            self.request.response.setStatus(404)
            return {"error": "Not found"}
        return dict(object.attrs.items())

    def get_last_modified(self):
        return api.portal.get_registry_record('abfab.last_modified')
    
    def set_last_modified(self):
        return api.portal.set_registry_record('abfab.last_modified', datetime.now().isoformat())


class Reset(object):
    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self):
        if can_manage(self.request) is False:
            return
        soup = get_soup('abfab', self.context)
        provideUtility(CatalogFactory(), ICatalogFactory, name='abfab')
        soup.clear()


class Tree(object):
    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self):
        soup = get_soup('abfab', self.context)
        provideUtility(CatalogFactory(), ICatalogFactory, name='abfab')
        search = [r for r in soup.query(Eq('path', '/'))]
        results = self.get_path_dict([r.attrs['path'] for r in search])
        self.request.response.setHeader('Content-Type', 'application/json')
        return json.dumps(results)
    
    def get_path_dict(self, paths):
        """Builds a tree like structure out of a list of paths"""
        def _recurse(dic, fullpath, chain):
            if len(chain) == 0:
                return
            if len(chain) == 1:
                dic[chain[0]] = {"type": "File", "path": fullpath}
                return
            key, *new_chain = chain
            if key not in dic:
                dic[key] = {}
            _recurse(dic[key], fullpath, new_chain)
            return

        new_path_dict = {}
        for path in paths:
            _recurse(new_path_dict, path, Path(path).parts)
        return new_path_dict

def can_manage(request):
    user = api.user.get_current()
    if not api.user.has_permission('Manage portal', user=user):
        request.response.setStatus(403)
        return False
    return True