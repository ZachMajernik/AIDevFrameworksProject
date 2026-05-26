# The Ollama Docker container must be running before executing this script
# Copilot added an entry point in the Docker-compose file to pull Ollama on startup
from ollama import Client

# client = Client(host="http://ollama:11434")
client = Client(host="http://localhost:11434")

response = client.chat(
    model="llama3.2",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is Docker in one sentence?"}
    ]
)
print(response.message.content)
