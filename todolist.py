from flask import Flask, render_template_string, request, redirect, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room
import json
import os
import html
import uuid

app = Flask(__name__)
socketio = SocketIO(app)

DATA_FILE = 'todos.json'

# In-memory storage for shared boards
shared_boards = {}


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

TODO_HTML = """
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
    .tabs { display: flex; gap: 0.5em; }
    .tab {
      background: #444;
      border: none;
      color: white;
      padding: 0.5em 1em;
      border-radius: 5px;
      cursor: pointer;
    }
    .tab.active { background: #fff; color: #333; }
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
    main { padding: 2em; position: relative; }
    .search-box { margin-bottom: 1em; }
    .search-box input {
      width: 100%; padding: 0.75em; font-size: 1em;
      border: 1px solid #ccc; border-radius: 6px;
    }
    form {
      margin-bottom: 1em; display: flex; align-items: center;
      border: 1px solid #ccc; border-radius: 6px; overflow: hidden;
    }
    #newtodo {
      flex: 1; padding: 0.75em; border: none; font-size: 1em;
    }
    .add-btn {
      color: #aaa; border: none; font-size: 1.5em;
      width: 48px; height: 100%; cursor: pointer;
    }
    .add-btn:hover { background: #ddd; }
    ul { list-style-type: none; padding: 0; }
    li {
      margin: 0.5em 0; background: white; padding: 0.5em;
      border-radius: 5px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);
      display: flex; align-items: center; justify-content: space-between;
      transition: background 0.2s;
    }
    li:hover { background: #eef; cursor: default; }
    .todo-item { display: flex; align-items: center; gap: 0.5em; flex: 1; }
    .todo-item input[type="checkbox"] { width: 20px; height: 20px; cursor: pointer; }
    .todo-text { flex: 1; }
    .todo-text[contenteditable="true"] { outline: none; }
    .done { text-decoration: line-through; color: #888; }
    .delete-btn {
      background: none; border: none; cursor: pointer;
      color: #c00; font-size: 1em; transition: background 0.2s;
    }
    .delete-btn:hover { background: #fdd; border-radius: 4px; }
    .delete-btn::after { content: 'Delete'; font-size: 1.2em; }
    .new-board-btn {
      position: fixed;
      bottom: 20px;
      right: 20px;
      width: 48px;
      height: 48px;
      font-size: 2em;
      background: #4CAF50;
      color: white;
      border: none;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .new-board-btn:hover {
      background: #45a049;
    }
  </style>
</head>
<body>
  <header>
    <div class="tabs" id="tabbar"></div>
    <button class="add-tab" title="Create new list" onclick="promptNewList()">+</button>
  </header>
  <main>
    <div class="search-box">
      <input type="text" id="search" placeholder="Search todos..." oninput="filterTodos()">
    </div>
    <form id="form">
      <input type="text" id="newtodo" autocomplete="off" placeholder="New todo">
      <button class="add-btn" type="submit" title="Add task">+</button>
    </form>
    <ul id="todolist"></ul>
    <button class="new-board-btn" onclick="location.href='/board'" title="New Shared Board">+</button>
  </main>
  <script>
    const socket = io();
    let currentList = "default";
    let fullTodos = [];

    function escapeHTML(str) {
      return str.replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/\"/g, '&quot;')
                .replace(/'/g, '&#039;');
    }

    function renderTodos(data) {
      fullTodos = data.todos;
      const tabbar = document.getElementById('tabbar');
      tabbar.innerHTML = '';
      data.lists.forEach(name => {
        const button = document.createElement('button');
        button.className = 'tab' + (name === currentList ? ' active' : '');
        button.textContent = name;
        button.onclick = () => {
          currentList = name;
          socket.emit('switch_list', name);
        };
        tabbar.appendChild(button);
      });
      filterTodos();
    }

    function filterTodos() {
      const query = document.getElementById('search').value.toLowerCase();
      const list = document.getElementById('todolist');
      list.innerHTML = '';
      fullTodos.forEach((todo, index) => {
        if (todo.text.toLowerCase().includes(query)) {
          const li = document.createElement('li');
          li.innerHTML = `
            <div class="todo-item">
              <input type="checkbox" ${todo.done ? 'checked' : ''} onchange="toggle(${index})">
              <span class="todo-text ${todo.done ? 'done' : ''}" contenteditable="true" onblur="commitEdit(${index}, this)" onkeydown="checkEnter(event)">${escapeHTML(todo.text)}</span>
            </div>
            <button class="delete-btn" title="Delete task" onclick="remove(${index})"></button>
          `;
          list.appendChild(li);
        }
      });
    }

    function checkEnter(e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        e.target.blur();
      }
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

    function commitEdit(index, element) {
      const newText = element.innerText.trim();
      if (newText) {
        socket.emit('edit_todo', { list: currentList, index, text: newText });
      }
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

BOARD_HTML = """
<!doctype html>
<html>
<head>
  <title>Shared Board</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.5.4/socket.io.min.js"></script>
  <style>
    body { font-family: monospace; margin: 0; padding: 1em; background: #f0f0f0; }
    textarea {
      width: 100%; height: 90vh;
      font-size: 1em; padding: 1em;
      border: 1px solid #ccc; border-radius: 6px;
    }
  </style>
</head>
<body>
  <textarea id="board" placeholder="Start typing..."></textarea>
  <script>
    const boardId = window.location.pathname.split("/").pop();
    const socket = io();
    const textarea = document.getElementById('board');

    textarea.addEventListener('input', () => {
      socket.emit('update_shared_board', { id: boardId, content: textarea.value });
    });

    socket.on('shared_board', content => {
      textarea.value = content;
    });

    socket.emit('join_shared_board', boardId);
  </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(TODO_HTML)

@app.route('/board')
def create_board():
    board_id = str(uuid.uuid4())[:8]
    shared_boards[board_id] = ""
    return redirect(url_for('view_board', board_id=board_id))

@app.route('/board/<board_id>')
def view_board(board_id):
    return render_template_string(BOARD_HTML)

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

@socketio.on('edit_todo')
def handle_edit(data):
    name = data['list']
    index = data['index']
    text = str(data['text']).strip()[:256]
    text = html.escape(text)
    if 0 <= index < len(todos.get(name, [])):
        todos[name][index]['text'] = text
        save_todos()
        emit('todos', {'todos': todos[name], 'lists': list(todos.keys())}, broadcast=True)

@socketio.on('join_shared_board')
def join_shared_board(board_id):
    join_room(board_id)
    content = shared_boards.get(board_id, "")
    emit('shared_board', content, room=board_id)

@socketio.on('update_shared_board')
def update_shared_board(data):
    board_id = data['id']
    content = data['content'][:10000]
    shared_boards[board_id] = content
    emit('shared_board', content, room=board_id)

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0')