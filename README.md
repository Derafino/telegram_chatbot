# Telegram Chatbot
This repository contains a Telegram chat bot that allows you to interact with various features and functionalities. Follow the instructions below to install and configure the bot for your own use.

## Installation
### Manual Installation</h1> 

1. Clone the repository to your local machine using the following command:
```
git clone https://github.com/Derafino/telegram_chatbot.git
```
2. Navigate to the project directory:
```
cd telegram_chatbot
```
3. Install the required dependencies using pip:
```
pip install -r requirements.txt
```
4. Create a configuration file by making a copy of config.json.example and renaming it to config.json
5. Start the chat bot by running the main script:
```
python main.py
```
### Docker Compose Installation

1. Clone the repository to your local machine using the following command:
```
git clone https://github.com/Derafino/telegram_chatbot.git
```
2. Navigate to the project directory:
```
cd telegram_chatbot
```
3. Create a configuration file by making a copy of config.json.example and renaming it to config.json
4. Build and run the Docker containers using docker-compose:
```
docker-compose up --build
```
## Usage
Once the bot is running and the configuration is set up, you can start interacting with it through Telegram. Add the bot to a group and send it direct messages to trigger the bot's functionality.

`/who` - bot will mention a random user in the chat.

`/8ball [text]` - command allows users to ask the bot a question by providing the question as an argument. The bot will generate a random response from a predefined set of answers, mimicking the behavior of a magic 8-ball. The response is sent back to the user.

`/balance` -  command provides users with information about their account balance. It allows users to check how many coins they have accumulated.

`/pick variant1, variant2...variant5` -  command allows users to make a choice between multiple options. Users pass a list of options as arguments, separated by commas. The bot randomly selects one option from the provided list and sends it back as a response.

`/boosters` - command displays information about active bonuses or boosters related to the chat bot.

`/level` - command allows users to check their current level and experience points (XP) in the bot's system.
