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
    body { font-family: sans-serif; padding: 2em; background: #f4f4f9; color: #333; }
    form, .list-selector { margin-bottom: 1em; }
    input[type="text"] { padding: 0.5em; width: 200px; }
    button { padding: 0.5em; margin-left: 0.5em; }
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
  <h2>Realtime Todo List</h2>

  <div class="list-selector">
    <label for="list">Select List:</label>
    <select id="list"></select>
    <input type="text" id="newlist" placeholder="New list">
    <button onclick="createList()">Create</button>
  </div>

  <form id="form">
    <input type="text" id="newtodo" autocomplete="off" placeholder="New todo">
    <button type="submit">Add</button>
  </form>

  <ul id="todolist"></ul>

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

      const selector = document.getElementById('list');
      selector.innerHTML = '';
      lists.forEach(name => {
        const option = document.createElement('option');
        option.value = name;
        option.textContent = name;
        if (name === currentList) option.selected = true;
        selector.appendChild(option);
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

    function createList() {
      const input = document.getElementById('newlist');
      const name = input.value.trim();
      if (name) {
        currentList = name;
        socket.emit('create_list', name);
        input.value = '';
      }
    }

    document.getElementById('list').addEventListener('change', (e) => {
      currentList = e.target.value;
      socket.emit('switch_list', currentList);
    });
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
