# pylint: disable=invalid-name,redefined-builtin
import asyncio
import aiohttp

from .etree import ElementTree


class NotFound(Exception):
    pass


class JSS(object):
    def __init__(self, url, username, password):
        self.url = url
        self.username = username
        self.password = password
        self.auth = aiohttp.BasicAuth(username, password)
        self.session = aiohttp.ClientSession(loop=asyncio.get_event_loop())

    def __del__(self):
        self.session.close()

    async def _get_endpoint(self, endpoint, id=None, name=None):
        base_url = self.url + f'/JSSResource/{endpoint}'
        if id:
            url = base_url + f'/id/{id}'
            async with self.session.get(url, auth=self.auth) as resp:
                if resp.status != 200:
                    raise NotFound
                return await resp.text()
        elif name:
            url = base_url + f'/name/{name}'
            async with self.session.get(url, auth=self.auth) as resp:
                if resp.status != 200:
                    raise NotFound
                return await resp.text()
        else:
            async with self.session.get(base_url, auth=self.auth) as resp:
                if resp.status != 200:
                    raise NotFound
                return await resp.text()

    async def _post_endpoint(self, endpoint, jss_object):
        base_url = self.url + f'/JSSResource/{endpoint}/name'
        base_url += f'/{jss_object.name.text}'
        headers = {'content-type': 'application/xml'}
        try:
            await self._get_endpoint(endpoint, name=jss_object.name.text)
            base_url += f'/{jss_object.name.text}'
            resp = await self.session.put(base_url,
                                          auth=self.auth,
                                          data=jss_object.raw_xml(),
                                          headers=headers)
        except NotFound:
            self.session.post(base_url,
                              auth=self.auth,
                              data=jss_object.raw_xml(),
                              headers=headers)

    async def scripts(self, id=None, name=None):
        data = await self._get_endpoint('scripts', id, name)
        return Script(data, self)

    async def computer_extension_attributes(self, id=None, name=None):
        data = await self._get_endpoint('computerextensionattributes',
                                        id,
                                        name)
        return ExtensionAttribute(data, self)

class JSSObject(object):
    def __init__(self, xml, delegate=None):
        self._root = ElementTree.fromstring(xml)
        self.delegate = delegate

    def __getattr__(self, attr):
        return self._root.__getattr__(attr)

    def save(self):
        raise NotImplementedError

    def delete(self):
        raise NotImplementedError

    def raw_xml(self):
        return ElementTree.tostring(self._root).decode("utf-8") 

class Script(JSSObject):
    def __init__(self, xml, delegate):
        super().__init__(xml, delegate)
    async def save(self):
        await self.delegate._post_endpoint('scripts', self)
    def delete(self):
        raise NotImplementedError

class ExtensionAttribute(JSSObject):
    def __init__(self, xml, delegate):
        super().__init__(xml, delegate)
    async def save(self):
        await self.delegate._post_endpoint('computerextensionattributes',
                                           self)
    def delete(self):
        raise NotImplementedError
