- long poll on chat topic
  - chat topic backed by either
    - async in memory queue
    - redis client which is async
- send command
  - command runs async, publishes to the chat topic
 
____________

- autocomplete for commands