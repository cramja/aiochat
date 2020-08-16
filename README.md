# aiochat
 
Sample app using aiohttp. Testing how it is to write an event-loop driven backend in python. So far so good.

____________

```
python -mvirtualenv venv
source venv/bin/activate
pip install -r requirements.txt

export AIO_CONFIG=`pwd`/config-local.json
cd server
adev runserver
```
____________


**To Try**
- fancy markdown editing
  - prosemirror
  - slate
    - prism for syntax highlighting
    - autocomplete for commands [see example](https://www.slatejs.org/examples/mentions)
- postgres for persistence
- redis for message q
  - asyncio redis