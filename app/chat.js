function randomString(len) {
  const chars = '0123456789abcdefghijklmnopqrstuvwxyz';
  const str = [];
  for (let i = 0; i < len; i++) {
    str.push(chars[Math.floor(Math.random() * 1000) % chars.length]);
  }
  return str.join('');
}



function ChatApp({host='ws://localhost:8000', debug=true, clientId=randomString(8)}={}) {
  if (!(this instanceof ChatApp)) {
    throw 'ChatApp requires new keyword';
  }

  this.clientId = clientId;


  function log(m) {
    if (debug) {
      console.log(m);
    }
  }

  function createElements() {
    const appEle = document.getElementById('app');
    const chatPane = document.createElement('div');
    chatPane.id = 'chatPane';
    
    const header = document.createElement('h1');
    header.innerText = 'Chat App';
    chatPane.appendChild(header);
    
    const messagePane = document.createElement('div');
    messagePane.id = 'messagePane';
    chatPane.appendChild(messagePane);

    const controlPane = document.createElement('div');
    controlPane.id = 'controlPane';
    chatPane.appendChild(controlPane);

    const chatSuggestPane = document.createElement('div');
    chatSuggestPane.id = 'chatSuggestPane';
    controlPane.appendChild(chatSuggestPane);
    
    const chatTextarea = document.createElement('textarea');
    chatTextarea.id = 'chatTextarea';
    controlPane.appendChild(chatTextarea);

    appEle.appendChild(chatPane);

    return {messagePane, chatTextarea}
  }

  const {messagePane, chatTextarea} = createElements();
  this.ws = null;
  this.wsOpenAttempt = 0;
  this.queue = [];

  this.onWsOpen = () => {
    log(`connected after ${this.wsOpenAttempt} attempts`);
    this.sendWsMessage({'type': 'open'});
    while(this.queue.length > 0) {
      webSocket.send(this.queue[0]);
      this.queue = queue.slice(1);
    }
    this.wsOpenAttempt = 0;
  };

  this.onWsClose = () => {
    log("closed socket");
    if (this.ws) {
      this.ws = null;
      this.openWs(0)();
    }
  }

  this.onWsError = () => {
    log("socket error");
    this.ws = null;
    this.openWs(0)();
  }

  this.sendWsMessage = (message) => {
    message['cid'] = this.clientId;
    const content = JSON.stringify(message);
    if (!this.ws) {
      this.queue.push(content);
    } else {
      try {
        this.ws.send(content);
      } catch {
        // todo: should only catch related to network error
        this.queue.push(content);
      }
    }
  }

  this.onWsMessage = () => {
    try {
      let message = JSON.parse(event.data);
      switch (message.type) {
        case 'create_message': {
          const self = this.clientId === message.cid;
          let outerDiv = document.createElement('div');
          let innerDiv = document.createElement('div');
          let textP = document.createElement('p');

          outerDiv.appendChild(innerDiv);
          innerDiv.appendChild(textP);
          if (!self) {
            let metaP = document.createElement('p');
            innerDiv.appendChild(metaP);
            metaP.classList.add('messageMeta');
            metaP.innerText = message.cid;
          }
          textP.innerText = message.text;
          innerDiv.classList.add('message');
          innerDiv.classList.add(self ? 'messageOurs' : 'messageTheirs');
          messagePane.prepend(outerDiv);
          outerDiv.scrollIntoView({behavior: "smooth", block: "end", inline: "nearest"});
          break;
        }
        default: {
          log(`unhandled message ${event.data}`);
        }
      }
    } catch {
      log(`unparsable message ${event.data}`);
    }
  }

  function createWebsocket(onerror, onopen, onmessage, onclose) {
    let webSocket = new WebSocket(`${host}/api/chat/ws`);
    webSocket.onerror = onerror;
    webSocket.onopen = onopen;
    webSocket.onmessage = onmessage;
    webSocket.onclose = onclose;
    return webSocket;
  }

  this.openWs = (attempt) => () => {
    if (!this.ws && attempt == this.wsOpenAttempt) {
      this.ws = createWebsocket(this.onWsError, this.onWsOpen, this.onWsMessage, this.onWsClose);
      this.wsOpenAttempt += 1;
      setTimeout(this.openWs(this.wsOpenAttempt), Math.max(Math.pow(this.wsOpenAttempt, 2) * 10, 2000));
    }
  };

  chatTextarea.addEventListener("keyup", event => {
    if (event.key == "Enter" && !event.shiftKey) {
      let val = chatTextarea.value;
      if (val.startsWith("\\")) {
        args = val.substring(1).trim().split(/\s+/);
        this.sendWsMessage({type: 'execute_command', args});
      } else {
        this.sendWsMessage({type: 'create_message', text: val});
      }
      chatTextarea.value = '';
    }
  });

  this.openWs(this.wsOpenAttempt)();
}

const app = new ChatApp();