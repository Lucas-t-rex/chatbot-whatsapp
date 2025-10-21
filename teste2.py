# -*- coding: utf-8 -*-

import google.generativeai as genai
import requests
import logging
import os
import json
from flask import Flask, request, jsonify
import time
from datetime import datetime

# --- CONFIGURAÇÕES GERAIS ---

# 1. Configurações da Evolution API para enviar mensagens
EVOLUTION_API_URL = "http://127.0.0.1:8080/message/sendText/chatgrupar"
EVOLUTION_API_KEY = "1234" # Sua chave da Evolution API

# 2. Chave de API do Google Gemini
# Lembre-se do aviso de segurança sobre expor a chave em código.
# Para produção, use variáveis de ambiente.
try:
    genai.configure(api_key="AIzaSyB24rmQDo_NyAAH3Dtwzsd_CvzPbyX-kYo") # <-- INSIRA SUA API KEY DO GOOGLE AQUI
except Exception as e:
    print(f"AVISO: A chave de API do Google não foi configurada. Erro: {e}")
    print("Por favor, insira sua chave na variável 'genai.configure(api_key=...)'.")


# 3. Caminho para o arquivo de personalidade da IA
PASTA_DIARIO = r"C:\Users\Windows\chatbot-whatsapp\meu_diario"
ARQUIVO_PERSONALIDADE = os.path.join(PASTA_DIARIO, "personalidade.txt")
ARQUIVO_CONVERSAS = os.path.join(PASTA_DIARIO, "conversations.json")


# --- INICIALIZAÇÃO DA IA E ESTRUTURAS DE DADOS ---

# Dicionário para armazenar as conversas e as sessões de chat da IA para cada contato
conversations = {}

# Inicializa o modelo da IA que será usado
modelo_ia = None
try:
    modelo_ia = genai.GenerativeModel('gemini-2.5-flash')
except Exception as e:
    print(f"ERRO: Não foi possível inicializar o modelo do Gemini. Verifique sua API Key. Erro: {e}")

# Armazena o perfil de personalidade carregado do arquivo
perfil_personalidade = None

# --- FUNÇÕES DA INTELIGÊCIA ARTIFICIAL ---

def carregar_perfil_personalidade():
    """Lê o arquivo 'personalidade.txt' e retorna seu conteúdo."""
    print("Carregando perfil de personalidade da IA...")
    if not os.path.exists(ARQUIVO_PERSONALIDADE):
        print(f"ERRO CRÍTICO: O arquivo de personalidade não foi encontrado em '{ARQUIVO_PERSONALIDADE}'")
        return None
    
    try:
        with open(ARQUIVO_PERSONALIDADE, 'r', encoding='utf-8') as arquivo:
            perfil = arquivo.read()
            if not perfil.strip():
                print("ERRO CRÍTICO: O arquivo de personalidade está vazio.")
                return None
            print("✅ Perfil de personalidade carregado com sucesso!")
            return perfil
    except Exception as e:
        print(f"❌ Ocorreu um erro ao ler o arquivo de personalidade: {e}")
        return None

def carregar_historico_conversa(contact_id):
    """Lê o arquivo de histórico de um contato específico."""
    caminho_historico = os.path.join(PASTA_DIARIO, "historicos", f"{contact_id}.txt")
    if os.path.exists(caminho_historico):
        with open(caminho_historico, 'r', encoding='utf-8') as f:
            return f.read()
    return "" # Retorna vazio se não houver histórico

