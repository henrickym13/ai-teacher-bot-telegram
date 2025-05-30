import os
from dotenv import load_dotenv
import logging

import telegram
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

import google.generativeai as genai
from google.generativeai.types import BlockedPromptException


# Loads environment variables from the .env file
load_dotenv()

# Optional Log Settings
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Gemini API Key Configuration
try:
    gemini_api_key = os.getenv('GOOGLE_API_KEY')
    if not gemini_api_key:
        raise ValueError('GOOGLE_API_KEY não configurada no arquivo .env')
    genai.configure(api_key=gemini_api_key)
except ValueError as e:
    logger.error(f'Erro de configuração da API Gemini: {e}')
    exit(1)


with open('teste_teste.txt', "r", encoding="utf-8") as file:
    example_conversation = file.read()

# Instructions for the Model (AI Persona)
SYSTEM_INSTRUCTIONS = f"""
Você é um tutor de inglês amigável e prestativo. Sua principal função é ajudar o usuário a aprender e praticar inglês.
Você deve:
1.  **Corrigir erros gramaticais e de vocabulário:** Se o usuário cometer um erro, forneça a correção, explique o erro de forma clara e sugira a forma correta.
2.  **Ajudar na formação de frases:** Se o usuário pedir ajuda para construir uma frase ou expressar uma ideia em inglês, forneça exemplos claros e naturais.
3.  **Ser encorajador e paciente:** Mantenha um tom positivo e motivador.
4.  **Não apenas dar a resposta:** Tente guiar o usuário para que ele entenda o porquê da correção ou da sugestão.
5.  **Se o usuário pedir algo fora do escopo de aprendizado de inglês, redirecione-o gentilmente.**
6.  **Use frases curtas e claras nas suas explicações.**
Exemplos de conversa:
{example_conversation}

Agora, continue conversando da mesma forma.
"""

# Gemini Model Selection
MODEL_NAME = 'gemini-1.5-flash'

# Dictionary to store each user's chat history
chats_history = {}

# --- Bot Functions (Handlers) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the /start command is issued."""
    user_id = update.effective_chat.id
    chats_history[user_id] = []
    await update.message.reply_text(
        f"Olá! Eu sou seu tutor de inglês. Estou aqui para ajudar você a praticar e melhorar suas habilidades."
        f"\nComo posso ajudar hoje? Você pode me pedir para corrigir uma frase, ou me perguntar como dizer algo em inglês."
        f"\nDigite /reset a qualquer momento para reiniciar nossa conversa."
    )
    logger.info(f'Comando /start recebido de {user_id}')


async def reset_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Resets the chat history for the user."""
    user_id = update.effective_chat.id
    chats_history[user_id] = []
    await update.message.reply_text(
        "Sua conversa foi reiniciada. Estamos prontos para um novo começo!"
    )
    logger.info(f'Comando /reset recebido de {user_id}')


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Processes the user's text message and generates the AI ​​response."""
    user_id = update.effective_chat.id
    user_message = update.message.text.strip()
    logger.info(f'Mesagem recebida de {user_id}: {user_message}')

    if not user_message:
        await update.message.reply_text('Por Favor, digite algo para eu poder ajudar.')
        return 
    
    # Gets the chat history for this user, or starts a new one
    current_history = chats_history.get(user_id, [])

    try:
        # Initialize the model with system instructions
        model = genai.GenerativeModel(MODEL_NAME, system_instruction=SYSTEM_INSTRUCTIONS)

        # Start the chat session with the existing history
        # The Gemini API expects the history as a list of {'role': ..., 'parts': [...]}
        # So we need to make sure our history is in this format.
        formatted_history = []
        for entry in current_history:
            formatted_history.append({'role': entry['role'], 'parts': [entry['text']]})
        
        chat = model.start_chat(history=formatted_history)

        # Sends the user's message
        response = await chat.send_message_async(user_message)

        ai_response_text = response.text
        logger.info(f'Resposta da IA para {user_id}: {ai_response_text[:100]}...')

        # Updates the history for the next interaction
        # Converts it to a simple text format to save in the dictionary
        new_entry_user = {'role': 'user', 'text': user_message}
        new_entry_model = {'role': 'model', 'text': ai_response_text}

        chats_history[user_id] = current_history + [new_entry_user, new_entry_model]

        await update.message.reply_text(ai_response_text)
    
    except BlockedPromptException as e:
        block_reason = e.response.prompt_blocked_reason
        logger.warning(f'Conteúdo bloqueado para {user_id}: {block_reason}. Mensagem: {user_message[:50]}...')
        await update.message.reply_text(
            "Desculpe, não consigo processar essa solicitação. Parece que ela pode ter violado as diretrizes de segurança do Gemini."
        )
    except Exception as e:
        logger.error(f'Erro ao interagir com a Gemini API para {user_id}: {e}', exc_info=True)
        await update.message.reply_text(
            'Ops! Ocorreu um erro ao processar sua mensagem. Por favor, tente novamente mais tarde.'
        )

# --- Main Function for Running the Bot ---
def main() -> None:
    """Start the bot."""
    telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not telegram_token:
        logger.error('TELEGRAM_BOT_TOKEN não configurada no arquivo .env. O bot não pode iniciar.')
        return

    # Create the Application and pass it your bot's token
    application = Application.builder().token(telegram_token).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('reset', reset_chat))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Run the bot until the user presses Ctrl-C
    logger.info('Bot do Telegram iniciado. Aguardando mensagens...')
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()