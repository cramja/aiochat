function randomString(len) {
  const chars = '0123456789abcdefghijklmnopqrstuvwxyz';
  const str = [];
  for (let i = 0; i < len; i++) {
    str.push(chars[Math.floor(Math.random() * 1000) % chars.length]);
  }
  return str.join('');
}

function hash(s) {
  var hash = 0, i, chr;
    for (i = 0; i < s.length; i++) {
      chr   = s.charCodeAt(i);
      hash  = ((hash << 5) - hash) + chr;
      hash |= 0; // Convert to 32bit integer
    }
    return hash;
}

function colorOf(s) {
  var palette = ["ffadad","ffd6a5","F7FF0A","caffbf","9bf6ff","a0c4ff","bdb2ff","ffc6ff"];
  let idx = Math.abs(hash(s)) % palette.length;
  console.log(hash(s));
  return "#" + palette[idx];
}


var tabId = sessionStorage.tabId ? sessionStorage.tabId : sessionStorage.tabId = randomString(8);


function ChatApp({host='ws://localhost:8000', debug=true, clientId=null}={}) {
  if (!(this instanceof ChatApp)) {
    throw 'ChatApp requires new keyword';
  }

  this.clientId = clientId;
  if (!this.clientId) {
    this.clientId = tabId;
  }
  if (!this.clientId) {
    this.clientId = randomString(8);
  }


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
    chatTextarea.autofocus = true;
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
    this.sendWsMessage({type: 'open', clientId: this.clientId});
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

  this.createMessageElement = ({clientId, message}) => {
    const self = this.clientId === clientId;
    let outerDiv = document.createElement('div');
    outerDiv.classList.add("message");
    let innerDiv = document.createElement('div');
    let textP = document.createElement('p');

    outerDiv.appendChild(innerDiv);
    innerDiv.appendChild(textP);
    if (!self) {
      let metaP = document.createElement('p');
      innerDiv.appendChild(metaP);
      metaP.classList.add('messageMeta');
      metaP.innerText = clientId;
    }
    textP.innerText = message;
    innerDiv.classList.add('message');
    innerDiv.classList.add(self ? 'messageOurs' : 'messageTheirs');
    innerDiv.style.backgroundColor = colorOf(clientId);
    messagePane.prepend(outerDiv);
    return outerDiv;
  }

  this.onWsMessage = () => {
    try {
      let message = JSON.parse(event.data);
      switch (message.kind) {
        case 'MessageEvent': {
          let outerDiv = this.createMessageElement({clientId: message.client_id, message: message.message});
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
      if (/\\\w+(\w+\s*)*/.test(val)) {
        args = val.substring(1).trim().split(/\s+/);
        if (args[0] === 'clear') {
          document.querySelectorAll(".message").forEach(e => e.parentNode.removeChild(e));
        }
        this.sendWsMessage({type: 'execute_command', args});
      } else {
        this.sendWsMessage({type: 'create_message', text: val.trim()});
      }
      chatTextarea.value = '';
    }
  });

  this.fetchHistory = () => {
    fetch('/api/chat/history')
      .then(r => r.json())
      .then(r => {
        let outerDiv;
        for (message of r) {
          outerDiv = this.createMessageElement({message: message.value, clientId: message.client_id});
        }
        outerDiv.scrollIntoView({behavior: "smooth", block: "end", inline: "nearest"});
      }).finally(() => this.openWs(this.wsOpenAttempt)());
  }

  this.fetchHistory();

}

const app = new ChatApp();