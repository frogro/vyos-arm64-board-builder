from anthias_server.django_project.asgi import application as upstream
from storage_guard import Guard
application = Guard(upstream)
