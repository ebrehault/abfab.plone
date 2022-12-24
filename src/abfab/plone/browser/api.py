from zope.interface import implementer
from zope.component import provideUtility
from zope.publisher.interfaces import IPublishTraverse
from souper.soup import get_soup, Record
from souper.interfaces import ICatalogFactory
from repoze.catalog.query import Eq
from plone import api
from datetime import datetime
from .catalog import CatalogFactory
import json
import mimetypes

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
            self.request.response.setStatus(404)
            return "Record not found"
    
    def POST(self):
        body = self.request.get('BODY')
        data = json.loads(body)
        id = data.get('id', None)
        if not id:
            self.request.response.setHeader('Content-Type', 'application/json')
            self.request.response.setStatus(400)
            return {"error": "id is missing"}
        path = "/".join([''] + self.path + [id])
        record = self.get_object(path) or Record()
        record.attrs["path"] = path
        for key, value in data.items():
            record.attrs[key] = value
        self.soup.add(record)
        self.set_last_modified()
        self.request.response.setHeader('Content-Type', 'application/json')
        return {"path": path}
    
    def DELETE(self):
        path = self.get_path()
        for resource in self.soup.query(Eq('path', path)):
            del self.soup[resource]

    def get_path(self):
        path = self.path
        if path[-1] == self.request.method:
            path = path[:-1]
        return "/".join([] + path)
    
    def get_object(self, path):
        search = [r for r in self.soup.query(Eq('path', path))]
        if len(search) > 0:
            # TODO: return the best match (like index.js, index.html, etc.)
            return search[0]
        else:
            return None

    def wrap_component(self, js_component, path_to_content, type='json'):
        if not js_component:
            self.request.response.setStatus(404)
            return "Not found"
        get_content = ""
        if path_to_content:
            path_to_content = (path_to_content.startswith('/') and "/~" + path_to_content) or path_to_content
            get_content = """import {{API, redirectToLogin}} from '/~/abfab/core.js';
    let content;
    try {{
        let response = await API.fetch('{path_to_content}');
        content = await response.{type}();
    }} catch (e) {{
        redirectToLogin();
    }}""".format(path_to_content=path_to_content, type=type)
        else:
            content = self.request.get('content', {})
            get_content = """let content = {content}""".format(content=content)
        body = """<!DOCTYPE html>
    <html lang="en">
    <script type="module">
        import Component from '/~{component}';
        import Main from '/~/abfab/main.svelte.js';
        {get_content}
        const component = new Main({{
            target: document.body,
            props: {{content, component: Component}},
        }});
        export default component;
    </script>
    </html>
    """.format(component=js_component.attrs['path'], get_content=get_content)
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
        soup = get_soup('abfab', self.context)
        provideUtility(CatalogFactory(), ICatalogFactory, name='abfab')
        soup.clear()