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
            return json.load(f)
    return []

def save_todos():
    with open(DATA_FILE, 'w') as f:
        json.dump(todos, f)

# Load existing todos on startup
todos = load_todos()

HTML = """
<!doctype html>
<html>
<head>
  <title>Realtime Todo List</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.5.4/socket.io.min.js"></script>
  <style>
    body { font-family: sans-serif; padding: 2em; background: #f4f4f9; color: #333; }
    form { margin-bottom: 1em; }
    input[type="text"] { padding: 0.5em; width: 200px; }
    button { padding: 0.5em; margin-left: 0.5em; }
    ul { list-style-type: none; padding: 0; }
    li { margin: 0.5em 0; background: white; padding: 0.5em; border-radius: 5px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .done { text-decoration: line-through; color: #888; }
  </style>
</head>
<body>
  <h2>Realtime Todo List</h2>
  <form id="form">
    <input type="text" id="newtodo" autocomplete="off" placeholder="New todo">
    <button type="submit">Add</button>
  </form>
  <ul id="todolist"></ul>
  <script>
    const socket = io();

    function escapeHTML(str) {
      return str.replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/\"/g, '&quot;')
                .replace(/'/g, '&#039;');
    }

    function renderTodos(todos) {
      const list = document.getElementById('todolist');
      list.innerHTML = '';
      todos.forEach((todo, index) => {
        const li = document.createElement('li');
        li.innerHTML = `
          <input type="checkbox" ${todo.done ? 'checked' : ''} onchange="toggle(${index})">
          <span class="${todo.done ? 'done' : ''}">${escapeHTML(todo.text)}</span>
          <button onclick="remove(${index})">Delete</button>
        `;
        list.appendChild(li);
      });
    }

    socket.on('todos', renderTodos);

    document.getElementById('form').onsubmit = (e) => {
      e.preventDefault();
      const input = document.getElementById('newtodo');
      if (input.value.trim()) {
        socket.emit('add_todo', input.value.trim());
        input.value = '';
      }
    };

    function toggle(index) {
      socket.emit('toggle_todo', index);
    }

    function remove(index) {
      socket.emit('remove_todo', index);
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
    emit('todos', todos)

@socketio.on('add_todo')
def handle_add(todo):
    safe_text = str(todo).strip()[:256]  # sanitize and truncate input
    safe_text = html.escape(safe_text)  # escape for good measure
    todos.append({'text': safe_text, 'done': False})
    save_todos()
    emit('todos', todos, broadcast=True)

@socketio.on('toggle_todo')
def handle_toggle(index):
    if 0 <= index < len(todos):
        todos[index]['done'] = not todos[index]['done']
        save_todos()
        emit('todos', todos, broadcast=True)

@socketio.on('remove_todo')
def handle_remove(index):
    if 0 <= index < len(todos):
        todos.pop(index)
        save_todos()
        emit('todos', todos, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, debug=False, host='0.0.0.0')