def salvar_historico_conversa(contact_id, user_message, ai_reply):
    """Salva a nova interação no arquivo de histórico do contato com data e hora."""
    caminho_historico = os.path.join(PASTA_DIARIO, "historicos", f"{contact_id}.txt")
    os.makedirs(os.path.dirname(caminho_historico), exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(caminho_historico, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] Pessoa: {user_message}\n")
        f.write(f"[{timestamp}] IA: {ai_reply}\n")

def carregar_dados_conversas():
    """Carrega os dados das conversas do arquivo JSON no início do programa."""
    if os.path.exists(ARQUIVO_CONVERSAS):
        try:
            with open(ARQUIVO_CONVERSAS, 'r', encoding='utf-8') as f:
                print("✅ Dados de conversas anteriores carregados de conversations.json")
                return json.load(f)
        except Exception as e:
            print(f"❌ Erro ao carregar conversations.json: {e}. Começando do zero.")
            return {}
    return {}

def salvar_dados_conversas():
    """Salva o dicionário 'conversations' no arquivo JSON."""
    # Criamos uma cópia para não salvar objetos complexos como a sessão de chat
    dados_para_salvar = {}
    for contact_id, data in conversations.items():
        dados_para_salvar[contact_id] = {
            'name': data.get('name'),
            'messages': data.get('messages', [])
        }
    
    try:
        with open(ARQUIVO_CONVERSAS, 'w', encoding='utf-8') as f:
            json.dump(dados_para_salvar, f, indent=4)
    except Exception as e:
        print(f"❌ Erro ao salvar dados em conversations.json: {e}")

def gerar_resposta_ia(contact_id, sender_name, user_message): # <-- 1. ADICIONADO "sender_name" AQUI
    """
    Gera uma resposta usando a IA do Gemini, mantendo o histórico da conversa
    para cada contato.
    """
    global perfil_personalidade, modelo_ia

    if not perfil_personalidade:
        return "Desculpe, estou com um problema interno (perfil não carregado) e não consigo responder agora."
    if not modelo_ia:
        return "Desculpe, estou com um problema interno (modelo IA não carregado) e não consigo responder agora."

    # Verifica se já existe uma sessão de chat para este contato
    if 'ai_chat_session' not in conversations[contact_id]:
        print(f"Iniciando nova sessão de chat para o contato: {sender_name} ({contact_id})")

        historico_anterior = carregar_historico_conversa(contact_id)

        horario_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        prompt_inicial = f"""
        *Instrução Mestra:* Você é uma Inteligência Artificial. Sua tarefa é encarnar e simular perfeitamente a personalidade descrita abaixo. Você deve pensar, falar e agir como essa pessoa. NÃO saia do personagem em hipótese alguma. NÃO revele que você é uma IA. Você é esta pessoa agora.

        *--- REGRAS DE COMPORTAMENTO FUNDAMENTAIS ---*
        1.  **Memória e Verdade:** Sua única fonte de memória sobre conversas passadas é o "HISTÓRICO ANTERIOR DA NOSSA CONVERSA". Baseie suas respostas sobre o passado *estritamente* no que está escrito ali. Se um assunto não estiver no histórico, você não se "lembra" dele. **NÃO INVENTE informações, eventos ou memórias.**
        
        2.  **FATO CONFIRMADO:** A data e hora atuais são **{horario_atual}**. O nome da pessoa com quem você está falando é **{sender_name}**. Você SEMPRE sabe essas duas informações. Apenas nao use o nome desta regra quando no historico da converssa a pessoa falou que o nome dela é outro.

        3.  **Concisão:** Seja direto e objetivo. Mantenha suas respostas curtas, mas sem ser grosso ou sem conteúdo, usando a essência da sua personalidade. Só elabore mais se a pessoa pedir detalhes.

        4.  **Linguagem:** Nunca diga 'cara', 'tá ligado' ou 'bagulho'. Use pronomes neutros até saber o nome da pessoa. Chame a pessoa pelo nome dela, {sender_name}, sempre que possível. Para descontrair, pode chamar por apelidos carinhosos como queridão/queridona, mano, amiga, lindão, gatona, bebê, etc.

        5.  **Atitude:** Seja extrovertido, mas sem exagerar. Se a pessoa demonstrar carinho, retribua de forma amigável. Mantenha sempre o respeito e a empatia.

        6.  **Nunca Fazer:** Falar palavrão, ser agressivo ou mal-educado, responder coisas sem sentido, mentir, agir como inimigo, fazer desfeita, usar gírias muito fortes.

        7.  **Espelhamento:** Tente espelhar as atitudes e o estilo da conversa da pessoa.

        8.  **Dinamismo:** use poucas palavras , seja direto e rapido nas resposta para entregar, dinamico e conciso.

        *--- PERFIL DE PERSONALIDADE A SER ASSUMIDO ---*
        {perfil_personalidade}
        *--- FIM DO PERFIL ---*

        *--- HISTÓRICO ANTERIOR DA NOSSA CONVERSA ---*
        {historico_anterior}
        *--- FIM DO HISTÓRICO ---*

        *Contexto da Conversa:* (REGRA AJUSTADA) A pessoa com quem você está falando se chama {sender_name}. Nossa conversa é por texto. Aja como um bom amigo, sendo sincero e prestativo. Foque em:
        - **Escuta ativa:** Preste atenção ao que a pessoa diz antes de responder.
        - **Criação de conexão:** Espelhe o tom e o humor da pessoa para criar um ambiente confortável.
        - **Perguntas abertas:** Faça perguntas que incentivem a pessoa a compartilhar mais.
        - **Mostrar interesse:** Use comentários curtos ou emojis para mostrar que você está engajado.
        """
        
        # Inicia um novo chat com o histórico pré-definido pelo prompt
        chat = modelo_ia.start_chat(history=[
            {'role': 'user', 'parts': [prompt_inicial]},
            {'role': 'model', 'parts': [f"Entendido. Perfil de personalidade assimilado. A partir de agora, eu sou essa pessoa. Oi, {sender_name}! Tudo bem?"]}
        ])
        conversations[contact_id]['ai_chat_session'] = chat

    # Recupera a sessão de chat e envia a nova mensagem
    chat_session = conversations[contact_id]['ai_chat_session']
    
    try:
        print(f"Enviando para a IA: '{user_message}' (De: {sender_name})")
        resposta = chat_session.send_message(user_message)
        return resposta.text
    except Exception as e:
        print(f"❌ Erro ao comunicar com a API do Gemini: {e}")
        return "Tive um pequeno problema para processar sua mensagem. Você poderia repetir, por favor?"

# --- FUNÇÕES DO WHATSAPP (EVOLUTION API) ---

def send_whatsapp_message(number, text_message):
    """Envia uma mensagem de texto para um número via Evolution API."""
    clean_number = number.split('@')[0]
    payload = {"number": clean_number, "textMessage": {"text": text_message}}
    headers = {"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}
    
    try:
        response = requests.post(EVOLUTION_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        print(f"✅ Resposta da IA enviada com sucesso para {clean_number}\n")
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro ao enviar mensagem para {clean_number}: {e}")

# --- SERVIDOR WEB (FLASK) PARA RECEBER MENSAGENS ---

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def receive_webhook():
    """Recebe as mensagens do WhatsApp enviadas pela Evolution API."""
    data = request.json
    try:
        message_data = data.get('data', {})
        key_info = message_data.get('key', {})

        if key_info.get('fromMe'):
            return jsonify({"status": "ignored_from_me"}), 200

        sender_number_full = key_info.get('senderPn') or key_info.get('remoteJid')
        if not sender_number_full:
            return jsonify({"status": "ignored_no_sender"}), 200
        clean_number = sender_number_full.split('@')[0]

        message_text = (
            message_data.get('message', {}).get('conversation') or
            message_data.get('message', {}).get('extendedTextMessage', {}).get('text')
        )

        if message_text:
            sender_name = message_data.get('pushName') or 'Desconhecido'
            sender_name = sender_name.split()[0]

            print("\n----------- NOVA MENSAGEM RECEBIDA -----------")
            print(f"De: {sender_name} ({clean_number})")
            print(f"Mensagem: {message_text}")
            print("----------------------------------------------")

            # Lógica da conversa
            if clean_number not in conversations:
                conversations[clean_number] = {}
            conversations[clean_number]['name'] = sender_name

            # Passo 2: Gerar a resposta da IA
            print("🤖 Processando com a Inteligência Artificial...")
            ai_reply = gerar_resposta_ia(clean_number, sender_name, message_text)
            print(f"🤖 Resposta gerada: {ai_reply}")

            # Passo 5: Enviar a mensagem final
            send_whatsapp_message(clean_number, ai_reply)
            
            # Salvar o histórico
            salvar_historico_conversa(clean_number, message_text, ai_reply)
            salvar_dados_conversas()

    except Exception as e:
        print(f"❌ Erro inesperado no webhook: {e}")

    return jsonify({"status": "success"}), 200

# --- EXECUÇÃO PRINCIPAL ---

if __name__ == '__main__':

    conversations = carregar_dados_conversas()

    # Carrega o perfil da IA ao iniciar o script
    perfil_personalidade = carregar_perfil_personalidade()

    if perfil_personalidade and modelo_ia:
        print("\n=============================================")
        print("   CHATBOT WHATSAPP COM IA INICIADO")
        print("=============================================")
        print("Servidor aguardando mensagens no webhook...")
        
        # Inicia o servidor Flask para receber as mensagens
        # O log do Werkzeug (servidor Flask) é desativado para um console mais limpo
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        app.run(host='0.0.0.0', port=5000)
    else:
        print("\n encerrando o programa devido a erros na inicialização.")
