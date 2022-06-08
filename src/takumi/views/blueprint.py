from flask import Blueprint

api = Blueprint("api", "api")
tasks = Blueprint("tasks", "tasks", url_prefix="/tasks/<uuid:task_id>")
webhooks = Blueprint("callbacks", "callbacks", url_prefix="/callbacks")
