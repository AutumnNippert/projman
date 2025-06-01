from flask import Flask, render_template_string, request, jsonify
from flask_socketio import SocketIO, emit
import json
import os
import html

app = Flask(__name__)
socketio = SocketIO(app)

DATA_FILE = 'todos.json'

def load_todos():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    return {"default": []}

def save_todos():
    with open(DATA_FILE, 'w') as f:
        json.dump(todos, f)

# Load existing todos on startup
todos = load_todos()
current_list = "default"
todos.setdefault(current_list, [])

HTML = """
<!doctype html>
<html>
<head>
  <title>Realtime Todo List</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.5.4/socket.io.min.js"></script>
  <style>
    body { font-family: sans-serif; margin: 0; background: #f4f4f9; color: #333; }
    header {
      display: flex;
      align-items: center;
      background: #333;
      color: white;
      padding: 1em;
      justify-content: space-between;
    }
    .tabs {
      display: flex;
      gap: 0.5em;
    }
    .tab {
      background: #444;
      border: none;
      color: white;
      padding: 0.5em 1em;
      border-radius: 5px;
      cursor: pointer;
    }
    .tab.active {
      background: #fff;
      color: #333;
    }
    .add-tab {
      font-size: 1.4em;
      background: #555;
      color: #ddd;
      border: none;
      border-radius: 50%;
      width: 32px;
      height: 32px;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
    }
    main { padding: 2em; }
    form { margin-bottom: 1em; display: flex; align-items: center; gap: 0.5em; }
    input[type="text"] { padding: 0.5em; width: 200px; }
    .add-btn {
      background: none;
      border: none;
      cursor: pointer;
      color: #080;
      font-size: 1.2em;
      transition: background 0.2s;
      padding: 0.5em;
      border-radius: 4px;
    }
    .add-btn:hover {
      background: #dfd;
    }
    ul { list-style-type: none; padding: 0; }
    li { margin: 0.5em 0; background: white; padding: 0.5em; border-radius: 5px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); display: flex; align-items: center; justify-content: space-between; }
    .done { text-decoration: line-through; color: #888; }
    .delete-btn {
      background: none;
      border: none;
      cursor: pointer;
      color: #c00;
      font-size: 1em;
      transition: background 0.2s;
    }
    .delete-btn:hover {
      background: #fdd;
      border-radius: 4px;
    }
    .delete-btn::after {
      content: '\1F5D1';
      font-size: 1.2em;
    }
  </style>
</head>
<body>
  <header>
    <div class="tabs" id="tabbar"></div>
    <button class="add-tab" title="Create new list" onclick="promptNewList()">+</button>
  </header>
  <main>
    <form id="form">
      <input type="text" id="newtodo" autocomplete="off" placeholder="New todo">
      <button class="add-btn" type="submit" title="Add task">+</button>
    </form>
    <ul id="todolist"></ul>
  </main>

  <script>
    const socket = io();
    let currentList = "default";

    function escapeHTML(str) {
      return str.replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/\"/g, '&quot;')
                .replace(/'/g, '&#039;');
    }

    function renderTodos(data) {
      const { todos, lists } = data;
      const list = document.getElementById('todolist');
      list.innerHTML = '';
      todos.forEach((todo, index) => {
        const li = document.createElement('li');
        li.innerHTML = `
          <span>
            <input type="checkbox" ${todo.done ? 'checked' : ''} onchange="toggle(${index})">
            <span class="${todo.done ? 'done' : ''}">${escapeHTML(todo.text)}</span>
          </span>
          <button class="delete-btn" title="Delete task" onclick="remove(${index})"></button>
        `;
        list.appendChild(li);
      });

      const tabbar = document.getElementById('tabbar');
      tabbar.innerHTML = '';
      lists.forEach(name => {
        const button = document.createElement('button');
        button.className = 'tab' + (name === currentList ? ' active' : '');
        button.textContent = name;
        button.onclick = () => {
          currentList = name;
          socket.emit('switch_list', name);
        };
        tabbar.appendChild(button);
      });
    }

    socket.on('todos', renderTodos);

    document.getElementById('form').onsubmit = (e) => {
      e.preventDefault();
      const input = document.getElementById('newtodo');
      if (input.value.trim()) {
        socket.emit('add_todo', { list: currentList, text: input.value.trim() });
        input.value = '';
      }
    };

    function toggle(index) {
      socket.emit('toggle_todo', { list: currentList, index });
    }

    function remove(index) {
      socket.emit('remove_todo', { list: currentList, index });
    }

    function promptNewList() {
      const name = prompt("Enter new list name:");
      if (name) {
        currentList = name;
        socket.emit('create_list', name);
      }
    }
  </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML)

@socketio.on('connect')
def handle_connect():
    emit('todos', {'todos': todos[current_list], 'lists': list(todos.keys())})

@socketio.on('switch_list')
def handle_switch(name):
    global current_list
    current_list = name
    todos.setdefault(current_list, [])
    emit('todos', {'todos': todos[current_list], 'lists': list(todos.keys())}, broadcast=True)

@socketio.on('create_list')
def handle_create(name):
    global current_list
    current_list = name
    if name not in todos:
        todos[name] = []
    save_todos()
    emit('todos', {'todos': todos[current_list], 'lists': list(todos.keys())}, broadcast=True)

@socketio.on('add_todo')
def handle_add(data):
    name = data['list']
    text = str(data['text']).strip()[:256]
    text = html.escape(text)
    todos.setdefault(name, []).append({'text': text, 'done': False})
    save_todos()
    emit('todos', {'todos': todos[name], 'lists': list(todos.keys())}, broadcast=True)

@socketio.on('toggle_todo')
def handle_toggle(data):
    name = data['list']
    index = data['index']
    if 0 <= index < len(todos.get(name, [])):
        todos[name][index]['done'] = not todos[name][index]['done']
        save_todos()
        emit('todos', {'todos': todos[name], 'lists': list(todos.keys())}, broadcast=True)

@socketio.on('remove_todo')
def handle_remove(data):
    name = data['list']
    index = data['index']
    if 0 <= index < len(todos.get(name, [])):
        todos[name].pop(index)
        save_todos()
        emit('todos', {'todos': todos[name], 'lists': list(todos.keys())}, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0')
